import datetime

def now_utc():
    """
    Return a datetime.datetime object with the current time in the UTC timezone.
    """
    return datetime.datetime.now(tz=datetime.timezone.utc)
