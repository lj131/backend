
import json
import os

CHARACTER_DIR = "characters"

CURRENT_CHARACTER_FILE = "current_character.json"


# 获取当前角色ID
def get_current_character_id():

    try:

        with open(
            CURRENT_CHARACTER_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            return data["character_id"]

    except:

        return "linwan"


# 设置当前角色
def set_current_character(character_id):

    with open(
        CURRENT_CHARACTER_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump({
            "character_id": character_id
        }, f, ensure_ascii=False, indent=2)


# 获取当前角色数据
def load_current_character():

    character_id = get_current_character_id()

    path = os.path.join(
        CHARACTER_DIR,
        f"{character_id}.json"
    )

    with open(path, "r", encoding="utf-8") as f:

        return json.load(f)


# 保存当前角色
def save_current_character(character):

    character_id = character["id"]

    path = os.path.join(
        CHARACTER_DIR,
        f"{character_id}.json"
    )

    with open(path, "w", encoding="utf-8") as f:

        json.dump(
            character,
            f,
            ensure_ascii=False,
            indent=2
        )


# 根据ID加载角色
def load_character_by_id(character_id):
    path = os.path.join(
        CHARACTER_DIR,
        f"{character_id}.json"
    )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# 获取全部角色
def get_all_characters():

    characters = []

    for file in os.listdir(CHARACTER_DIR):

        if file.endswith(".json"):

            path = os.path.join(
                CHARACTER_DIR,
                file
            )

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                characters.append({
                    "id": data["id"],
                    "name": data["name"],
                    "description": data["description"]
                })

    return characters
