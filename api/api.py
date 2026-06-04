from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from funcation import memory, prompt
from funcation import utils
from funcation import memory_agent
from funcation.memory_center import MemoryCenter
from funcation import state_agent
from funcation import event_agent
from funcation import story_agent
from funcation import relationship_agent

load_dotenv()

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 数据中心单例
mc = MemoryCenter()


class ChatRequest(BaseModel):
    message: str


class SwitchCharacterRequest(BaseModel):
    character_id: str


# 聊天接口
@app.post("/chat")
def chat(req: ChatRequest):

    user_input = req.message

    # 当前角色
    character = mc.load_current_character()
    char_id = character["id"]

    # 聊天历史（由 memory.py 管理，数据量大不适合放统一文件）
    messages = memory.load_memory(char_id)

    # 统一记忆数据（画像 + 好感度 + 长期记忆 + 事件 + 聊天摘要）
    mem = mc.load_memory(char_id)


    # 当前世界观
    world = mc.load_current_world()

    event_agent.check_daily_event(
        mc,
        character,
        world
    )

    story_agent.check_story(
        mc,
        character,
        world
    )
    memory_data = mc.load_memory(
        character["id"]
    )
    memory_data = (
        story_agent.sync_story_to_state(
            memory_data
        )
    )

    mc.save_memory(
        character["id"],
        memory_data
    )

    memory_data = mc.load_memory(
        character["id"]
    )

    # 角色状态
    current_state = (
        memory_data.get(
            "character_state",
            {}
        )
    )

    # 构建 Prompt
    system_prompt = prompt.build_system_prompt(
        character_id=char_id,
        memory_data=mem,
        world=world,
        messages=messages
    )

    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = system_prompt
    else:
        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })

    # 更新用户画像
    mc.update_profile(user_input, char_id)

    # 更新好感度
    relationship_agent.update_relationship(
        mc,
        character["id"],
        user_input
    )


    new_state = (
        state_agent.analyze_state(
            user_input,
            current_state,
            world
        )
    )
    mc.update_character_state(
        character["id"],
        new_state
    )

    messages.append({
        "role": "user",
        "content": user_input
    })

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.9
    )

    ai_reply = response.choices[0].message.content

    messages.append({
        "role": "assistant",
        "content": ai_reply
    })

    # 更新最后聊天时间
    mc.update_last_chat_time(char_id)

    # 保存聊天历史
    memory.save_memory(char_id, messages)

    # 长期记忆提取（AI agent）
    current_memories = mc.get_long_memories_text(char_id)
    memory_result = memory_agent.extract_memory(user_input, current_memories)

    action = memory_result.get("action", "ignore")
    if action == "add":
        mc.add_long_memory(char_id, memory_result["memory"])
    elif action == "update":
        mc.update_long_memory(
            char_id,
            memory_result.get("old_memory", ""),
            memory_result.get("new_memory", "")
        )

    return {
        "reply": ai_reply,
        "favorability": mc.get_favorability(char_id)
    }


# 获取好感度
@app.get("/favorability")
def favorability():
    char_id = mc.get_current_character_id()
    return {
        "favorability": mc.get_favorability(char_id)
    }


# 获取用户画像
@app.get("/profile")
def profile():
    char_id = mc.get_current_character_id()
    return {
        "profile": mc.get_profile(char_id)
    }


# 保存用户画像
@app.post("/profile")
def save_profile(req: ChatRequest):
    char_id = mc.get_current_character_id()
    try:
        profile = json.loads(req.message)
        mem = mc.load_memory(char_id)
        mem["profile"] = profile
        mc.save_memory(char_id, mem)
    except:
        pass
    return {
        "message": "保存成功"
    }


# 获取历史记录
@app.get("/history")
def history():
    character = mc.load_current_character()
    messages = memory.load_memory(character["id"])
    return {
        "messages": messages[-10:]
    }


# 获取记忆
@app.get("/memory")
def get_memory():
    character = mc.load_current_character()
    messages = memory.load_memory(character["id"])
    user_messages = [
        msg["content"]
        for msg in messages
        if msg["role"] == "user"
    ]
    return {
        "memory": user_messages
    }


# 清空记忆
@app.post("/clear-memory")
def clear_memory():
    character = mc.load_current_character()
    memory.clear_memory(character["id"])
    return {
        "message": "清空成功"
    }


# 获取角色列表
@app.get("/characters")
def get_characters():
    return {
        "characters": mc.get_all_characters()
    }


# 切换角色
@app.post("/character/switch")
def switch_character(req: SwitchCharacterRequest):
    mc.set_current_character(req.character_id)
    return {
        "message": "切换成功"
    }


# 获取世界列表
@app.get("/worlds")
def get_worlds():
    return {
        "worlds": mc.get_all_worlds()
    }


# 切换世界
@app.post("/world/switch")
def switch_world(req: SwitchCharacterRequest):
    mc.set_current_world(req.character_id)
    return {
        "message": "切换成功"
    }


