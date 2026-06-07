"""
语音对话管理器
处理语音通话中的对话流程和TTS集成

复用了 /chat 端点中已有的 agent 调用模式 ——
所有 agent 都是模块级函数，不是类方法。
"""
import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

from funcation import memory, prompt
from funcation import memory_agent as memory_agent_mod
from funcation import profile_agent
from funcation import recall_agent
from funcation import relationship_agent
from funcation import state_agent
from funcation import story_agent
from funcation import world_event_agent
from funcation.memory_center import MemoryCenter
from funcation.memory_rag import retrieve_memories
from funcation.utils import retry_async

from .voice_service import voice_service

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 类型 / 枚举
# ---------------------------------------------------------------------------

class ConversationState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class ConversationContext:
    call_id: str
    character_id: str
    user_id: str
    state: ConversationState = ConversationState.IDLE
    message_history: list = field(default_factory=list)
    last_audio_time: float = 0.0
    audio_buffer: bytes = b""
    last_response_time: float = 0.0
    websocket: Any = None
    stats: dict = field(default_factory=lambda: {
        "messages_processed": 0,
        "audio_bytes_received": 0,
        "tts_requests": 0,
        "errors": 0,
    })


# ---------------------------------------------------------------------------
# 对话管理器
# ---------------------------------------------------------------------------

