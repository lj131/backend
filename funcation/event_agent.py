import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
def generate_daily_event(
        character,
        world
):

    prompt = f"""
你是角色生活规划师。

角色：

名字：
{character["name"]}

性格：
{character["personality"]}

角色设定：
{character["description"]}

世界：

{world["name"]}

背景：

{world["background"]}

请生成今天角色正在经历的事情。

返回JSON：

{{
    "title":"",
    "description":"",
    "impact":0
}}

规则：

impact范围：

-50 到 50

只返回JSON。
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=1
    )

    content = (
        response
        .choices[0]
        .message
        .content
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(content)



from datetime import datetime


def check_daily_event(
        memory_center,
        character,
        world
):

    character_id = character["id"]

    memory_data = (
        memory_center.load_memory(
            character_id
        )
    )

    state = memory_data.get(
        "character_state",
        {}
    )

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    event_date = state.get(
        "event_date",
        ""
    )

    if event_date == today:
        return

    event = generate_daily_event(
        character,
        world
    )

    state["current_event"] = event

    state["event_date"] = today

    memory_data["character_state"] = state

    memory_center.save_memory(
        character_id,
        memory_data
    )