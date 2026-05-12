from __future__ import annotations

import math
from collections import defaultdict

from app.engine.geo import haversine_m, manhattan_grid_cell_id
from app.models.schemas import Coordinates, Place, PlaceCategory

# (name, min_lat, max_lat, min_lng, max_lng) — ordered from most-specific to broadest
_NEIGHBORHOOD_BOUNDS: list[tuple[str, float, float, float, float]] = [
    ("Battery Park City", 40.705, 40.721, -74.025, -74.012),
    ("Financial District", 40.700, 40.714, -74.020, -73.999),
    ("Tribeca", 40.710, 40.722, -74.014, -73.999),
    ("Chinatown", 40.712, 40.720, -74.003, -73.990),
    ("Little Italy", 40.718, 40.724, -73.999, -73.992),
    # Nolita is east of Lafayette St (-73.997), SoHo is west of it
    ("Nolita", 40.721, 40.729, -73.999, -73.989),
    ("SoHo", 40.719, 40.731, -74.011, -73.994),
    ("Lower East Side", 40.712, 40.726, -73.994, -73.969),
    ("West Village", 40.728, 40.743, -74.013, -73.998),
    # Union Square before Greenwich Village so 14th St coords resolve correctly
    ("Union Square", 40.731, 40.739, -73.994, -73.981),
    ("Greenwich Village", 40.727, 40.739, -74.005, -73.993),
    ("East Village", 40.720, 40.733, -73.995, -73.972),
    ("Meatpacking District", 40.737, 40.744, -74.012, -74.002),
    ("Chelsea", 40.739, 40.759, -74.012, -73.990),
    ("Flatiron", 40.737, 40.749, -73.997, -73.979),
    ("Gramercy", 40.734, 40.752, -73.984, -73.971),
    # Murray Hill is east of Madison Ave; Midtown covers Times Sq / 7th Ave corridor
    ("Murray Hill", 40.744, 40.757, -73.983, -73.967),
    ("Turtle Bay", 40.748, 40.758, -73.975, -73.954),
    ("Midtown", 40.744, 40.769, -74.002, -73.981),
    ("Hell's Kitchen", 40.754, 40.772, -74.007, -73.990),
    ("Central Park", 40.764, 40.801, -73.982, -73.948),
    ("Upper West Side", 40.768, 40.805, -73.995, -73.948),
    ("Upper East Side", 40.759, 40.803, -73.971, -73.920),
    ("Morningside Heights", 40.800, 40.816, -73.970, -73.949),
    # East Harlem is east of Lenox/5th Ave (~-73.944)
    ("East Harlem", 40.789, 40.815, -73.946, -73.916),
    ("Harlem", 40.799, 40.840, -73.972, -73.943),
    ("Washington Heights", 40.835, 40.866, -73.950, -73.918),
    ("Inwood", 40.862, 40.882, -73.945, -73.910),
]

_NEIGHBORHOOD_CENTROIDS: list[tuple[str, float, float]] = [
    (name, (min_lat + max_lat) / 2, (min_lng + max_lng) / 2)
    for name, min_lat, max_lat, min_lng, max_lng in _NEIGHBORHOOD_BOUNDS
]


def neighborhood_from_coords(lat: float, lng: float) -> str:
    for name, min_lat, max_lat, min_lng, max_lng in _NEIGHBORHOOD_BOUNDS:
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return name
    best = min(
        _NEIGHBORHOOD_CENTROIDS,
        key=lambda item: math.hypot(lat - item[1], lng - item[2]),
    )
    return best[0]

MANHATTAN_BOUNDS = {
    "min_lat": 40.7000,
    "max_lat": 40.8800,
    "min_lng": -74.0200,
    "max_lng": -73.9100,
}


def is_in_manhattan_bounds(coordinates: Coordinates) -> bool:
    return (
        MANHATTAN_BOUNDS["min_lat"] <= coordinates.lat <= MANHATTAN_BOUNDS["max_lat"]
        and MANHATTAN_BOUNDS["min_lng"] <= coordinates.lng <= MANHATTAN_BOUNDS["max_lng"]
    )


