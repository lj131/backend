"""
用户画像 Agent

使用 DeepSeek 智能提取用户画像信息并生成关心消息。
替代旧的关键词匹配方式。
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise ValueError("DEEPSEEK_API_KEY 未配置")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)


def extract_profile(user_input, current_profile):
    """
    从用户发言中智能提取画像信息。

    参数:
        user_input: 用户最新发言
        current_profile: 当前画像 dict

    返回:
        dict: 提取到的画像字段（只返回需要更新的字段）
    """

    prompt = f"""
你是用户画像提取器。

当前画像：
{json.dumps(current_profile, ensure_ascii=False, indent=2)}

请分析用户最新发言，提取以下信息：

- name: 用户的名字/称呼
- city: 所在城市
- job: 职业/身份
- mood: 当前情绪（开心、难过、疲惫、焦虑、平静、兴奋、无聊等）

规则：
1. 只提取用户发言中明确提到的信息
2. 不要猜测没有提到的内容
3. 如果用户说了和现有画像矛盾的信息，用新的替换
4. 如果某项没有新信息，不要包含该字段

返回纯 JSON（只包含有变化的字段）：
{{
  "name": "...",
  "city": "...",
  "job": "...",
  "mood": "..."
}}

用户发言：
{user_input}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "你是用户画像提取器。返回纯JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # 低温度，提高提取准确性
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except Exception as e:
        print(f"[profile_agent] extract_profile 失败: {e}")
        return {}


def generate_caring_message(profile, character_name="角色"):
    """
    根据用户画像生成自然的关心消息。

    参数:
        profile: 用户画像 dict
        character_name: 角色名字

    返回:
        str: 关心消息，如果画像信息不足则返回 None
    """

    # 如果画像几乎没有信息，不生成
    has_info = any([
        profile.get("name"),
        profile.get("city"),
        profile.get("job"),
        profile.get("mood")
    ])
    if not has_info:
        return None

    prompt = f"""
你是{character_name}，一个关心用户的角色。

用户当前画像：
{json.dumps(profile, ensure_ascii=False, indent=2)}

请根据画像信息，生成一句自然的关心/问候语。

规则：
1. 保持{character_name}的角色身份
2. 语气自然，像真实的朋友聊天
3. 只提画像中有的信息，不要编造
4. 简短，不超过30个字
5. 只返回这句话本身，不要加引号

关心语：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"你是{character_name}。生成一句自然的关心语。不要加引号。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,
            max_tokens=100
        )

        result = response.choices[0].message.content.strip()
        # 清理可能的引号
        result = result.strip('"').strip("'").strip("「").strip("」")
        return result if result else None

    except Exception as e:
        print(f"[profile_agent] generate_caring_message 失败: {e}")
        return None
