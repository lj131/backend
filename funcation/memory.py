import json
import random

# memory文件
MEMORY_FILE = "memory.json"


# 读取历史聊天
def load_memory():
    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return []


# 保存历史聊天
def save_memory(messages):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
