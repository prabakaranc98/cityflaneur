from __future__ import annotations

import math
from collections import Counter, defaultdict

from app.models.schemas import Coordinates, GridCell, Place, PlaceCategory, RouteGeometry

EARTH_RADIUS_M = 6_371_000
WALKING_SPEED_M_PER_MIN = 80
MANHATTAN_MIN_LAT = 40.68
MANHATTAN_MIN_LNG = -74.05
MANHATTAN_GRID_REF_LAT = 40.785
MANHATTAN_GRID_CELL_SIZE_M = 500
M_PER_DEG_LAT = 111_320
M_PER_DEG_LNG = 111_320 * math.cos(math.radians(MANHATTAN_GRID_REF_LAT))


def haversine_m(a: Coordinates, b: Coordinates) -> float:
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlng = math.radians(b.lng - a.lng)
    root = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(root))


def route_distance_m(origin: Coordinates, stops: list[Coordinates]) -> int:
    if not stops:
        return 0
    distance = 0.0
    cursor = origin
    for stop in stops:
        distance += haversine_m(cursor, stop)
        cursor = stop
    return int(round(distance))


def walking_route_distance_m(origin: Coordinates, stops: list[Coordinates]) -> int:
    """Approximate walk distance with a Manhattan-grid bias until a routing engine is wired in."""
    if not stops:
        return 0
    distance = 0.0
    cursor = origin
    for stop in stops:
        avg_lat = math.radians((cursor.lat + stop.lat) / 2)
        dy = abs(stop.lat - cursor.lat) * 111_320
        dx = abs(stop.lng - cursor.lng) * 111_320 * math.cos(avg_lat)
        gridish_distance = dx + dy
        direct_distance = haversine_m(cursor, stop)
        distance += max(direct_distance * 1.18, gridish_distance * 0.82)
        cursor = stop
    return int(round(distance))


def walking_minutes(distance_m: int) -> int:
    return int(math.ceil(distance_m / WALKING_SPEED_M_PER_MIN))


def route_geometry(origin: Coordinates, stops: list[Coordinates]) -> RouteGeometry:
    coords = [(origin.lng, origin.lat)]
    coords.extend((stop.lng, stop.lat) for stop in stops)
    return RouteGeometry(coordinates=coords)


def project_to_grid_m(coordinates: Coordinates) -> tuple[float, float]:
    x_m = (coordinates.lng - MANHATTAN_MIN_LNG) * M_PER_DEG_LNG
    y_m = (coordinates.lat - MANHATTAN_MIN_LAT) * M_PER_DEG_LAT
    return x_m, y_m


def unproject_from_grid_m(x_m: float, y_m: float) -> Coordinates:
    return Coordinates(
        lat=MANHATTAN_MIN_LAT + y_m / M_PER_DEG_LAT,
        lng=MANHATTAN_MIN_LNG + x_m / M_PER_DEG_LNG,
    )


def manhattan_grid_indices(coordinates: Coordinates) -> tuple[int, int]:
    x_m, y_m = project_to_grid_m(coordinates)
    return (
        math.floor(x_m / MANHATTAN_GRID_CELL_SIZE_M),
        math.floor(y_m / MANHATTAN_GRID_CELL_SIZE_M),
    )


def manhattan_grid_cell_id(coordinates: Coordinates) -> str:
    """Stable 500m projected grid key for Manhattan-first indexing."""
    x_index, y_index = manhattan_grid_indices(coordinates)
    return f"mnh-500m-{y_index:03d}-{x_index:03d}"


def grid_cell_bounds(x_index: int, y_index: int) -> list[Coordinates]:
    min_x = x_index * MANHATTAN_GRID_CELL_SIZE_M
    min_y = y_index * MANHATTAN_GRID_CELL_SIZE_M
    max_x = min_x + MANHATTAN_GRID_CELL_SIZE_M
    max_y = min_y + MANHATTAN_GRID_CELL_SIZE_M
    return [
        unproject_from_grid_m(min_x, min_y),
        unproject_from_grid_m(max_x, min_y),
        unproject_from_grid_m(max_x, max_y),
        unproject_from_grid_m(min_x, max_y),
    ]


def build_grid_cells(places: list[Place]) -> list[GridCell]:
    buckets: dict[str, list[Place]] = defaultdict(list)
    indices: dict[str, tuple[int, int]] = {}
    for place in places:
        x_index, y_index = manhattan_grid_indices(place.coordinates)
        cell_id = manhattan_grid_cell_id(place.coordinates)
        buckets[cell_id].append(place)
        indices[cell_id] = (x_index, y_index)

    cells: list[GridCell] = []
    for cell_id, cell_places in sorted(buckets.items()):
        x_index, y_index = indices[cell_id]
        min_x = x_index * MANHATTAN_GRID_CELL_SIZE_M
        min_y = y_index * MANHATTAN_GRID_CELL_SIZE_M
        categories = Counter(place.category for place in cell_places)
        neighborhoods = sorted({place.neighborhood for place in cell_places})
        cells.append(
            GridCell(
                id=cell_id,
                center=unproject_from_grid_m(
                    min_x + MANHATTAN_GRID_CELL_SIZE_M / 2,
                    min_y + MANHATTAN_GRID_CELL_SIZE_M / 2,
                ),
                bounds=grid_cell_bounds(x_index, y_index),
                x_index=x_index,
                y_index=y_index,
                cell_size_m=MANHATTAN_GRID_CELL_SIZE_M,
                place_count=len(cell_places),
                top_categories=[
                    category for category, _ in categories.most_common(3)
                ],
                neighborhoods=neighborhoods,
            )
        )
    return cells


def category_matches(place: Place, category_or_tag: str | PlaceCategory) -> bool:
    needle = str(category_or_tag)
    return place.category == category_or_tag or needle in place.tags or needle in place.atmosphere_tags
