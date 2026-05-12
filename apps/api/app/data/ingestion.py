from __future__ import annotations

from collections import defaultdict

from app.engine.geo import haversine_m, manhattan_grid_cell_id
from app.models.schemas import Coordinates, Place, PlaceCategory

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
    return Place(
        id=source_id.replace(":", "-"),
        name=name,
        category=category,
        coordinates=coordinates,
        neighborhood=tags.get("addr:neighbourhood", "Manhattan"),
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

