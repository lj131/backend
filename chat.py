import json

from openai import OpenAI

from dotenv import load_dotenv

import os

load_dotenv()

# DeepSeek客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 角色设定
def build_system_prompt(favorability):

    attitude = ""

    if favorability < 20:

        attitude = """
你对用户比较冷淡。

说话简短。

不主动关心。
"""

    elif favorability < 50:

        attitude = """
你对用户态度普通。

偶尔会回应。

但不会太热情。
"""

    elif favorability < 80:

        attitude = """
你开始对用户有好感。

会主动关心。

语气明显柔和。
"""

    else:

        attitude = """
你非常喜欢用户。

会明显表现亲近感。

偶尔会撒娇。

会在意用户情绪。
"""

    return f"""
你叫林晚。

你是一个温柔可爱爱撒娇得女生。

{attitude}

禁止：

- AI口吻
- 官方回答
- 机械感
"""

# memory文件
MEMORY_FILE = "memory.json"

#好感度 文件
CHARACTER_FILE = "character.json"

# 读取角色状态
def load_character():

    try:

        with open(CHARACTER_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return {
            "favorability": 50
        }

# 保存角色状态
def save_character(data):

    with open(CHARACTER_FILE, "w", encoding="utf-8") as f:

        json.dump(data, f, ensure_ascii=False, indent=2)

# 读取历史聊天
def load_memory():

    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return []


# 保存历史聊天
def save_memory(messages):

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:

        json.dump(messages, f, ensure_ascii=False, indent=2)


# 加载历史
messages = load_memory()

# 加载角色好感度
character = load_character()

# 如果第一次启动
if not messages:

    messages = []

system_prompt = build_system_prompt(
    character["favorability"]
)

messages.insert(0, {
    "role": "system",
    "content": system_prompt
})

while True:

    user_input = input("\n你：")

    # 好感度变化（简单规则）
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

    # 限制范围
    character["favorability"] = max(
        0,
        min(100, character["favorability"])
    )

    # 保存状态
    save_character(character)

    if user_input == "exit":
        break

    # 添加用户消息
    messages.append({
        "role": "user",
        "content": user_input
    })

    # 调用模型
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.9
    )

    ai_reply = response.choices[0].message.content

    print(f"\n林晚：{ai_reply}")

    # 保存AI回复
    messages.append({
        "role": "assistant",
        "content": ai_reply
    })

    # memory管理
    MAX_MEMORY = 2000

    system_message = messages[0]

    recent_messages = messages[-MAX_MEMORY:]

    messages = [system_message] + recent_messages

    # 保存memory
    save_memory(messages)