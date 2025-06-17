from datetime import timedelta


def timedelta_isoformat(td: timedelta) -> str:
    """
    ISO 8601 encoding for Python timedelta object.
    Taken from pydantic source:
        https://github.com/pydantic/pydantic/blob/3704eccce4661455acdda1cdcf716bd4b3382e08/pydantic/deprecated/json.py#L135-L140

    """
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{"-" if td.days < 0 else ""}P{abs(td.days)}DT{hours:d}H{minutes:d}M{seconds:d}.{td.microseconds:06d}S'
