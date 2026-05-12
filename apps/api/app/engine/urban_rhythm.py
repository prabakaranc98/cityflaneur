from __future__ import annotations

import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Crowd density model
# ---------------------------------------------------------------------------
# Multiplier applied to crowd_risk for a place in a given neighborhood at a
# given time.  Values > 1.0 mean more crowded than baseline.
# Keys: neighborhood name → weekday (0=Mon … 6=Sun) → day_type → multiplier.
# "_default" is the fallback for unlisted neighborhoods.

_DayType = str  # "weekday_rush" | "weekday_lunch" | "weekend_peak" | "off_peak"

CROWD_MULTIPLIERS: dict[str, dict[int, dict[_DayType, float]]] = {
    "Midtown": {
        **{d: {"weekday_rush": 2.2, "weekday_lunch": 1.8, "weekend_peak": 1.3, "off_peak": 1.0} for d in range(5)},
        5: {"weekday_rush": 1.0, "weekday_lunch": 1.4, "weekend_peak": 1.5, "off_peak": 0.9},
        6: {"weekday_rush": 1.0, "weekday_lunch": 1.3, "weekend_peak": 1.4, "off_peak": 0.8},
    },
    "Times Square": {
        **{d: {"weekday_rush": 2.5, "weekday_lunch": 2.0, "weekend_peak": 2.3, "off_peak": 1.6} for d in range(5)},
        5: {"weekday_rush": 1.6, "weekday_lunch": 2.1, "weekend_peak": 2.5, "off_peak": 1.8},
        6: {"weekday_rush": 1.5, "weekday_lunch": 2.0, "weekend_peak": 2.4, "off_peak": 1.7},
    },
    "SoHo": {
        **{d: {"weekday_rush": 1.2, "weekday_lunch": 1.4, "weekend_peak": 1.8, "off_peak": 0.9} for d in range(5)},
        5: {"weekday_rush": 1.0, "weekday_lunch": 1.6, "weekend_peak": 2.0, "off_peak": 1.2},
        6: {"weekday_rush": 1.0, "weekday_lunch": 1.5, "weekend_peak": 1.9, "off_peak": 1.1},
    },
    "Financial District": {
        **{d: {"weekday_rush": 2.0, "weekday_lunch": 1.6, "weekend_peak": 0.6, "off_peak": 0.7} for d in range(5)},
        5: {"weekday_rush": 0.5, "weekday_lunch": 0.6, "weekend_peak": 0.5, "off_peak": 0.4},
        6: {"weekday_rush": 0.4, "weekday_lunch": 0.5, "weekend_peak": 0.5, "off_peak": 0.4},
    },
    "Upper West Side": {
        **{d: {"weekday_rush": 1.4, "weekday_lunch": 1.0, "weekend_peak": 1.3, "off_peak": 0.8} for d in range(5)},
        5: {"weekday_rush": 0.9, "weekday_lunch": 1.2, "weekend_peak": 1.5, "off_peak": 1.0},
        6: {"weekday_rush": 0.9, "weekday_lunch": 1.1, "weekend_peak": 1.4, "off_peak": 0.9},
    },
    "Union Square": {
        **{d: {"weekday_rush": 1.6, "weekday_lunch": 1.8, "weekend_peak": 1.5, "off_peak": 1.0} for d in range(5)},
        5: {"weekday_rush": 1.0, "weekday_lunch": 1.6, "weekend_peak": 1.8, "off_peak": 1.1},
        6: {"weekday_rush": 1.0, "weekday_lunch": 1.5, "weekend_peak": 1.7, "off_peak": 1.0},
    },
    "Chelsea": {
        **{d: {"weekday_rush": 1.1, "weekday_lunch": 1.2, "weekend_peak": 1.6, "off_peak": 0.9} for d in range(5)},
        5: {"weekday_rush": 0.9, "weekday_lunch": 1.3, "weekend_peak": 1.8, "off_peak": 1.1},
        6: {"weekday_rush": 0.9, "weekday_lunch": 1.2, "weekend_peak": 1.7, "off_peak": 1.0},
    },
    "East Village": {
        **{d: {"weekday_rush": 1.0, "weekday_lunch": 1.1, "weekend_peak": 1.5, "off_peak": 0.8} for d in range(5)},
        5: {"weekday_rush": 0.9, "weekday_lunch": 1.2, "weekend_peak": 1.7, "off_peak": 1.1},
        6: {"weekday_rush": 0.9, "weekday_lunch": 1.1, "weekend_peak": 1.6, "off_peak": 1.0},
    },
    "_default": {
        **{d: {"weekday_rush": 1.3, "weekday_lunch": 1.1, "weekend_peak": 1.2, "off_peak": 1.0} for d in range(5)},
        5: {"weekday_rush": 1.0, "weekday_lunch": 1.1, "weekend_peak": 1.3, "off_peak": 1.0},
        6: {"weekday_rush": 1.0, "weekday_lunch": 1.0, "weekend_peak": 1.2, "off_peak": 0.9},
    },
}


