from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from funcation import memory, prompt
from funcation import positive
from funcation import userfile
from funcation import utils

load_dotenv()

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该指定具体的域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

class ChatRequest(BaseModel):
    message: str

class CharacterNameRequest(BaseModel):
    name: str

# 聊天接口
@app.post("/chat")
def chat(req: ChatRequest):

    user_input = req.message

    messages = memory.load_memory()

    character = positive.load_character()

    profile = userfile.load_profile()

    if not messages:
        messages = []

    system_prompt = prompt.build_system_prompt(
        character["favorability"]
    )

    if not messages or messages[0]["role"] != "system":

        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })

    # 更新用户画像
    userfile.update_profile(user_input, profile)

    # 好感度系统
    positive_words = [
        "喜欢",
        "爱你",
        "谢谢",
        "可爱",
        "陪我",
        "想你"
    ]

    negative_words = [
        "讨厌",
        "滚",
        "烦",
        "傻",
        "闭嘴"
    ]

    for word in positive_words:

        if word in user_input:
            character["favorability"] += 5

    for word in negative_words:

        if word in user_input:
            character["favorability"] -= 5

    character["favorability"] = max(
        0,
        min(100, character["favorability"])
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

    character["last_chat_time"] = datetime.now().isoformat()

    positive.save_character(character)

    memory.save_memory(messages)

    return {
        "reply": ai_reply,
        "favorability": character["favorability"]
    }

# 获取好感度
@app.get("/favorability")
def favorability():
    character = positive.load_character()
    return {
        "favorability": character["favorability"]
    }

# 获取用户画像
@app.get("/profile")
def profile():
    profile = userfile.load_profile()
    return {
        "profile": profile
    }



# 保存用户画像
@app.post("/profile")
def save_profile(req: ChatRequest):
    userfile.save_profile(req.message)
    return {
        "message": "保存成功"
    }

#获取历史记录
@app.get("/history")
def history():
    messages = memory.load_memory()

    return {
        "messages": messages[-10:]   # 取最后10条
    }

# 获取记忆
@app.get("/memory")
def get_memory():
    messages = memory.load_memory()
    # 只提取用户消息
    user_messages = [
        msg["content"] for msg in messages
        if msg["role"] == "user"
    ]
    return {
        "memory": user_messages
    }

# 清空记忆
@app.post("/clear-memory")
def clear_memory():
    memory.save_memory([])
    return {}

# 获取历史消息
@app.get("/messages")
def messages():
    messages = memory.load_memory()
    return {
        "messages": messages
    }

# 设置角色名字
@app.post("/character/name")
def set_character_name(req: CharacterNameRequest):
    character = positive.load_character()
    character["name"] = req.name
    positive.save_character(character)
    return {
        "message": f"角色名字已设置为：{req.name}"
    }

# 获取角色名字
@app.get("/character/name")
def get_character_name():
    character = positive.load_character()
    return {
        "name": character.get("name", "林晚")
    }
