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
MEMORIES_DIR = os.path.join(DATA_DIR, "memories")

CURRENT_CHARACTER_FILE = "current_character.json"
CURRENT_WORLD_FILE = "current_world.json"


# ============================================================
# 默认记忆工厂
# ============================================================

def create_default_memory():
    """创建一个角色的默认记忆结构"""
    return {
        "profile": {
            "name": "",
            "city": "",
            "job": "",
            "mood": "",
            "recent_topics": []
        },
        "favorability": 50,
        "long_memory": [],
        "events": [],
        "chat_summary": [],
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
        """加载角色的完整记忆数据"""
        path = self._get_memory_path(character_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return create_default_memory()

    def save_memory(self, character_id, data):
        """保存角色的完整记忆数据"""
        os.makedirs(MEMORIES_DIR, exist_ok=True)
        path = self._get_memory_path(character_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
        """获取长期记忆列表"""
        mem = self.load_memory(character_id)
        return mem.get("long_memory", [])

    def add_long_memory(self, character_id, memory_text):
        """添加一条长期记忆（自动去重）"""
        mem = self.load_memory(character_id)
        memories = mem.setdefault("long_memory", [])

        if memory_text not in memories:
            memories.append(memory_text)

        mem["long_memory"] = memories
        self.save_memory(character_id, mem)

    def update_long_memory(self, character_id, old_text, new_text):
        """更新一条长期记忆"""
        mem = self.load_memory(character_id)
        memories = mem.get("long_memory", [])

        for i, m in enumerate(memories):
            if m == old_text:
                memories[i] = new_text
                break

        mem["long_memory"] = memories
        self.save_memory(character_id, mem)

    def get_long_memories_text(self, character_id):
        """获取长期记忆的文本列表（兼容旧格式）"""
        memories = self.get_long_memories(character_id)
        # 兼容两种格式：纯字符串列表 和 [{type, value}] 列表
        result = []
        for m in memories:
            if isinstance(m, str):
                result.append(m)
            elif isinstance(m, dict):
                result.append(m.get("value", str(m)))
        return result

    # ========== 事件 ==========

    def get_events(self, character_id):
        """获取事件列表"""
        mem = self.load_memory(character_id)
        return mem.get("events", [])

    def add_event(self, character_id, event_text):
        """添加一个事件（带时间戳）"""
        mem = self.load_memory(character_id)
        events = mem.setdefault("events", [])

        events.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "event": event_text
        })

        # 只保留最近 50 条事件
        mem["events"] = events[-50:]
        self.save_memory(character_id, mem)

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
        """获取聊天摘要列表"""
        mem = self.load_memory(character_id)
        return mem.get("chat_summary", [])

    def update_chat_summary(self, character_id, summaries):
        """替换聊天摘要"""
        mem = self.load_memory(character_id)
        mem["chat_summary"] = summaries
        self.save_memory(character_id, mem)

    def add_chat_summary(self, character_id, summary):
        """追加一条聊天摘要"""
        mem = self.load_memory(character_id)
        summaries = mem.setdefault("chat_summary", [])
        summaries.append(summary)
        # 只保留最近 10 条摘要
        mem["chat_summary"] = summaries[-10:]
        self.save_memory(character_id, mem)

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
                                "description": data.get("description", "")
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

    # ========== 主动消息 ==========

    def get_proactive_message(self, character_id):
        """
        根据状态变化标记生成主动消息。
        优先检查 story/relationship/mood 变更标记，
        有变更时用 proactive_agent 生成上下文相关消息并清除标记；
        无变更时回退到基于好感度和时间的随机消息。
        """
        mem = self.load_memory(character_id)

        # ── 检查变更标记 ──
        story = mem.get("story", {})
        rel = mem.get("relationship", {})
        state = mem.get("character_state", {})

        story_changed = story.get("changed", False)
        level_changed = rel.get("level_changed", False)
        mood_changed = state.get("mood_changed", False)

        has_change = story_changed or level_changed or mood_changed

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
