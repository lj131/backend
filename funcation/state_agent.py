import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def analyze_state(
        user_input,
        current_state,
        world
):

    prompt = f"""
你是状态分析器。

任务：

根据用户输入，

判断角色当前应该处于什么状态。

返回JSON。

当前状态：

{json.dumps(current_state, ensure_ascii=False)}

当前世界：

{json.dumps(world, ensure_ascii=False)}

当前事件：

{current_state["current_event"]}

世界：

{world}

用户消息：

{user_input}

输出格式：

{{
    "mood":"开心",
    "energy":80,
    "current_event":""
}}

规则：

mood只能是：

- 开心
- 平静
- 低落
- 生气
- 疲惫

energy范围：

0~100

只返回JSON。
"""

    try:

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        result = response.choices[0].message.content.strip()

        result = result.replace(
            "```json",
            ""
        )

        result = result.replace(
            "```",
            ""
        )

        return json.loads(result)

    except Exception as e:

        print("StateAgent异常:", e)

        return current_state