# 获取长期记忆
@app.get("/long-memory")
def get_long_memory():
    char_id = mc.get_current_character_id()
    return {
        "long_memory": mc.get_long_memories(char_id)
    }


# 获取事件
@app.get("/events")
def get_events():
    char_id = mc.get_current_character_id()
    return {
        "events": mc.get_events(char_id)
    }


# ============================================================
# 新增：角色信息
# ============================================================


# 获取当前角色详情
@app.get("/character/current")
def get_current_character():
    """获取当前角色的完整静态定义"""
    character = mc.load_current_character()
    return {
        "character": character
    }


# 获取角色状态
@app.get("/character/state")
def get_character_state():
    """获取当前角色状态（心情、精力、当前事件）"""
    char_id = mc.get_current_character_id()
    return {
        "state": mc.get_character_state(char_id)
    }


# ============================================================
# 新增：关系信息
# ============================================================


# 获取关系信息
@app.get("/relationship")
def get_relationship():
    """获取当前角色与用户的关系（等级、最近变化原因）"""
    char_id = mc.get_current_character_id()
    mem = mc.load_memory(char_id)
    relationship = mem.get("relationship", {})
    return {
        "relationship": relationship,
        "favorability": mem.get("favorability", 50)
    }


# ============================================================
# 新增：剧情
# ============================================================


# 获取当前剧情
@app.get("/story")
def get_story():
    """获取当前剧情信息"""
    char_id = mc.get_current_character_id()
    mem = mc.load_memory(char_id)
    story = mem.get("story", {})
    return {
        "story": story
    }


# ============================================================
# 新增：聊天摘要
# ============================================================


# 获取聊天摘要
@app.get("/chat-summary")
def get_chat_summary():
    """获取聊天摘要列表"""
    char_id = mc.get_current_character_id()
    return {
        "chat_summary": mc.get_chat_summary(char_id)
    }


# ============================================================
# 新增：主动消息 & 关心消息
# ============================================================


# 获取主动消息
@app.get("/proactive-message")
def get_proactive_message():
    """获取角色的主动问候消息（基于好感度和离线时间）"""
    char_id = mc.get_current_character_id()
    return {
        "message": mc.get_proactive_message(char_id)
    }


# 获取关心消息
@app.get("/caring-message")
def get_caring_message():
    """获取角色的关心消息（基于用户画像）"""
    char_id = mc.get_current_character_id()
    msg = mc.get_caring_message(char_id)
    return {
        "message": msg
    }


# ============================================================
# 新增：事件管理
# ============================================================


class EventRequest(BaseModel):
    event: str


# 添加自定义事件
@app.post("/events")
def add_event(req: EventRequest):
    """手动添加一个事件"""
    char_id = mc.get_current_character_id()
    mc.add_event(char_id, req.event)
    return {
        "message": "事件已添加",
        "events": mc.get_events(char_id)
    }


# ============================================================
# 新增：长期记忆管理
# ============================================================


class MemoryItemRequest(BaseModel):
    memory: str


class MemoryUpdateRequest(BaseModel):
    old_memory: str
    new_memory: str


# 添加长期记忆
@app.post("/long-memory/add")
def add_long_memory(req: MemoryItemRequest):
    """手动添加一条长期记忆"""
    char_id = mc.get_current_character_id()
    mc.add_long_memory(char_id, req.memory)
    return {
        "message": "记忆已添加",
        "long_memory": mc.get_long_memories(char_id)
    }


# 更新长期记忆
@app.post("/long-memory/update")
def update_long_memory(req: MemoryUpdateRequest):
    """手动更新一条长期记忆"""
    char_id = mc.get_current_character_id()
    mc.update_long_memory(char_id, req.old_memory, req.new_memory)
    return {
        "message": "记忆已更新",
        "long_memory": mc.get_long_memories(char_id)
    }


# 删除长期记忆
@app.delete("/long-memory")
def delete_long_memory(req: MemoryItemRequest):
    """删除一条长期记忆（通过将其设为空来移除）"""
    char_id = mc.get_current_character_id()
    mem = mc.load_memory(char_id)
    memories = mem.get("long_memory", [])
    if req.memory in memories:
        memories.remove(req.memory)
        mem["long_memory"] = memories
        mc.save_memory(char_id, mem)
        return {
            "message": "记忆已删除",
            "long_memory": memories
        }
    return {
        "message": "未找到该记忆",
        "long_memory": memories
    }


# ============================================================
# 新增：完整记忆数据
# ============================================================


# 获取完整记忆数据
@app.get("/memory/full")
def get_full_memory():
    """获取当前角色的完整记忆数据（所有动态状态）"""
    char_id = mc.get_current_character_id()
    mem = mc.load_memory(char_id)
    return {
        "memory": mem
    }


# ============================================================
# 新增：世界信息
# ============================================================


# 获取当前世界详情
@app.get("/world/current")
def get_current_world():
    """获取当前世界的完整定义"""
    world = mc.load_current_world()
    return {
        "world": world
    }
