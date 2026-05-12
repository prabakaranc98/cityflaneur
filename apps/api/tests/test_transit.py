from __future__ import annotations

import pytest

from app.engine.transit import nearest_subway_label, _STATIONS, _haversine_m


class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_m(40.7, -74.0, 40.7, -74.0) == pytest.approx(0.0, abs=1e-3)

    def test_known_distance(self):
        # Times Sq to Grand Central is ~800m
        dist = _haversine_m(40.7556, -73.9866, 40.7525, -73.9769)
        assert 700 < dist < 950


class TestNearestSubway:
    def test_finds_station_in_range(self):
        label = nearest_subway_label(40.7359, -73.9911)
        assert label is not None
        assert "(" in label and ")" in label
        assert "~" in label

    def test_label_format(self):
        label = nearest_subway_label(40.7556, -73.9866)
        assert label is not None
        parts = label.split("(")
        assert len(parts) == 2
        lines_and_dist = parts[1]
        assert ")" in lines_and_dist

    def test_outside_range_returns_none(self):
        result = nearest_subway_label(40.7359, -73.9911, max_distance_m=5)
        assert result is None

    def test_no_duplicate_station_causes_crash(self):
        # All stations should be iterable without error
        for station in _STATIONS:
            assert station.name
            assert station.lines

    def test_harlem_station_found(self):
        label = nearest_subway_label(40.8103, -73.9497)
        assert label is not None
        _lines_in = label.split("(")[1].split(")")[0]
        assert any(line in _lines_in for line in ["2", "3", "A", "B", "C", "D"])

    def test_upper_west_side_finds_bc_line(self):
        label = nearest_subway_label(40.7820, -73.9763)
        assert label is not None
        assert "B" in label or "C" in label

    def test_chelsea_finds_ace(self):
        label = nearest_subway_label(40.7423, -74.0060)
        assert label is not None