def classify_day_type(dt: datetime) -> _DayType:
    """Return the crowd-pattern category for a given local datetime."""
    weekday = dt.weekday()  # 0=Mon
    if weekday >= 5:
        hour = dt.hour
        return "weekend_peak" if 11 <= hour <= 16 else "off_peak"
    total_minutes = dt.hour * 60 + dt.minute
    if (7 * 60 + 30) <= total_minutes <= (9 * 60 + 30) or 17 * 60 <= total_minutes <= 19 * 60:
        return "weekday_rush"
    if 12 * 60 <= total_minutes <= 14 * 60:
        return "weekday_lunch"
    return "off_peak"


def crowd_multiplier(neighborhood: str, dt: datetime) -> float:
    """Return a crowd density multiplier in [0.4, 2.5] for neighborhood at dt.

    Values > 1.0 mean more crowded than the place's baseline crowd_risk.
    """
    area = CROWD_MULTIPLIERS.get(neighborhood, CROWD_MULTIPLIERS["_default"])
    weekday = dt.weekday()
    row = area.get(weekday, area.get(0, {}))
    day_type = classify_day_type(dt)
    return row.get(day_type, 1.0)


# ---------------------------------------------------------------------------
# Seasonal POI availability
# ---------------------------------------------------------------------------
# Rules: days_of_week (0=Mon) and months (1=Jan) must both match for open.
# is_seasonally_open returns None when there is no rule (open by default).

_SeasonalRule = dict  # {"days_of_week": list[int], "months": list[int]}

SEASONAL_OPEN: dict[str, _SeasonalRule] = {
    "Union Square Greenmarket": {
        "days_of_week": [2, 4, 6],  # Wed, Fri, Sat
        "months": list(range(1, 13)),  # year-round
    },
    "Governors Island": {
        "days_of_week": list(range(7)),
        "months": [5, 6, 7, 8, 9, 10],  # May–Oct
    },
    "Bryant Park Winter Village": {
        "days_of_week": list(range(7)),
        "months": [11, 12, 1],  # Nov–Jan
    },
    "Pier 17 Rooftop": {
        "days_of_week": list(range(7)),
        "months": [5, 6, 7, 8, 9],  # May–Sep
    },
    "Chelsea Waterside Park": {
        "days_of_week": list(range(7)),
        "months": [4, 5, 6, 7, 8, 9, 10],  # Apr–Oct
    },
    "Grand Central Holiday Fair": {
        "days_of_week": list(range(7)),
        "months": [11, 12],  # Nov–Dec
    },
}


def is_seasonally_open(place_name: str, dt: datetime) -> bool | None:
    """Return True/False if a seasonal rule exists for this place, else None.

    None means "no seasonal rule — treat as open by default."
    False means "definitively closed by seasonal rule" (wrong day or off-season).
    """
    rule = SEASONAL_OPEN.get(place_name)
    if rule is None:
        return None
    return dt.weekday() in rule["days_of_week"] and dt.month in rule["months"]


# ---------------------------------------------------------------------------
# Sunset calculation (Spencer 1971 approximation, NY latitude)
# ---------------------------------------------------------------------------

_NY_LAT_RAD = math.radians(40.73)  # approximate Manhattan latitude


def minutes_to_sunset_ny(dt: datetime) -> float:
    """Return minutes from dt until tonight's sunset at NY latitude.

    Returns a negative number if sunset has already passed today.
    Uses the Spencer (1971) solar declination approximation — accurate to
    within ~1-2 minutes for practical routing purposes.
    """
    day_of_year = dt.timetuple().tm_yday
    b = (2.0 * math.pi / 364.0) * (day_of_year - 1)
    declination = (
        0.006918
        - 0.399912 * math.cos(b)
        + 0.070257 * math.sin(b)
        - 0.006758 * math.cos(2 * b)
        + 0.000907 * math.sin(2 * b)
    )
    cos_ha = -math.tan(_NY_LAT_RAD) * math.tan(declination)
    cos_ha = max(-1.0, min(1.0, cos_ha))
    half_day_hours = math.degrees(math.acos(cos_ha)) / 15.0
    sunset_hour = 12.0 + half_day_hours  # solar noon ≈ 12:00 local
    current_hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    return (sunset_hour - current_hour) * 60.0
