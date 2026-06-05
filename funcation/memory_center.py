"""
MemoryCenter - 角色数据中心

统一管理一个角色的所有动态数据：
- 用户画像 (profile)
- 好感度 (favorability)
- 长期记忆 (long_memory)
- 事件 (events)
- 聊天摘要 (chat_summary)

也管理角色和世界的切换与加载。

数据存储结构:
data/
├── characters/          # 静态角色定义
├── worlds/              # 静态世界定义
└── memories/            # 每个角色一个文件，包含所有动态状态
"""

import json
import os
import random
from datetime import datetime


# ============================================================
# 路径常量
# ============================================================

DATA_DIR = "data"
CHARACTERS_DIR = os.path.join(DATA_DIR, "characters")
WORLDS_DIR = os.path.join(DATA_DIR, "worlds")
WORLD_STATE_DIR = os.path.join(DATA_DIR, "world_state")
MEMORIES_DIR = os.path.join(DATA_DIR, "memories")

CURRENT_CHARACTER_FILE = "current_character.json"
CURRENT_WORLD_FILE = "current_world.json"


# ============================================================
# 默认记忆工厂
# ============================================================

def create_default_memory():
    """创建一个角色的默认记忆结构（大数据字段由 ChromaDB 管理，JSON 仅存小状态）"""
    return {
        "profile": {
            "name": "",
            "city": "",
            "job": "",
            "mood": "",
            "recent_topics": []
        },
        "favorability": 50,
        "relationship": {
            "level": "普通",
            "last_reason": ""
        },
        "character_state": {

            "mood": "开心",

            "energy": 80,

            "current_event": {

                "title": "",

                "description": "",
                "event_date": "",

                "start_time": "",
                "impact": -20
            },

            "last_active_time": ""
        },
        "proactive": {

            "last_time": "",

            "last_message": "",
            "today_count": 0,

            "last_trigger": "",

            "cooldown_hours": 6
        },
        "story": {
            "story_id": "",
            "title": "",
            "description": "",
            "stage": 0,
            "max_stage": 0,
            "stages": [],
            "last_update_date": ""
        },
        "last_chat_time": None
    }

# ChromaDB 管理的大数据字段（不存入 JSON）
_CHROMA_FIELDS = ["long_memory", "events", "chat_summary"]


def create_default_world_state(world_id=""):
    """创建世界动态状态的默认结构（独立于角色记忆）"""
    now = datetime.now().isoformat()
    return {
        "world_id": world_id,
        "world_state": {
            "season": "",
            "weather": "晴",
            "time_period": "",
            "last_tick_date": "",
            "last_event_gen_date": "",
            "last_interaction_date": "",
            "npc_registry": {},
            "factions": {},
            "economy": {},
        },
        "current_events": [],
        "history_events": [],
        "meta": {
            "version": 1,
            "created_at": now,
            "updated_at": now,
        },
    }


# ============================================================
# MemoryCenter 类
# ============================================================

