def should_send(memory_data):

    proactive = memory_data.get(
        "proactive",
        {}
    )

    today_count = proactive.get(
        "today_count",
        0
    )

    if today_count >= 5:

        return False

    state = memory_data.get(
        "character_state",
        {}
    )

    energy = state.get(
        "energy",
        100
    )

    if energy <= 10:

        return False

    return True