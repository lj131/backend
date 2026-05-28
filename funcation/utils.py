
from datetime import datetime

def get_time_diff_minutes(last_time):
    if not last_time:
        return 0

    last = datetime.fromisoformat(last_time)

    now = datetime.now()

    diff = now - last

    return diff.total_seconds() / 60
