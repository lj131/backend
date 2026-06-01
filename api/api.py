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
    mc.update_favorability(user_input, char_id)

    new_state = (
        state_agent.analyze_state(
            user_input,
            current_state
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
