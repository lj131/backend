def detect_trigger(memory_data):

    world_notice = memory_data.get(
        "world_event_notice",
        {}
    )

    if world_notice.get("changed"):

        world_notice["changed"] = False

        type_labels = {
            "created": "世界事件开始",
            "advanced": "世界事件推进",
            "finished": "世界事件结束",
        }

        return {
            "trigger": "world_event",
            "reason": type_labels.get(
                world_notice.get("type", ""),
                "世界发生变化",
            ),
            "world_event": world_notice,
        }

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