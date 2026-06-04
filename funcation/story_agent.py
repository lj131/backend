import json
import os
import uuid

from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def generate_story(
        character,
        world
):

    prompt = f"""
你是剧情设计师。

角色：

名字：
{character["name"]}

性格：
{character["personality"]}

设定：
{character["description"]}

世界：

{world["name"]}

背景：

{world["background"]}

请生成一个连续剧情。

返回JSON：

{{
    "title":"",
    "description":"",
    "stages":[
        "",
        "",
        "",
        "",
        ""
    ]
}}

要求：

1 至少5个阶段

2 阶段具有连续性

3 符合角色性格

4 符合世界观

只返回JSON
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

    # 清理可能导致 JSON 解析失败的控制字符
    import re
    content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print(f"[story_agent] JSON 解析失败，原始内容: {content[:200]}")
        return None

    return {
        "story_id": str(uuid.uuid4()),
        "title": data["title"],
        "description": data["description"],
        "stage": 0,
        "max_stage": len(data["stages"]) - 1,
        "stages": data["stages"]
    }



def get_current_stage(story):

    stages = story.get(
        "stages",
        []
    )

    stage = story.get(
        "stage",
        0
    )

    if not stages:
        return ""

    if stage >= len(stages):
        stage = len(stages) - 1

    return stages[stage]



def advance_story(
        memory_data
):

    story = memory_data.get(
        "story",
        {}
    )

    if not story:
        return memory_data

    current = story.get(
        "stage",
        0
    )

    max_stage = story.get(
        "max_stage",
        0
    )

    if current < max_stage:

        story["stage"] += 1

    memory_data["story"] = story

    return memory_data



def is_story_finished(
        story
):

    return (
        story.get("stage", 0)
        >=
        story.get("max_stage", 0)
    )



def check_story(
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

    story = memory_data.get(
        "story",
        {}
    )

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    last_date = story.get(
        "last_update_date",
        ""
    )

    # 今天已经处理过

    if today == last_date:
        return

    # 没剧情

    if not story or not story.get(
            "story_id"
    ):

        story = generate_story(
            character,
            world
        )

        if story is None:
            return  # 生成失败，跳过

    else:

        # 推进剧情

        if is_story_finished(
                story
        ):

            new_story = generate_story(
                character,
                world
            )
            if new_story:
                story = new_story

        else:

            story["stage"] += 1

    story["last_update_date"] = today

    memory_data["story"] = story

    memory_center.save_memory(
        character_id,
        memory_data
    )


def sync_story_to_state(
        memory_data
):

    story = memory_data.get(
        "story",
        {}
    )

    state = memory_data.get(
        "character_state",
        {}
    )

    current_stage = (
        get_current_stage(
            story
        )
    )

    if current_stage:  # 只有有剧情时才更新
        state["current_event"] = {
            "title": current_stage,
            "description": story.get(
                "description",
                ""
            ),
            "impact": 0
        }

    memory_data[
        "character_state"
    ] = state

    return memory_data