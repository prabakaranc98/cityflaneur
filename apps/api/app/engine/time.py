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
    from app.engine.urban_rhythm import is_seasonally_open
    local = effective_datetime(at)
    seasonal = is_seasonally_open(place.name, local)
    if seasonal is False:
        return False
    if not place.opening_hours:
        return True
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


_FUZZY_TIMES = {"dusk": 19 * 60, "dawn": 6 * 60, "midnight": 24 * 60, "noon": 12 * 60}


def _parse_hhmm(value: str) -> int:
    value = value.strip().lower()
    if value in _FUZZY_TIMES:
        return _FUZZY_TIMES[value]
    parts = value.split(":", maxsplit=1)
    if len(parts) == 1:
        return int(parts[0]) * 60
    hour, minute = parts
    return int(hour) * 60 + int(minute)

