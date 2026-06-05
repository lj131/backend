import os

from dotenv import load_dotenv

from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv(
        "DEEPSEEK_API_KEY"
    ),
    base_url="https://api.deepseek.com"
)


def generate_message(

        trigger,

        character,

        world,

        memory_data

):
    state = memory_data.get(
        "character_state",
        {}
    )

    profile = memory_data.get(
        "profile",
        {}
    )

    story = memory_data.get(
        "story",
        {}
    )

    relationship = memory_data.get(
        "relationship",
        {}
    )

    world_event_context = ""
    if trigger.get("trigger") == "world_event":
        we = trigger.get("world_event", {})
        world_event_context = f"""
世界事件：{we.get("title", "")}
描述：{we.get("description", "")}
状态：{we.get("type", "")}（进度 {we.get("progress", 0)}%）
"""

    prompt = f"""
你正在主动联系用户。

角色：

{character.get("name")}

角色设定：

{character.get("description")}

当前世界：

{world.get("name","")}

当前剧情：

{story}

当前状态：

{state}

关系：

{relationship}

用户画像：

{profile}

触发原因：

{trigger["reason"]}
{world_event_context}

要求：

1 像真人

2 不超过3句话

3 不打招呼

4 不要说在吗

5 不像客服

直接输出内容
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

    return response.choices[
        0
    ].message.content