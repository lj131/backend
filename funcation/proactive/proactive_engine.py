from datetime import datetime

from funcation.proactive import proactive_trigger

from funcation.proactive import proactive_decision

from funcation.proactive import proactive_cooldown

from funcation.proactive import proactive_message_agent


def run(
        mc,
        character,
        world
):
    memory_data = mc.load_memory(
        character["id"]
    )

    trigger = (
        proactive_trigger.detect_trigger(
            memory_data
        )
    )

    if not trigger:

        return None

    if not proactive_decision.should_send(
            memory_data
    ):
        return None

    if not proactive_cooldown.check(
            memory_data
    ):
        return None

    message = (
        proactive_message_agent.generate_message(
            trigger,
            character,
            world,
            memory_data
        )
    )

    proactive = memory_data.setdefault(
        "proactive",
        {}
    )

    proactive[
        "last_time"
    ] = datetime.now().isoformat()

    proactive[
        "last_message"
    ] = message

    proactive[
        "last_trigger"
    ] = trigger["trigger"]

    proactive[
        "today_count"
    ] = proactive.get(
        "today_count",
        0
    ) + 1

    mc.save_memory(
        character["id"],
        memory_data
    )

    return message