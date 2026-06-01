# memory文件
MEMORY_FILE = "memory.json"

import json
import os

MEMORY_DIR = "memories"


# 获取角色memory文件路径
def get_memory_path(character_id):
    return os.path.join(
        MEMORY_DIR,
        f"{character_id}_memory.json"
    )


# 加载角色记忆
def load_memory(character_id):
    path = get_memory_path(character_id)

    try:

        with open(path, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return []


# 保存角色记忆
def save_memory(character_id, messages):
    path = get_memory_path(character_id)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            messages,
            f,
            ensure_ascii=False,
            indent=2
        )


# 清空角色记忆
def clear_memory(character_id):
    save_memory(character_id, [])
