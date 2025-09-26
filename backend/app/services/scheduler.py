from datetime import datetime


def next_run(minutes: int = 60) -> datetime:
    from datetime import timedelta

    return datetime.utcnow() + timedelta(minutes=minutes)


