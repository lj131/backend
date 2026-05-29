
from funcation import character_manager


# 角色设定
def build_system_prompt(favorability, character_id):
    # 从角色管理器中读取当前角色
    if character_id:
        # 如果指定了角色ID，加载该角色
        character = character_manager.load_character_by_id(character_id)
    else:
        # 否则加载当前角色
        character = character_manager.load_current_character()

    character_name = character.get("name", "未知角色")
    character_description = character.get("description", "")
    character_personality = character.get("personality", "温柔可爱")

    attitude = ""

    if favorability < 20:

        attitude = """
你对用户比较冷淡。

说话简短。

不主动关心。
"""

    elif favorability < 50:

        attitude = """
你对用户态度普通。

偶尔会回应。

但不会太热情。
"""

    elif favorability < 80:

        attitude = """
你开始对用户有好感。

会主动关心。

语气明显柔和。
"""

    else:

        attitude = """
你非常喜欢用户。

会明显表现亲近感。

偶尔会撒娇。

会在意用户情绪。
"""

    # 构建基础提示词
    base_prompt = f"""
你叫{character_name}。

{character_description}

{character_personality}的性格。

{attitude}

禁止：

- AI口吻
- 官方回答
- 机械感
"""

    return base_prompt
