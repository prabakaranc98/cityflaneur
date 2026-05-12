from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.schemas import Place


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
NY_TZ = ZoneInfo("America/New_York")


def effective_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(NY_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=NY_TZ)
    return value.astimezone(NY_TZ)


def is_place_open(place: Place, at: datetime | None) -> bool:
    if not place.opening_hours:
        return True
    local = effective_datetime(at)
    day_key = DAYS[local.weekday()]
    windows = place.opening_hours.get(day_key, []) + place.opening_hours.get("daily", [])
    if not windows:
        return False
    minutes_now = local.hour * 60 + local.minute
    return any(_window_contains(window, minutes_now) for window in windows)


def _window_contains(window: str, minutes_now: int) -> bool:
    if window == "24h":
        return True
    start_raw, end_raw = window.split("-", maxsplit=1)
    start = _parse_hhmm(start_raw)
    end = _parse_hhmm(end_raw)
    if start <= end:
        return start <= minutes_now <= end
    return minutes_now >= start or minutes_now <= end


def _parse_hhmm(value: str) -> int:
    hour, minute = value.split(":", maxsplit=1)
    return int(hour) * 60 + int(minute)

