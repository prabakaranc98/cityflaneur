from __future__ import annotations

import math
from typing import NamedTuple


class SubwayStation(NamedTuple):
    name: str
    lat: float
    lng: float
    lines: tuple[str, ...]


_STATIONS: tuple[SubwayStation, ...] = (
    # 1/2/3 — Seventh Ave / Broadway
    SubwayStation("96 St", 40.7953, -73.9720, ("1", "2", "3")),
    SubwayStation("86 St", 40.7863, -73.9762, ("1",)),
    SubwayStation("79 St", 40.7830, -73.9798, ("1",)),
    SubwayStation("72 St", 40.7783, -73.9820, ("1", "2", "3")),
    SubwayStation("66 St–Lincoln Ctr", 40.7726, -73.9826, ("1",)),
    SubwayStation("59 St–Columbus Circle", 40.7686, -73.9815, ("1", "A", "B", "C", "D")),
    SubwayStation("50 St", 40.7621, -73.9835, ("1", "C", "E")),
    SubwayStation("Times Sq–42 St", 40.7556, -73.9866, ("1", "2", "3", "7", "N", "Q", "R", "W")),
    SubwayStation("34 St–Penn Station", 40.7505, -73.9928, ("1", "2", "3", "A", "C", "E")),
    SubwayStation("28 St", 40.7448, -73.9961, ("1", "N", "R", "W")),
    SubwayStation("23 St", 40.7419, -73.9995, ("1", "F", "M", "N", "R", "W")),
    SubwayStation("14 St", 40.7373, -74.0006, ("1", "2", "3", "A", "C", "E", "F", "M", "L")),
    SubwayStation("Christopher St", 40.7336, -74.0027, ("1",)),
    SubwayStation("Houston St", 40.7284, -74.0050, ("1",)),
    SubwayStation("Canal St", 40.7228, -74.0047, ("1", "A", "C", "E")),
    SubwayStation("Chambers St", 40.7154, -74.0088, ("1", "2", "3", "A", "C")),
    SubwayStation("Fulton St", 40.7089, -74.0077, ("2", "3", "4", "5", "A", "C", "J", "Z")),
    SubwayStation("Wall St", 40.7075, -74.0116, ("2", "3", "4", "5")),
    # 4/5/6 — Lexington Ave
    SubwayStation("125 St", 40.8060, -73.9379, ("4", "5", "6")),
    SubwayStation("116 St", 40.7985, -73.9407, ("6",)),
    SubwayStation("103 St", 40.7898, -73.9481, ("6",)),
    SubwayStation("96 St", 40.7850, -73.9516, ("4", "5", "6")),
    SubwayStation("86 St", 40.7775, -73.9555, ("4", "5", "6")),
    SubwayStation("77 St", 40.7722, -73.9591, ("6",)),
    SubwayStation("68 St–Hunter College", 40.7682, -73.9643, ("6",)),
    SubwayStation("59 St", 40.7625, -73.9674, ("4", "5", "6")),
    SubwayStation("51 St", 40.7570, -73.9719, ("6",)),
    SubwayStation("Grand Central–42 St", 40.7525, -73.9769, ("4", "5", "6", "7", "S")),
    SubwayStation("33 St", 40.7462, -73.9837, ("6",)),
    SubwayStation("28 St", 40.7429, -73.9884, ("6",)),
    SubwayStation("23 St", 40.7397, -73.9867, ("6",)),
    SubwayStation("14 St–Union Sq", 40.7348, -73.9899, ("4", "5", "6", "L", "N", "Q", "R", "W")),
    SubwayStation("Astor Place", 40.7304, -73.9912, ("6",)),
    SubwayStation("Bleecker St", 40.7257, -73.9944, ("6",)),
    SubwayStation("Spring St", 40.7225, -74.0018, ("6",)),
    SubwayStation("Brooklyn Bridge–City Hall", 40.7131, -74.0046, ("4", "5", "6")),
    # A/C/E — Eighth Ave
    SubwayStation("125 St", 40.8082, -73.9523, ("A", "B", "C", "D")),
    SubwayStation("86 St", 40.7822, -73.9796, ("B", "C")),
    SubwayStation("81 St–Museum", 40.7820, -73.9763, ("B", "C")),
    SubwayStation("72 St", 40.7762, -73.9793, ("B", "C")),
    SubwayStation("42 St–Port Authority", 40.7575, -73.9899, ("A", "C", "E")),
    SubwayStation("23 St", 40.7453, -74.0002, ("C", "E")),
    SubwayStation("14 St", 40.7394, -74.0027, ("A", "C", "E")),
    SubwayStation("W 4 St", 40.7324, -74.0004, ("A", "B", "C", "D", "E", "F", "M")),
    SubwayStation("Spring St", 40.7259, -74.0042, ("A", "C", "E")),
    SubwayStation("Canal St", 40.7226, -74.0047, ("A", "C", "E")),
    # F/M/B/D — Sixth Ave
    SubwayStation("47–50 Sts–Rockefeller Ctr", 40.7582, -73.9796, ("B", "D", "F", "M")),
    SubwayStation("42 St–Bryant Park", 40.7553, -73.9847, ("B", "D", "F", "M")),
    SubwayStation("34 St–Herald Sq", 40.7494, -73.9886, ("B", "D", "F", "M", "N", "Q", "R", "W")),
    SubwayStation("23 St", 40.7428, -73.9930, ("F", "M")),
    SubwayStation("14 St", 40.7398, -73.9986, ("F", "M", "L")),
    SubwayStation("2 Av", 40.7225, -73.9888, ("F",)),
    SubwayStation("Delancey St–Essex St", 40.7183, -73.9882, ("F", "J", "M", "Z")),
    # N/Q/R/W — Broadway
    SubwayStation("49 St", 40.7598, -73.9840, ("N", "Q", "R", "W")),
    SubwayStation("8 St–NYU", 40.7296, -73.9929, ("N", "Q", "R", "W")),
    SubwayStation("Prince St", 40.7244, -73.9977, ("N", "Q", "R", "W")),
    SubwayStation("Canal St", 40.7190, -74.0014, ("N", "Q", "R", "W")),
    # L
    SubwayStation("8 Av", 40.7394, -74.0028, ("L",)),
    SubwayStation("6 Av", 40.7379, -73.9978, ("L",)),
    SubwayStation("1 Av", 40.7301, -73.9809, ("L",)),
    # 7
    SubwayStation("Hudson Yards", 40.7551, -74.0017, ("7",)),
    # Harlem B/D/2/3/A/C
    SubwayStation("145 St", 40.8229, -73.9487, ("A", "B", "C", "D")),
    SubwayStation("135 St", 40.8151, -73.9417, ("2", "3")),
    SubwayStation("125 St", 40.8108, -73.9460, ("2", "3")),
    SubwayStation("116 St", 40.8032, -73.9582, ("B", "C")),
    SubwayStation("110 St–Cathedral Pkwy", 40.7994, -73.9636, ("B", "C")),
    SubwayStation("Cathedral Pkwy", 40.8029, -73.9659, ("1",)),
)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_subway_label(lat: float, lng: float, max_distance_m: int = 750) -> str | None:
    """Return a label like 'W 4 St (A/B/C/D/E/F/M) ~350m', or None if nothing is within max_distance_m."""
    best: SubwayStation | None = None
    best_dist = float("inf")
    for station in _STATIONS:
        dist = _haversine_m(lat, lng, station.lat, station.lng)
        if dist < best_dist:
            best_dist = dist
            best = station
    if best is None or best_dist > max_distance_m:
        return None
    lines = "/".join(best.lines)
    dist_m = int(round(best_dist / 10) * 10)
    return f"{best.name} ({lines}) ~{dist_m}m"
