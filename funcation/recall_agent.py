"""
Memory Recall Agent — 由 LLM 决定应该检索哪些记忆集合

替代关键词分类器 query_classifier.py。
输入用户消息，返回需要检索的 ChromaDB 集合列表。

特性:
- LLM 语义理解，覆盖所有表达方式
- 5 分钟缓存（同一消息不重复调用大模型）
- 异常时自动回退到默认集合，保证系统可用
"""

import hashlib
import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ============================================================
# 可选集合
# ============================================================

ALL_COLLECTIONS = [
    "profile",
    "relationship",
    "story",
    "events",
    "long_memory",
    "chat_summary",
]

# 异常时的默认回退集合
FALLBACK_COLLECTIONS = ["profile", "relationship", "story"]

# ============================================================
# 缓存
# ============================================================

_cache: dict[str, tuple[list[str], float]] = {}
CACHE_TTL = 300  # 5 分钟


def _cache_key(user_input: str, character_id: str = "") -> str:
    """生成缓存键"""
    raw = f"{character_id}:{user_input.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def clear_cache():
    """清除所有缓存"""
    global _cache
    _cache = {}


# ============================================================
# 核心函数
# ============================================================


def detect_memory_scope(
    user_input: str,
    character_id: str = "",
    use_cache: bool = True,
) -> list[str]:
    """
    由 LLM 判断当前消息需要检索哪些记忆集合。

    参数:
        user_input: 用户消息
        character_id: 角色 ID（用于缓存隔离）
        use_cache: 是否使用缓存

    返回:
        集合名称列表，例如 ["profile", "relationship"]
    """
    # ── 缓存检查 ──
    key = _cache_key(user_input, character_id)
    if use_cache and key in _cache:
        collections, timestamp = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return collections

    # ── LLM 调用 ──
    try:
        result = _call_llm(user_input)
    except Exception as e:
        print(f"[recall_agent] LLM 调用失败，回退到默认集合: {e}")
        result = None

    # ── 解析结果 ──
    if result and "collections" in result:
        collections = [
            c for c in result["collections"]
            if c in ALL_COLLECTIONS
        ]
        if collections:
            # 写入缓存
            if use_cache:
                _cache[key] = (collections, time.time())
            print(f"[recall_agent] 检测到集合: {collections} (原因: {result.get('reason', '')})")
            return collections

    # ── 回退 ──
    print("[recall_agent] 回退到默认集合")
    return FALLBACK_COLLECTIONS


# ============================================================
# LLM 调用
# ============================================================


def _call_llm(user_input: str) -> dict | None:
    """调用 DeepSeek 判断需要检索的集合"""

    collection_list = "\n".join(f"- {c}" for c in ALL_COLLECTIONS)

    prompt = f"""你是记忆检索规划器。

用户消息：
"{user_input}"

可用的记忆集合（只能从以下选择）：
{collection_list}

集合说明：
- profile: 用户个人信息（姓名、城市、职业、情绪等）
- relationship: 角色与用户的关系状态（好感度、关系等级、关系变化原因）
- story: 剧情记录（对话中发生的故事情节、过去经历）
- events: 事件记录（特定时间发生的事情，如考试、运动会、约会等）
- long_memory: 长期记忆（用户说过的事实，如爱好、经历、偏好）
- chat_summary: 聊天摘要（历史对话的摘要总结）

请判断：用户的这条消息，需要从哪些集合中检索相关记忆？

返回 JSON：
{{"collections": ["集合1", "集合2", ...], "reason": "简要说明为什么选择这些集合（不超过20字）"}}

规则：
1. 只返回真正相关的集合，不要全部返回
2. 如果用户询问个人信息/身份 → profile
3. 如果用户询问关系/感情 → relationship
4. 如果用户提及过去发生的事/剧情 → story
5. 如果用户询问特定时间的事/活动 → events
6. 如果用户询问偏好/习惯/事实 → long_memory
7. 如果用户要求回顾对话历史 → chat_summary
8. 普通闲聊可能只需要 story + long_memory
9. 最少返回 2 个，最多返回 4 个集合
10. 只返回 JSON，不要任何其他内容"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你是记忆检索规划器。只返回 JSON，不要任何其他文字。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=200,
    )

    content = response.choices[0].message.content.strip()
    return json.loads(content)