def normalize_osm_feature(feature: dict) -> Place | None:
    tags = feature.get("tags", {})
    lat = feature.get("lat") or feature.get("center", {}).get("lat")
    lng = feature.get("lon") or feature.get("center", {}).get("lon")
    name = tags.get("name")
    if not name or lat is None or lng is None:
        return None
    coordinates = Coordinates(lat=float(lat), lng=float(lng))
    if not is_in_manhattan_bounds(coordinates):
        return None

    category = category_from_osm_tags(tags)
    if category is None:
        return None

    source_id = f"osm:{feature.get('type', 'node')}:{feature.get('id')}"
    normalized_tags = sorted(
        {
            str(value).lower().replace(" ", "_")
            for key, value in tags.items()
            if key in {"amenity", "tourism", "shop", "leisure", "cuisine", "historic"}
        }
    )
    hood = tags.get("addr:neighbourhood") or tags.get("addr:neighborhood") or neighborhood_from_coords(float(lat), float(lng))
    return Place(
        id=source_id.replace(":", "-"),
        name=name,
        category=category,
        coordinates=coordinates,
        neighborhood=hood,
        tags=normalized_tags,
        atmosphere_tags=[],
        opening_hours={"daily": ["08:00-22:00"]},
        price_level=1,
        rating=4.0,
        quality_signals={"local_value": 0.5, "crowd_risk": 0.4},
        source="osm",
        source_id=source_id,
        attribution="OpenStreetMap contributors",
        indoor=category not in {PlaceCategory.park, PlaceCategory.scenic},
    )


def normalize_nyc_open_data_row(row: dict) -> Place | None:
    name = row.get("dba") or row.get("name") or row.get("facility_name")
    lat = row.get("latitude")
    lng = row.get("longitude")
    if not name or not lat or not lng:
        return None
    coordinates = Coordinates(lat=float(lat), lng=float(lng))
    if not is_in_manhattan_bounds(coordinates):
        return None
    source_id = f"nyc-open-data:{row.get('camis') or row.get('objectid') or name.lower()}"
    cuisine = str(row.get("cuisine_description") or "").lower()
    tags = ["food"] if cuisine else []
    if cuisine:
        tags.append(cuisine.replace(" ", "_"))
    return Place(
        id=source_id.replace(":", "-"),
        name=name.title(),
        category=PlaceCategory.restaurant,
        coordinates=coordinates,
        neighborhood=row.get("boro", "Manhattan").title(),
        tags=tags,
        atmosphere_tags=["hungry"],
        opening_hours={"daily": ["08:00-22:00"]},
        price_level=2,
        rating=4.0,
        quality_signals={"local_value": 0.5, "crowd_risk": 0.4},
        source="nyc_open_data",
        source_id=source_id,
        attribution="NYC Open Data",
        indoor=True,
    )


def category_from_osm_tags(tags: dict) -> PlaceCategory | None:
    amenity = tags.get("amenity")
    tourism = tags.get("tourism")
    shop = tags.get("shop")
    leisure = tags.get("leisure")
    historic = tags.get("historic")
    if amenity in {"cafe", "coffee_shop"}:
        return PlaceCategory.cafe
    if amenity in {"restaurant", "fast_food", "food_court"}:
        return PlaceCategory.restaurant
    if amenity in {"library"} or shop == "books":
        return PlaceCategory.bookstore
    if tourism in {"museum", "gallery"}:
        return PlaceCategory.museum if tourism == "museum" else PlaceCategory.gallery
    if leisure in {"park", "garden"}:
        return PlaceCategory.park
    if historic or tourism in {"attraction", "viewpoint"}:
        return PlaceCategory.landmark
    return None


def dedupe_places(places: list[Place], distance_threshold_m: int = 45) -> list[Place]:
    buckets: dict[str, list[Place]] = defaultdict(list)
    for place in places:
        buckets[manhattan_grid_cell_id(place.coordinates)].append(place)

    deduped: list[Place] = []
    for bucket_places in buckets.values():
        for place in bucket_places:
            duplicate = next(
                (
                    existing
                    for existing in deduped
                    if existing.name.lower() == place.name.lower()
                    and haversine_m(existing.coordinates, place.coordinates) <= distance_threshold_m
                ),
                None,
            )
            if duplicate is None:
                deduped.append(place)
    return deduped