class MemoryCenter:
    """
    角色的数据中心，统一管理所有动态数据。

    用法:
        mc = MemoryCenter()
        char = mc.load_current_character()
        mem = mc.load_memory(char["id"])
        mc.update_favorability(user_input, char["id"])
    """

    # ========== 记忆文件路径 ==========

    def _get_memory_path(self, character_id):
        return os.path.join(MEMORIES_DIR, f"{character_id}.json")

    # ========== 记忆读写 ==========

    def load_memory(self, character_id):
        """加载角色的完整记忆数据（JSON 小状态 + ChromaDB 大数据）"""
        path = self._get_memory_path(character_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = create_default_memory()

        # 一次性迁移：旧 JSON 中的大数据迁移到 ChromaDB
        self._migrate_to_chroma(character_id, data)

        # 从 ChromaDB 合并大数据字段
        data["long_memory"] = self.get_long_memories(character_id)
        data["events"] = self.get_events(character_id)
        data["chat_summary"] = self.get_chat_summary(character_id)

        return data

    def _migrate_to_chroma(self, character_id, data):
        """将旧 JSON 中的大数据一次性迁移到 ChromaDB"""
        from funcation import memory_rag

        # long_memory 迁移
        old_long = data.pop("long_memory", None)
        if old_long:
            existing = memory_rag.list_all_memories(character_id, "long_memory")
            existing_texts = {item["text"] for item in existing}
            for text in old_long:
                text_str = text.get("value", text) if isinstance(text, dict) else str(text)
                if text_str and text_str not in existing_texts:
                    memory_rag.add_memory(character_id, "long_memory", text_str)

        # events 迁移
        old_events = data.pop("events", None)
        if old_events:
            existing = memory_rag.list_all_memories(character_id, "events")
            existing_texts = {item["text"] for item in existing}
            for evt in old_events:
                event_text = evt.get("event", "") if isinstance(evt, dict) else str(evt)
                event_time = evt.get("time", "") if isinstance(evt, dict) else ""
                if event_text and event_text not in existing_texts:
                    memory_rag.add_memory(
                        character_id, "events", event_text,
                        metadata={"time": event_time},
                    )

        # chat_summary 迁移
        old_summary = data.pop("chat_summary", None)
        if old_summary:
            existing = memory_rag.list_all_memories(character_id, "chat_summary")
            existing_texts = {item["text"] for item in existing}
            for s in old_summary:
                text_str = str(s)
                if text_str and text_str not in existing_texts:
                    memory_rag.add_memory(character_id, "chat_summary", text_str)

    def save_memory(self, character_id, data):
        """保存角色的完整记忆数据（仅小状态入 JSON，大数据已在 ChromaDB）"""
        os.makedirs(MEMORIES_DIR, exist_ok=True)
        path = self._get_memory_path(character_id)
        # 创建副本，移除 ChromaDB 管理的大数据字段
        json_data = {k: v for k, v in data.items() if k not in _CHROMA_FIELDS}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

    # ========== 用户画像 ==========

    def get_profile(self, character_id):
        """获取角色的用户画像"""
        mem = self.load_memory(character_id)
        return mem.get("profile", {})

    def update_profile(self, user_input, character_id):
        """根据用户输入更新画像（AI agent 智能提取）"""
        from funcation import profile_agent

        mem = self.load_memory(character_id)
        profile = mem.setdefault("profile", {})

        # 用 AI agent 提取画像信息
        extracted = profile_agent.extract_profile(user_input, profile)

        # 合并提取结果
        if extracted:
            for key in ["name", "city", "job", "mood"]:
                if key in extracted and extracted[key]:
                    profile[key] = extracted[key]

        # 最近话题（保留旧逻辑，每次追加用户输入）
        profile.setdefault("recent_topics", [])
        profile["recent_topics"].append(user_input)
        profile["recent_topics"] = profile["recent_topics"][-5:]

        mem["profile"] = profile
        self.save_memory(character_id, mem)

    def get_caring_message(self, character_id):
        """根据画像生成关心消息（AI agent 智能生成）"""
        from funcation import profile_agent

        profile = self.get_profile(character_id)

        # 加载角色名
        try:
            character = self.load_character_by_id(character_id)
            character_name = character.get("name", "角色")
        except:
            character_name = "角色"

        return profile_agent.generate_caring_message(profile, character_name)

    # ========== 好感度 ==========

    def get_favorability(self, character_id):
        """获取角色的好感度"""
        mem = self.load_memory(character_id)
        return mem.get("favorability", 50)

    def update_favorability(self, user_input, character_id):
        """根据用户输入更新好感度（AI agent 智能分析）"""
        from funcation import relationship_agent

        result = relationship_agent.update_relationship(
            self,
            character_id,
            user_input
        )
        return result["favorability"]

    # ========== 长期记忆 ==========

    def get_long_memories(self, character_id):
        """获取长期记忆列表（从 ChromaDB）"""
        from funcation import memory_rag
        items = memory_rag.list_all_memories(character_id, "long_memory")
        return [item["text"] for item in items]

    def add_long_memory(self, character_id, memory_text):
        """添加一条长期记忆（自动去重，写入 ChromaDB）"""
        existing = self.get_long_memories(character_id)
        if memory_text in existing:
            return
        from funcation import memory_rag
        memory_rag.add_memory(character_id, "long_memory", memory_text)

    def update_long_memory(self, character_id, old_text, new_text):
        """更新一条长期记忆（在 ChromaDB 中）"""
        from funcation import memory_rag
        memory_rag.update_memory(character_id, "long_memory", old_text, new_text)

    def get_long_memories_text(self, character_id):
        """获取长期记忆的文本列表"""
        return self.get_long_memories(character_id)

    # ========== 事件 ==========

    def get_events(self, character_id):
        """获取事件列表（从 ChromaDB）"""
        from funcation import memory_rag
        items = memory_rag.list_all_memories(character_id, "events")
        result = []
        for item in items:
            meta = item.get("metadata", {})
            result.append({
                "time": meta.get("time", ""),
                "event": item["text"],
            })
        # 按时间排序
        result.sort(key=lambda x: x.get("time", ""))
        return result[-50:]  # 最多 50 条

    def add_event(self, character_id, event_text):
        """添加一个事件（写入 ChromaDB）"""
        from funcation import memory_rag
        event_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        memory_rag.add_memory(
            character_id, "events", event_text,
            metadata={"time": event_time},
        )

    # ========== 角色状态 ==========

    def get_character_state(self, character_id):
        """获取角色状态"""
        mem = self.load_memory(character_id)
        return mem.get("character_state", {})

    def update_character_state(self, character_id, state):
        """更新角色状态"""
        mem = self.load_memory(character_id)
        old_state = mem.get("character_state", {})
        old_mood = old_state.get("mood", "")
        new_mood = state.get("mood", "")

        # 心情变化标记
        if new_mood and new_mood != old_mood:
            state["mood_changed"] = True

        mem["character_state"] = state
        self.save_memory(character_id, mem)

    # ========== 聊天摘要 ==========

    def get_chat_summary(self, character_id):
        """获取聊天摘要列表（从 ChromaDB）"""
        from funcation import memory_rag
        items = memory_rag.list_all_memories(character_id, "chat_summary")
        return [item["text"] for item in items]

    def update_chat_summary(self, character_id, summaries):
        """替换聊天摘要（清空 ChromaDB 后重新写入）"""
        from funcation import memory_rag
        memory_rag.purge_collection(character_id, "chat_summary")
        for s in summaries:
            memory_rag.add_memory(character_id, "chat_summary", str(s))

    def add_chat_summary(self, character_id, summary):
        """追加一条聊天摘要（写入 ChromaDB，保留最近 10 条）"""
        from funcation import memory_rag
        memory_rag.add_memory(character_id, "chat_summary", str(summary))
        # 裁剪：超过 10 条时删除最旧的
        items = memory_rag.list_all_memories(character_id, "chat_summary")
        if len(items) > 10:
            # 删除最旧的 (id 最小的)
            items.sort(key=lambda x: x.get("id", ""))
            for item in items[:len(items) - 10]:
                memory_rag.delete_by_id(character_id, "chat_summary", item["id"])

    # ========== 最后聊天时间 ==========

    def update_last_chat_time(self, character_id):
        """更新最后聊天时间"""
        mem = self.load_memory(character_id)
        mem["last_chat_time"] = datetime.now().isoformat()
        self.save_memory(character_id, mem)

    def get_last_chat_time(self, character_id):
        """获取最后聊天时间"""
        mem = self.load_memory(character_id)
        return mem.get("last_chat_time")

    # ========== 角色管理 ==========

    def get_current_character_id(self):
        """获取当前选中的角色ID"""
        try:
            with open(CURRENT_CHARACTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data["character_id"]
        except:
            return "linwan"

    def set_current_character(self, character_id):
        """切换当前角色"""
        with open(CURRENT_CHARACTER_FILE, "w", encoding="utf-8") as f:
            json.dump({"character_id": character_id}, f, ensure_ascii=False, indent=2)

    def load_current_character(self):
        """加载当前角色的静态定义"""
        character_id = self.get_current_character_id()
        return self.load_character_by_id(character_id)

    def load_character_by_id(self, character_id):
        """根据ID加载角色静态定义"""
        path = os.path.join(CHARACTERS_DIR, f"{character_id}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            # 回退到旧的 characters/ 目录
            old_path = os.path.join("characters", f"{character_id}.json")
            with open(old_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def save_character(self, character):
        """保存角色静态定义"""
        os.makedirs(CHARACTERS_DIR, exist_ok=True)
        character_id = character["id"]
        path = os.path.join(CHARACTERS_DIR, f"{character_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(character, f, ensure_ascii=False, indent=2)

    def get_all_characters(self):
        """获取所有角色列表（简要信息）"""
        characters = []

        # 优先从 data/characters/ 读取
        search_dirs = [CHARACTERS_DIR, "characters"]
        seen_ids = set()

        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
            for file in os.listdir(search_dir):
                if file.endswith(".json"):
                    path = os.path.join(search_dir, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        char_id = data.get("id")
                        if char_id and char_id not in seen_ids:
                            seen_ids.add(char_id)
                            characters.append({
                                "id": char_id,
                                "name": data.get("name", char_id),
                                "description": data.get("description", ""),
                                "avatar": data.get("avatar", ""),
                            })
                    except:
                        pass

        return characters

    # ========== 世界管理 ==========

    def get_current_world_id(self):
        """获取当前选中的世界ID"""
        try:
            with open(CURRENT_WORLD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data["world_id"]
        except:
            return "campus"

    def set_current_world(self, world_id):
        """切换当前世界"""
        with open(CURRENT_WORLD_FILE, "w", encoding="utf-8") as f:
            json.dump({"world_id": world_id}, f, ensure_ascii=False, indent=2)

    def load_current_world(self):
        """加载当前世界的静态定义"""
        world_id = self.get_current_world_id()
        return self.load_world_by_id(world_id)

    def load_world_by_id(self, world_id):
        """根据ID加载世界定义"""
        # 优先从 data/worlds/ 读取
        for search_dir in [WORLDS_DIR, "worlds"]:
            path = os.path.join(search_dir, f"{world_id}.json")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                continue
        return None

    def get_all_worlds(self):
        """获取所有世界列表"""
        worlds = []
        seen_ids = set()

        for search_dir in [WORLDS_DIR, "worlds"]:
            if not os.path.exists(search_dir):
                continue
            for file in os.listdir(search_dir):
                if file.endswith(".json"):
                    path = os.path.join(search_dir, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        world_id = data.get("id")
                        if world_id and world_id not in seen_ids:
                            seen_ids.add(world_id)
                            worlds.append({
                                "id": world_id,
                                "name": data.get("name", world_id),
                                "description": data.get("description", "")
                            })
                    except:
                        pass

        return worlds

    # ========== 世界动态状态 (world_state/{world_id}.json) ==========

    def _get_world_state_path(self, world_id):
        return os.path.join(WORLD_STATE_DIR, f"{world_id}.json")

    def load_world_state(self, world_id=None):
        """加载世界的动态状态（事件、环境等）"""
        if world_id is None:
            world_id = self.get_current_world_id()

        path = self._get_world_state_path(world_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            default = create_default_world_state(world_id)
            self.save_world_state(world_id, default)
            return default

    def save_world_state(self, world_id, data):
        """保存世界动态状态"""
        os.makedirs(WORLD_STATE_DIR, exist_ok=True)
        data["world_id"] = world_id
        data.setdefault("meta", {})
        data["meta"]["updated_at"] = datetime.now().isoformat()
        path = self._get_world_state_path(world_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_current_events(self, world_id=None):
        """获取当前进行中的世界事件"""
        world_data = self.load_world_state(world_id)
        return world_data.get("current_events", [])

    def get_history_events(self, world_id=None):
        """获取已结束的世界历史事件"""
        world_data = self.load_world_state(world_id)
        return world_data.get("history_events", [])

    def get_world_runtime_state(self, world_id=None):
        """获取世界运行时环境（季节、天气、时间段）"""
        world_data = self.load_world_state(world_id)
        return world_data.get("world_state", {})

    # ========== NPC 社交网络 (world_state.npc_registry) ==========

    def ensure_npc_registry(self, world_data):
        """确保 npc_registry 结构完整"""
        runtime = world_data.setdefault("world_state", {})
        registry = runtime.setdefault("npc_registry", {})
        registry.setdefault("relationships", {})
        registry.setdefault("recent_interactions", [])
        registry.setdefault("gossip", [])
        registry.setdefault("world_impacts", [])
        return registry

    def get_npc_relationships(self, world_id=None):
        """获取角色间关系矩阵"""
        world_data = self.load_world_state(world_id)
        registry = self.ensure_npc_registry(world_data)
        return registry.get("relationships", {})

    def get_npc_relationship(self, world_id, from_id, to_id):
        """获取两个角色之间的关系，不存在时返回默认值"""
        relationships = self.get_npc_relationships(world_id)
        default = {"favorability": 50, "trust": 50, "intimacy": 30}
        return relationships.get(from_id, {}).get(to_id, default)

    def update_npc_relationship(self, world_id, from_id, to_id, deltas):
        """手动更新角色间关系 delta"""
        world_data = self.load_world_state(world_id)
        registry = self.ensure_npc_registry(world_data)
        rel = registry["relationships"].setdefault(from_id, {}).setdefault(
            to_id,
            {"favorability": 50, "trust": 50, "intimacy": 30},
        )
        for key in ("favorability", "trust", "intimacy"):
            if key in deltas:
                rel[key] = max(0, min(100, rel.get(key, 50) + int(deltas[key])))
        world_data["world_state"]["npc_registry"] = registry
        self.save_world_state(world_id, world_data)
        return rel

    # ========== 主动消息 ==========

    def get_proactive_message(self, character_id):
        """
        根据状态变化标记生成主动消息。
        优先检查 story/relationship/mood 变更标记，
        有变更时用 proactive_agent 生成上下文相关消息并清除标记；
        无变更时回退到基于好感度和时间的随机消息。
        """
        mem = self.load_memory(character_id)

        # ── 检查变更标记（世界事件优先） ──
        world_notice = mem.get("world_event_notice", {})
        story = mem.get("story", {})
        rel = mem.get("relationship", {})
        state = mem.get("character_state", {})

        world_event_changed = world_notice.get("changed", False)
        story_changed = story.get("changed", False)
        level_changed = rel.get("level_changed", False)
        mood_changed = state.get("mood_changed", False)

        has_change = (
            world_event_changed
            or story_changed
            or level_changed
            or mood_changed
        )

        if has_change:
            from funcation import proactive_agent

            # 加载角色信息
            try:
                character = self.load_character_by_id(character_id)
                char_name = character.get("name", "角色")
                char_personality = character.get("personality", "")
            except:
                char_name = "角色"
                char_personality = ""

            # 提取剧情上下文
            story_title = story.get("title", "")
            stages = story.get("stages", [])
            stage_idx = story.get("stage", 0)
            current_stage = stages[stage_idx] if 0 <= stage_idx < len(stages) else ""

            msg = proactive_agent.generate_proactive_message(
                character_name=char_name,
                character_personality=char_personality,
                world_event_changed=world_event_changed,
                world_event_type=world_notice.get("type", ""),
                world_event_title=world_notice.get("title", ""),
                world_event_description=world_notice.get("description", ""),
                world_event_progress=world_notice.get("progress", 0),
                story_changed=story_changed,
                story_title=story_title,
                current_stage_text=current_stage,
                level_changed=level_changed,
                new_level=rel.get("level", ""),
                level_reason=rel.get("last_reason", ""),
                mood_changed=mood_changed,
                new_mood=state.get("mood", ""),
            )

            # 清除已消费的标记
            changed = False
            if world_event_changed:
                world_notice.pop("changed", None)
                mem["world_event_notice"] = world_notice
                changed = True
            if story_changed:
                story.pop("changed", None)
                mem["story"] = story
                changed = True
            if level_changed:
                rel.pop("level_changed", None)
                mem["relationship"] = rel
                changed = True
            if mood_changed:
                state.pop("mood_changed", None)
                mem["character_state"] = state
                changed = True

            if changed:
                self.save_memory(character_id, mem)

            if msg:
                return msg

        # ── 回退：基于好感度和时间的随机消息 ──
        favorability = mem.get("favorability", 50)
        last_time = mem.get("last_chat_time")

        minutes = 0
        if last_time:
            try:
                last = datetime.fromisoformat(last_time)
                diff = datetime.now() - last
                minutes = diff.total_seconds() / 60
            except:
                pass

        low_messages = [
            "哦，又来了。",
            "今天居然还在。",
            "……有事？",
        ]

        normal_messages = [
            "你来了。",
            "今天怎么样？",
            "在忙吗？",
        ]

        high_messages = [
            "终于来了。",
            "我刚刚还在想你。",
            "今天过得怎么样？",
            "怎么现在才来。",
        ]

        if minutes > 30:
            return "……你终于想起我了？"

        if favorability < 30:
            return random.choice(low_messages)
        elif favorability < 70:
            return random.choice(normal_messages)
        else:
            return random.choice(high_messages)

# ========== 角色状态 ==========

def get_character_state(self, character_id):
    mem = self.load_memory(character_id)

    return mem.get(
        "character_state",
        {
            "mood": "开心",
            "energy": 80,
            "current_event": "",
            "last_active_time": ""
        }
    )


def save_character_state(
        self,
        character_id,
        state
):
    mem = self.load_memory(character_id)

    mem["character_state"] = state

    self.save_memory(
        character_id,
        mem
    )


def update_mood(
        self,
        character_id,
        mood
):
    state = self.get_character_state(
        character_id
    )

    state["mood"] = mood

    self.save_character_state(
        character_id,
        state
    )


def update_energy(
        self,
        character_id,
        energy
):
    state = self.get_character_state(
        character_id
    )

    state["energy"] = max(
        0,
        min(100, energy)
    )

    self.save_character_state(
        character_id,
        state
    )


def set_current_event(
        self,
        character_id,
        title,
        description=""
):
    state = self.get_character_state(
        character_id
    )

    state["current_event"] = {

        "title": title,

        "description": description,

        "start_time": datetime.now().isoformat()
    }

    self.save_character_state(
        character_id,
        state
    )

def update_character_state(
        self,
        character_id,
        new_state
):

    mem = self.load_memory(
        character_id
    )

    state = mem.get(
        "character_state",
        {}
    )

    state.update(
        new_state
    )

    mem["character_state"] = state

    self.save_memory(
        character_id,
        mem
    )
