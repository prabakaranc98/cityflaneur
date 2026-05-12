from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.data.ingestion import dedupe_places, normalize_osm_feature
from app.models.schemas import Place

logger = logging.getLogger(__name__)

_OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

_OVERPASS_QUERY_TEMPLATE = """[out:json][timeout:25];
(
  node["amenity"~"cafe|coffee_shop|restaurant|fast_food|food_court|library"]["name"](around:{radius},{lat},{lng});
  node["tourism"~"museum|gallery|attraction|viewpoint"]["name"](around:{radius},{lat},{lng});
  node["shop"="books"]["name"](around:{radius},{lat},{lng});
  node["leisure"~"park|garden"]["name"](around:{radius},{lat},{lng});
  node["historic"]["name"](around:{radius},{lat},{lng});
  way["amenity"~"cafe|restaurant|fast_food|library"]["name"](around:{radius},{lat},{lng});
  way["tourism"~"museum|gallery|attraction"]["name"](around:{radius},{lat},{lng});
  way["leisure"~"park|garden"]["name"](around:{radius},{lat},{lng});
  relation["leisure"~"park|garden"]["name"](around:{radius},{lat},{lng});
);
out center tags;"""

# Radius tiers in metres — query is cached per tier bucket
_RADIUS_TIERS = (1000, 1500, 2000, 3000, 4000, 5000)


def _cache_key(lat: float, lng: float, radius_m: float) -> tuple[float, float, int]:
    """Round to ~500m grid and snap radius to the next tier for cache locality."""
    lat_key = round(lat * 200) / 200   # 0.005° ≈ 500m
    lng_key = round(lng * 200) / 200
    tier = next((t for t in _RADIUS_TIERS if t >= radius_m), _RADIUS_TIERS[-1])
    return lat_key, lng_key, tier


_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "cityflaneur/1.0 (urban exploration app; contact: hello@cityflaneur.app)",
}


@lru_cache(maxsize=512)
def _fetch_overpass(lat_key: float, lng_key: float, radius_m: int) -> tuple[Place, ...]:
    """Single Overpass query for an area. Cached by approximate location + radius tier."""
    import urllib.parse
    query = _OVERPASS_QUERY_TEMPLATE.format(radius=radius_m, lat=lat_key, lng=lng_key)
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(_OVERPASS_ENDPOINT, content=body, headers=_HEADERS)
            response.raise_for_status()
            elements = response.json().get("elements", [])
    except Exception as exc:
        logger.warning("Overpass fetch failed (%.4f,%.4f r=%dm): %s", lat_key, lng_key, radius_m, exc)
        return ()

    places: list[Place] = []
    for element in elements:
        place = normalize_osm_feature(element)
        if place is not None:
            places.append(place)

    deduped = dedupe_places(places, distance_threshold_m=40)
    logger.info("Overpass: %d raw → %d deduped places (%.4f,%.4f r=%dm)", len(places), len(deduped), lat_key, lng_key, radius_m)
    return tuple(deduped)


def pois_for_context(lat: float, lng: float, radius_m: float) -> list[Place]:
    """Fetch POIs from OSM for the given location and radius. Results are cached."""
    lat_key, lng_key, tier = _cache_key(lat, lng, radius_m)
    return list(_fetch_overpass(lat_key, lng_key, tier))


def cache_info() -> dict[str, object]:
    info = _fetch_overpass.cache_info()
    return {"hits": info.hits, "misses": info.misses, "maxsize": info.maxsize, "currsize": info.currsize}
