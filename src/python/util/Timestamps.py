from typing import Dict, Tuple
from zoneinfo import ZoneInfo
from datetime import timedelta, datetime, timezone

def now_utc():
    """
    Return a datetime.datetime object with the current time in the UTC timezone.
    """
    return datetime.datetime.now(tz=datetime.timezone.utc)


_seconds_per_day = 3600 * 24


def time_since(date: datetime, brief=False) -> Dict[str, int|str]:
    now = datetime.now(timezone.utc)
    date_utc = date.astimezone(timezone.utc)
    delta = now - date_utc
    days = delta.days
    hours = int(delta.seconds / 3600)
    minutes = int((delta.seconds % 3600) / 60)

    ret_val = {
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'delta_seconds': delta.seconds + (delta.days * _seconds_per_day)
    }

    if delta < timedelta(0):
        # Force a longer string for future timestamps.
        brief = False

    direction = 'from now' if delta < timedelta(0) else 'ago'

    days = 'd' if brief else f'days {direction}'
    hrs = 'h' if brief else 'fhours {direction}'
    mins = 'm' if brief else f'minutes {direction}'
    secs = 's' if brief else f'seconds {direction}'

    duration = abs(delta)
    if duration.days > 0:
        ret_val['desc'] = f'{duration.days} {days}'
    elif duration.seconds >= 3600:
        ret_val['desc'] = f'{duration.seconds // 3600} {hrs}'
    elif duration.seconds >= 60:
        ret_val['desc'] = f'{duration.seconds // 60} {mins}'
    else:
        ret_val['desc'] = f'{duration.seconds} {secs}'

    return ret_val
