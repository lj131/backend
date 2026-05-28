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
SYSTEM_PROMPT = """
你叫林晚。

你是一个高冷、聪明、嘴硬的女生。

你的特点：

- 不喜欢废话
- 偶尔毒舌
- 会默默关心用户
- 不会长篇大论
- 说话自然
- 像真实人类

禁止：

- AI口吻
- 助手口吻
- 官方回答
- “作为AI”
- “我不能”
"""

# memory文件
MEMORY_FILE = "memory.json"


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

# 如果第一次启动
if not messages:

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

while True:

    user_input = input("\n你：")

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