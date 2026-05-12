from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.engine.urban_rhythm import (
    CROWD_MULTIPLIERS,
    SEASONAL_OPEN,
    classify_day_type,
    crowd_multiplier,
    is_seasonally_open,
    minutes_to_sunset_ny,
)

NY_TZ = ZoneInfo("America/New_York")


def _dt(weekday: int, hour: int, minute: int = 0) -> datetime:
    """Create a NY-aware datetime on an arbitrary week with the given weekday/hour."""
    # Use a fixed Monday as base: 2026-05-11 (weekday=0)
    from datetime import timedelta
    base = datetime(2026, 5, 11, hour, minute, tzinfo=NY_TZ)
    return base + timedelta(days=weekday)


class TestClassifyDayType:
    def test_weekday_morning_rush(self):
        assert classify_day_type(_dt(0, 8, 0)) == "weekday_rush"

    def test_weekday_evening_rush(self):
        assert classify_day_type(_dt(2, 17, 30)) == "weekday_rush"

    def test_weekday_lunch(self):
        assert classify_day_type(_dt(1, 13, 0)) == "weekday_lunch"

    def test_weekday_off_peak(self):
        assert classify_day_type(_dt(0, 15, 0)) == "off_peak"

    def test_saturday_peak(self):
        assert classify_day_type(_dt(5, 14, 0)) == "weekend_peak"

    def test_saturday_evening(self):
        assert classify_day_type(_dt(5, 20, 0)) == "off_peak"

    def test_sunday_morning(self):
        assert classify_day_type(_dt(6, 9, 0)) == "off_peak"


class TestCrowdMultiplier:
    def test_midtown_rush_higher_than_off_peak(self):
        rush = crowd_multiplier("Midtown", _dt(0, 8, 30))
        off_peak = crowd_multiplier("Midtown", _dt(0, 15, 0))
        assert rush > off_peak

    def test_times_square_always_above_one(self):
        assert crowd_multiplier("Times Square", _dt(0, 15, 0)) >= 1.0

    def test_financial_district_weekend_low(self):
        weekday = crowd_multiplier("Financial District", _dt(0, 12, 0))
        weekend = crowd_multiplier("Financial District", _dt(5, 12, 0))
        assert weekday > weekend

    def test_unknown_neighborhood_uses_default(self):
        result = crowd_multiplier("Nolita", _dt(0, 8, 0))
        default_rush = CROWD_MULTIPLIERS["_default"][0]["weekday_rush"]
        assert result == default_rush

    def test_result_in_reasonable_range(self):
        for hood in list(CROWD_MULTIPLIERS.keys()):
            for wday in range(7):
                for hour in [8, 13, 18, 21]:
                    result = crowd_multiplier(hood, _dt(wday % 5, hour))
                    assert 0.3 <= result <= 3.0, f"{hood} {wday} {hour}: {result}"


class TestIsSeasonallyOpen:
    def test_greenmarket_open_wednesday(self):
        wed = _dt(2, 10)  # Wednesday
        assert is_seasonally_open("Union Square Greenmarket", wed) is True

    def test_greenmarket_closed_monday(self):
        mon = _dt(0, 10)
        assert is_seasonally_open("Union Square Greenmarket", mon) is False

    def test_greenmarket_closed_tuesday(self):
        tue = _dt(1, 10)
        assert is_seasonally_open("Union Square Greenmarket", tue) is False

    def test_governors_island_open_in_summer(self):
        summer_sat = datetime(2026, 7, 11, 12, 0, tzinfo=NY_TZ)  # Saturday in July
        assert is_seasonally_open("Governors Island", summer_sat) is True

    def test_governors_island_closed_in_december(self):
        winter = datetime(2026, 12, 15, 12, 0, tzinfo=NY_TZ)
        assert is_seasonally_open("Governors Island", winter) is False

    def test_normal_place_returns_none(self):
        assert is_seasonally_open("Bryant Park", _dt(0, 12)) is None
        assert is_seasonally_open("The Met", _dt(3, 14)) is None
        assert is_seasonally_open("Some Random Cafe", _dt(1, 9)) is None

    def test_all_seasonal_places_have_valid_rules(self):
        for name, rule in SEASONAL_OPEN.items():
            assert "days_of_week" in rule, f"{name} missing days_of_week"
            assert "months" in rule, f"{name} missing months"
            assert all(0 <= d <= 6 for d in rule["days_of_week"])
            assert all(1 <= m <= 12 for m in rule["months"])


class TestMinutesToSunsetNY:
    def test_midday_has_positive_minutes(self):
        noon = datetime(2026, 5, 12, 12, 0, tzinfo=NY_TZ)
        result = minutes_to_sunset_ny(noon)
        assert result > 0, "Noon should have hours until sunset"

    def test_value_in_reasonable_range_for_noon(self):
        noon = datetime(2026, 6, 21, 12, 0, tzinfo=NY_TZ)  # summer solstice
        result = minutes_to_sunset_ny(noon)
        assert 200 < result < 600, f"Expected 3-10 hours until sunset at noon solstice, got {result:.0f} min"

    def test_evening_has_fewer_minutes_than_morning(self):
        morning = datetime(2026, 5, 12, 9, 0, tzinfo=NY_TZ)
        evening = datetime(2026, 5, 12, 19, 0, tzinfo=NY_TZ)
        assert minutes_to_sunset_ny(morning) > minutes_to_sunset_ny(evening)

    def test_winter_sunset_earlier_than_summer(self):
        winter_noon = datetime(2026, 12, 21, 12, 0, tzinfo=NY_TZ)
        summer_noon = datetime(2026, 6, 21, 12, 0, tzinfo=NY_TZ)
        assert minutes_to_sunset_ny(winter_noon) < minutes_to_sunset_ny(summer_noon)
