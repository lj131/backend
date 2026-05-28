
import json
import random

PROFILE_FILE = "user_profile.json"

def load_profile():

    try:

        with open(PROFILE_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return {
            "name": "",
            "city": "",
            "job": "",
            "mood": "",
            "recent_topics": []
        }

def save_profile(profile):

    with open(PROFILE_FILE, "w", encoding="utf-8") as f:

        json.dump(profile, f, ensure_ascii=False, indent=2)

def update_profile(user_input, profile):

    # 城市
    if "南京" in user_input:
        profile["city"] = "南京"

    # 工作
    if "上班" in user_input:
        profile["job"] = "上班族"

    if "Java" in user_input:
        profile["job"] = "Java开发"

    # 情绪
    if "累" in user_input:
        profile["mood"] = "疲惫"

    if "难过" in user_input:
        profile["mood"] = "难过"

    if "开心" in user_input:
        profile["mood"] = "开心"

    # 最近话题
    profile["recent_topics"].append(user_input)

    profile["recent_topics"] = profile["recent_topics"][-5:]

    save_profile(profile)



def get_caring_message(profile):

    caring_messages = []

    if profile["mood"] == "疲惫":

        caring_messages.append(
            "你最近是不是太累了？"
        )

    if profile["mood"] == "难过":

        caring_messages.append(
            "你最近心情好像不太好。"
        )

    if profile["job"] == "Java开发":

        caring_messages.append(
            "今天代码又出bug了？"
        )

    if profile["city"] == "南京":

        caring_messages.append(
            "南京最近天气怎么样？"
        )

    if not caring_messages:

        return None

    return random.choice(caring_messages)