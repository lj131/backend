from fastapi import FastAPI
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

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

class ChatRequest(BaseModel):
    message: str

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