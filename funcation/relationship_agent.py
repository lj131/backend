import json
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def get_relationship_level(
        favorability
):
    """
    根据好感度计算关系等级
    """

    if favorability < 20:
        return "陌生"

    elif favorability < 40:
        return "普通"

    elif favorability < 60:
        return "朋友"

    elif favorability < 80:
        return "亲近"

    else:
        return "暧昧"


def analyze_relationship(
        user_input,
        favorability
):
    """
    AI分析关系变化
    """

    prompt = f"""
你是关系分析器。

当前好感度：

{favorability}

用户说：

{user_input}

请判断：

用户这句话会让角色好感度变化多少。

返回JSON：

{{
    "delta":0,
    "reason":""
}}

规则：

1 只返回JSON

2 delta范围：

-10 到 10

3 感谢、关心、赞美：

增加

4 攻击、辱骂：

减少

5 普通聊天：

0
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

        result = response.choices[0].message.content

        result = result.replace(
            "```json",
            ""
        ).replace(
            "```",
            ""
        ).strip()

        return json.loads(result)

    except Exception as e:

        print("RelationshipAgent错误:", e)

        return {
            "delta": 0,
            "reason": "分析失败"
        }


def update_relationship(
        mc,
        character_id,
        user_input
):
    """
    更新关系
    """

    memory_data = mc.load_memory(
        character_id
    )

    favorability = memory_data.get(
        "favorability",
        50
    )

    old_level = get_relationship_level(
        favorability
    )

    result = analyze_relationship(
        user_input,
        favorability
    )

    delta = result.get(
        "delta",
        0
    )

    reason = result.get(
        "reason",
        ""
    )

    favorability += delta

    favorability = max(
        0,
        min(
            100,
            favorability
        )
    )

    new_level = get_relationship_level(
        favorability
    )

    memory_data[
        "favorability"
    ] = favorability

    memory_data[
        "relationship"
    ] = {

        "level": new_level,

        "last_reason": reason
    }

    # 关系升级事件
    if old_level != new_level:

        memory_data["relationship"]["level_changed"] = True

        memory_data.setdefault(
            "events",
            []
        )

        memory_data["events"].append({

            "event":
                f"关系从{old_level}变成{new_level}",

            "time":
                str(__import__("datetime")
                    .datetime.now())
        })

    mc.save_memory(
        character_id,
        memory_data
    )

    return {
        "favorability": favorability,
        "level": new_level,
        "reason": reason
    }