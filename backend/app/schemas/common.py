import re
from datetime import datetime, timezone


def normalize_phone_number(value: str) -> str:
    return re.sub(r"[\s().-]", "", value)


def require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scheduled_at must include a timezone")
    return value.astimezone(timezone.utc)


def normalize_output_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)