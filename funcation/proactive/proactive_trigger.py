def detect_trigger(memory_data):

    story = memory_data.get(
        "story",
        {}
    )

    if story.get("changed"):

        story["changed"] = False

        return {
            "trigger": "story",
            "reason": "剧情推进"
        }

    relationship = memory_data.get(
        "relationship",
        {}
    )

    if relationship.get(
            "level_changed"
    ):

        relationship[
            "level_changed"
        ] = False

        return {
            "trigger": "relation",
            "reason": "关系变化"
        }

    state = memory_data.get(
        "character_state",
        {}
    )

    if state.get(
            "mood_changed"
    ):

        state[
            "mood_changed"
        ] = False

        return {
            "trigger": "state",
            "reason": "心情变化"
        }

    return None