class ConversationManager:

    def __init__(self):
        self.contexts: Dict[str, ConversationContext] = {}
        self.memory_centers: Dict[str, MemoryCenter] = {}
        self.tts_queue: asyncio.Queue = asyncio.Queue()
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        """延迟初始化 OpenAI 客户端（复用 .env 里的 key）"""
        if self._client is None:
            self._client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com",
            )
        return self._client

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start_conversation(self, call_id: str, character_id: str, user_id: str, websocket=None) -> bool:
        """初始化一个通话会话"""
        # 防护：character_id 不能为空
        if not character_id:
            logger.error("start_conversation: character_id is required")
            return False

        try:
            ctx = ConversationContext(
                call_id=call_id,
                character_id=character_id,
                user_id=user_id,
                websocket=websocket,
            )
            self.contexts[call_id] = ctx

            if character_id not in self.memory_centers:
                mc = MemoryCenter()
                mc.set_current_character(character_id)
                self.memory_centers[character_id] = mc

            logger.info("Conversation started — call_id=%s char=%s", call_id, character_id)
            return True
        except Exception as exc:
            logger.error("start_conversation failed: %s", exc)
            return False

    async def end_conversation(self, call_id: str):
        """结束通话并持久化状态"""
        try:
            ctx = self.contexts.pop(call_id, None)
            if ctx is None:
                return
            mc = self.memory_centers.get(ctx.character_id)
            if mc:
                mc.save_memory(ctx.character_id, mc.load_memory(ctx.character_id))
            logger.info("Conversation ended — call_id=%s", call_id)
        except Exception as exc:
            logger.error("end_conversation failed: %s", exc)

    # ------------------------------------------------------------------
    # 音频处理
    # ------------------------------------------------------------------

    async def process_audio(self, call_id: str, audio_data: bytes) -> Optional[Dict]:
        """收到前端音频 chunk 时调用"""
        ctx = self.contexts.get(call_id)
        if ctx is None:
            return None

        try:
            ctx.audio_buffer += audio_data
            ctx.last_audio_time = time.time()
            ctx.stats["audio_bytes_received"] += len(audio_data)
            ctx.state = ConversationState.LISTENING

            return {
                "type": "audio_received",
                "call_id": call_id,
                "audio_length": len(audio_data),
                "state": ctx.state.value,
            }
        except Exception as exc:
            logger.error("process_audio error: %s", exc)
            ctx.state = ConversationState.ERROR
            ctx.stats["errors"] += 1
            return {"type": "error", "call_id": call_id, "message": str(exc)}

    async def process_text_message(self, call_id: str, user_message: str) -> Dict:
        """处理前端识别的文本（浏览器端语音识别完成后调用）"""
        logger.info("[VOICE CM] process_text_message call_id=%s text='%s'", call_id, user_message[:80])

        ctx = self.contexts.get(call_id)
        if ctx is None:
            logger.error("[VOICE CM] call_id=%s 未找到会话！活跃会话: %s", call_id, list(self.contexts.keys()))
            return {"type": "error", "call_id": call_id, "message": "call not found"}

        ctx.state = ConversationState.PROCESSING
        ctx.message_history.append({"role": "user", "content": user_message})
        ctx.stats["messages_processed"] += 1

        try:
            logger.info("[VOICE CM] → _generate_response call_id=%s", call_id)
            response = await self._generate_response(ctx, user_message)
            logger.info("[VOICE CM] ← _generate_response 完成 text='%s'", response.get("text", "")[:80])
            ctx.state = ConversationState.IDLE
            return {"type": "response", "call_id": call_id, **response}
        except Exception as exc:
            logger.error("[VOICE CM] process_text_message error: %s", exc)
            ctx.state = ConversationState.ERROR
            ctx.stats["errors"] += 1
            return {"type": "error", "call_id": call_id, "message": str(exc)}

    # ------------------------------------------------------------------
    # AI 回复生成（完全复用 /chat 的 agent 流程）
    # ------------------------------------------------------------------

    async def _generate_response(self, ctx: ConversationContext, user_input: str) -> Dict:
        char_id = ctx.character_id
        mc = self.memory_centers[char_id]

        # -- 与 /chat 保持一致的调用顺序 --
        character = mc.load_character_by_id(char_id)
        world = mc.load_current_world()
        world_id = world.get("id") if world else None

        # ① 世界事件
        world_event_agent.tick(mc, character, world)

        # ② 剧情
        story_agent.check_story(mc, character, world)
        memory_data = mc.load_memory(char_id)
        memory_data = story_agent.sync_story_to_state(memory_data)
        mc.save_memory(char_id, memory_data)

        # ③ RAG 检索
        recalled = recall_agent.detect_memory_scope(user_input, char_id)
        retrieved = retrieve_memories(char_id, user_input, top_k=10, world_id=world_id, collections=recalled)

        # ④ 构建 system prompt
        system_prompt = prompt.build_system_prompt(
            character_id=char_id,
            memory_data=memory_data,
            world=world,
            messages=ctx.message_history,
            retrieved_memories=retrieved,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(ctx.message_history[-10:])  # 最近 10 轮
        messages.append({"role": "user", "content": user_input})

        # ⑤ 画像
        mc.update_profile(user_input, char_id)

        # ⑥ 关系
        relationship_agent.update_relationship(mc, char_id, user_input)

        # ⑦ 状态
        current_state = memory_data.get("character_state", {})
        new_state = state_agent.analyze_state(user_input, current_state, world)
        mc.update_character_state(char_id, new_state)

        # ⑧ DeepSeek 生成（带重试）
        logger.info("[VOICE CM] → DeepSeek API 调用 (messages=%d 条)", len(messages))
        resp = await retry_async(
            lambda: self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.9,
            ),
            max_retries=3,
        )
        ai_reply = resp.choices[0].message.content.strip()
        logger.info("[VOICE CM] ← DeepSeek 返回: '%s'", ai_reply[:100])

        # 保存本轮对话到消息历史（维持多轮上下文）
        ctx.message_history.append({"role": "assistant", "content": ai_reply})

        # ⑨ 记忆提取（非关键路径，失败不影响回复）
        try:
            current_memories = mc.get_long_memories_text(char_id)
            memory_result = memory_agent_mod.extract_memory(user_input, current_memories)
            action = memory_result.get("action", "ignore")
            if action == "add":
                mc.add_long_memory(char_id, memory_result["memory"])
            elif action == "update":
                mc.update_long_memory(
                    char_id,
                    memory_result.get("old_memory", ""),
                    memory_result.get("new_memory", ""),
                )
        except Exception as mem_err:
            logger.warning("记忆提取失败（非关键）: %s", mem_err)

        # ⑩ 保存 & 聊天摘要（非关键路径）
        try:
            mc.add_chat_summary(char_id, f"用户: {user_input}")
            mc.add_chat_summary(char_id, f"AI: {ai_reply}")
            mc.update_last_chat_time(char_id)
            mc.save_memory(char_id, memory_data)
            # 追加本轮对话到主聊天历史（不覆盖已有记录）
            try:
                existing = memory.load_memory(char_id)
                existing.append({"role": "user", "content": user_input})
                existing.append({"role": "assistant", "content": ai_reply})
                memory.save_memory(char_id, existing)
            except Exception:
                # 回退：直接保存 voice session 历史
                memory.save_memory(char_id, ctx.message_history)
        except Exception as save_err:
            logger.warning("保存状态失败（非关键）: %s", save_err)

        # ⑪ TTS 异步合成（非关键路径）
        try:
            await self._queue_tts(ctx.call_id, ai_reply, char_id)
            ctx.stats["tts_requests"] += 1
        except Exception as tts_err:
            logger.warning("TTS 入队失败（非关键）: %s", tts_err)

        ctx.last_response_time = time.time()

        return {
            "text": ai_reply,
            "favorability": mc.load_memory(char_id).get("favorability", 50),
        }

    # ------------------------------------------------------------------
    # TTS 队列
    # ------------------------------------------------------------------

    async def _queue_tts(self, call_id: str, text: str, character_id: str):
        await self.tts_queue.put({
            "call_id": call_id,
            "text": text,
            "character_id": character_id,
        })

    async def process_tts_queue(self):
        """后台协程：逐条消费 TTS 队列"""
        while True:
            try:
                item = await self.tts_queue.get()
                call_id = item["call_id"]
                text = item["text"]
                character_id = item["character_id"]

                ctx = self.contexts.get(call_id)
                if ctx:
                    ctx.state = ConversationState.SPEAKING

                audio_data = await voice_service.synthesize_speech(text=text, character_id=character_id)
                await self._send_audio_to_frontend(call_id, audio_data)

                if ctx:
                    ctx.state = ConversationState.IDLE
            except Exception as exc:
                logger.error("process_tts_queue error: %s", exc)

    async def _send_audio_to_frontend(self, call_id: str, audio_data: bytes):
        """通过 WebSocket 将 TTS 音频下发给前端（base64 编码）"""
        ctx = self.contexts.get(call_id)
        if ctx is None or ctx.websocket is None:
            logger.warning("TTS audio skipped — no websocket for call_id=%s", call_id)
            return

        try:
            payload = json.dumps({
                "type": "tts_audio",
                "call_id": call_id,
                "audio": base64.b64encode(audio_data).decode("ascii"),
                "format": "wav",
            })
            await ctx.websocket.send_text(payload)
            logger.info("TTS audio sent — call_id=%s size=%d", call_id, len(audio_data))
        except Exception as exc:
            logger.error("Failed to send TTS audio — call_id=%s: %s", call_id, exc)

    # ------------------------------------------------------------------
    # 状态查询 / 清理
    # ------------------------------------------------------------------

    async def get_conversation_status(self, call_id: str) -> Optional[Dict]:
        ctx = self.contexts.get(call_id)
        if ctx is None:
            return None

        mc = self.memory_centers.get(ctx.character_id)
        favorability = mc.load_memory(ctx.character_id).get("favorability", 50) if mc else 0

        return {
            "call_id": call_id,
            "state": ctx.state.value,
            "favorability": favorability,
            "message_count": len(ctx.message_history),
            "last_audio_time": ctx.last_audio_time,
            "stats": ctx.stats,
        }

    async def get_active_calls(self) -> Dict[str, Any]:
        active = []
        for call_id, ctx in self.contexts.items():
            if ctx.state != ConversationState.IDLE:
                active.append({
                    "call_id": call_id,
                    "character_id": ctx.character_id,
                    "state": ctx.state.value,
                    "message_count": len(ctx.message_history),
                    "stats": ctx.stats,
                })
        return {"total": len(self.contexts), "active": len(active), "calls": active}

    async def cleanup_stale_calls(self, max_idle_sec: int = 300) -> int:
        now = time.time()
        stale = [
            call_id for call_id, ctx in self.contexts.items()
            if ctx.state == ConversationState.IDLE and (now - ctx.last_audio_time) > max_idle_sec
        ]
        for call_id in stale:
            await self.end_conversation(call_id)
        return len(stale)


# 全局单例（供 WebSocket 路由使用）
conversation_manager = ConversationManager()
