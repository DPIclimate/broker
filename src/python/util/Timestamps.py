from typing import Dict, Tuple
from zoneinfo import ZoneInfo
from datetime import timedelta, datetime, timezone

def now_utc():
    """
    Return a datetime.datetime object with the current time in the UTC timezone.
    """
    return datetime.datetime.now(tz=datetime.timezone.utc)


_seconds_per_day = 3600 * 24


def time_since(date: datetime) -> Dict[str, int|str]:
    now = datetime.now(timezone.utc)
    date_utc = date.astimezone(timezone.utc)
    delta = now - date_utc
    days = delta.days
    hours = int(delta.seconds / 3600)
    minutes = int((delta.seconds % 3600) / 60)
    seconds = int(delta.seconds % 60)

    ret_val = {
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'delta_seconds': delta.seconds + (delta.days * _seconds_per_day)
    }

    if days > 0:
        ret_val['desc'] = f'{days} days ago'
    elif hours > 0:
        ret_val['desc'] = f'{hours} hours ago'
    elif minutes > 0:
        ret_val['desc'] = f'{minutes} minutes ago'
    else:
        ret_val['desc'] = f'{seconds} seconds ago'

    return ret_val
