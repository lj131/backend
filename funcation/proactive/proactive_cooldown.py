from datetime import datetime
from datetime import timedelta


def check(memory_data):

    proactive = memory_data.get(
        "proactive",
        {}
    )

    last_time = proactive.get(
        "last_time",
        ""
    )

    if not last_time:

        return True

    last = datetime.fromisoformat(
        last_time
    )

    return (
            datetime.now() - last
    ) > timedelta(
        hours=3
    )