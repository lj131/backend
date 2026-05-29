
import json
import random


#好感度 文件
CHARACTER_FILE = "character.json"



def get_proactive_message(favorability, minutes):

    low_messages = [
        "哦，又来了。",
        "今天居然还在。",
        "……有事？"
    ]

    normal_messages = [
        "你来了。",
        "今天怎么样？",
        "在忙吗？"
    ]

    high_messages = [
        "终于来了。",
        "我刚刚还在想你。",
        "今天过得怎么样？",
        "怎么现在才来。"
    ]

    if minutes > 2:
        return "……你终于想起我了？"

    if favorability < 30:

        return random.choice(low_messages)

    elif favorability < 70:

        return random.choice(normal_messages)

    else:

        return random.choice(high_messages)
# 读取角色状态
def load_character():

    try:

        with open(CHARACTER_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return {
            "favorability": 50,
            "name": "林晚"
        }

# 保存角色状态
def save_character(data):

    with open(CHARACTER_FILE, "w", encoding="utf-8") as f:

        json.dump(data, f, ensure_ascii=False, indent=2)