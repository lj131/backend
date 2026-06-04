"""
主动消息 Agent

当角色状态发生变化（剧情推进、关系升级、心情变化）时，
用 DeepSeek 生成上下文相关的自然主动消息。
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

MOOD_MAP = {
    "开心": "心情变得很好",
    "低落": "心情有点低落",
    "生气": "有点不开心",
    "疲惫": "感到有些疲惫",
    "平静": "心情恢复了平静",
}


def generate_proactive_message(
    character_name,
    character_personality,
    story_changed=False,
    story_title="",
    current_stage_text="",
    level_changed=False,
    new_level="",
    level_reason="",
    mood_changed=False,
    new_mood="",
):
    """
    根据状态变更生成主动消息。

    参数:
        character_name: 角色名
        character_personality: 角色性格
        story_changed: 剧情是否推进
        story_title: 剧情标题
        current_stage_text: 当前阶段文本
        level_changed: 关系是否升级
        new_level: 新关系等级
        level_reason: 关系变化原因
        mood_changed: 心情是否变化
        new_mood: 新心情

    返回:
        str | None: 生成的消息，失败时返回 None
    """

    change_descriptions = []

    if story_changed:
        change_descriptions.append(
            f"📖 剧情推进：「{story_title}」→ 当前阶段：{current_stage_text}"
        )

    if level_changed:
        desc = f"💕 关系升级：现在的关系是「{new_level}」"
        if level_reason:
            desc += f"（{level_reason}）"
        change_descriptions.append(desc)

    if mood_changed:
        mood_desc = MOOD_MAP.get(new_mood, f"心情变成了「{new_mood}」")
        change_descriptions.append(f"😊 心情变化：{mood_desc}")

    change_text = "\n".join(change_descriptions)

    prompt = f"""你是{character_name}，一个{character_personality}的角色。

就在刚才，发生了一些变化：

{change_text}

请以{character_name}的口吻，主动对用户说一句话。

规则：
1. 保持角色性格和说话风格
2. 自然、不做作，像真人一样
3. 间接提及变化，不要直接说"剧情推进了"或"关系升级了"
4. 简短，控制在1-3句话
5. 只返回这句话本身，不要加引号、前缀或解释

{character_name}说："""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": f"你是{character_name}，性格{character_personality}。只说一句话，不要加引号。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=120,
        )

        result = response.choices[0].message.content.strip()
        result = result.strip('"').strip("'").strip("「").strip("」")
        return result if result else None

    except Exception as e:
        print(f"[proactive_agent] 生成主动消息失败: {e}")
        return None
