# funcation/query_classifier.py

QUERY_TYPE_WEIGHTS = {

    "profile": {
        "profile": 0.3,
        "relationship": 0.7,
        "long_memory": 0.8,
        "story": 1.2,
        "events": 1.3,
        "chat_summary": 1.4
    },

    "relationship": {
        "relationship": 0.3,
        "profile": 0.6,
        "long_memory": 0.8,
        "story": 1.0,
        "events": 1.2,
        "chat_summary": 1.3
    },

    "story": {
        "story": 0.3,
        "relationship": 0.6,
        "profile": 0.8,
        "long_memory": 0.9,
        "events": 1.0,
        "chat_summary": 1.2
    },

    "event": {
        "events": 0.3,
        "story": 0.5,
        "relationship": 0.8,
        "profile": 1.0,
        "long_memory": 1.0,
        "chat_summary": 1.2
    }
}


def classify_query(text: str):

    text = text.lower()

    profile_keywords = [
        "我是谁",
        "记得我",
        "我的名字",
        "我的工作",
        "我在哪",
        "我住哪",
        "个人信息"
    ]

    relationship_keywords = [
        "喜欢我",
        "爱我",
        "关系",
        "好感",
        "想我",
        "在意我"
    ]

    story_keywords = [
        "之前",
        "那次",
        "剧情",
        "发生过",
        "记不记得"
    ]

    event_keywords = [
        "活动",
        "事件",
        "运动会",
        "考试周",
        "世界"
    ]

    for k in profile_keywords:
        if k in text:
            return "profile"

    for k in relationship_keywords:
        if k in text:
            return "relationship"

    for k in story_keywords:
        if k in text:
            return "story"

    for k in event_keywords:
        if k in text:
            return "event"

    return "general"