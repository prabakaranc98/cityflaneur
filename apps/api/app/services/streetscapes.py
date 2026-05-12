from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.models.schemas import Coordinates, StreetSceneImage, StreetScenesResponse


MAPILLARY_RADIUS_DEGREES = 0.0007
MAPILLARY_FIELDS = ",".join(
    [
        "id",
        "captured_at",
        "computed_geometry",
        "thumb_1024_url",
        "thumb_2048_url",
        "quality_score",
    ]
)


def build_street_scenes(
    coordinates: Coordinates,
    limit: int = 4,
    heading: int | None = None,
) -> StreetScenesResponse:
    settings = get_settings()
    if not settings.enable_streetscapes:
        return StreetScenesResponse(
            query=coordinates,
            provider_status={"streetscapes": "disabled"},
            source_note="streetscapes disabled",
        )

    images: list[StreetSceneImage] = []
    provider_status: dict[str, str] = {}

    mapillary_images, mapillary_status = fetch_mapillary_images(
        coordinates.lat,
        coordinates.lng,
        limit=max(1, limit - 1),
    )
    provider_status["mapillary"] = mapillary_status
    images.extend(mapillary_images)

    google_image, google_status = fetch_google_street_view(
        coordinates.lat,
        coordinates.lng,
        heading=heading,
    )
    provider_status["google_street_view"] = google_status
    if google_image:
        images.append(google_image)

    providers = [name for name, status in provider_status.items() if status == "ok"]
    if providers:
        source_note = " + ".join(providers)
    else:
        source_note = "no street imagery returned"

    return StreetScenesResponse(
        query=coordinates,
        images=images[:limit],
        provider_status=provider_status,
        source_note=source_note,
    )


@lru_cache(maxsize=512)
def fetch_mapillary_images(lat: float, lng: float, limit: int = 3) -> tuple[tuple[StreetSceneImage, ...], str]:
    settings = get_settings()
    if not settings.mapillary_access_token:
        return (), "missing_key"

    coordinates = Coordinates(lat=lat, lng=lng)
    params = {
        "access_token": settings.mapillary_access_token,
        "fields": MAPILLARY_FIELDS,
        "bbox": mapillary_bbox(coordinates),
        "limit": str(limit),
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get("https://graph.mapillary.com/images", params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        return (), f"http_{exc.response.status_code}"
    except Exception:
        return (), "request_failed"

    images = tuple(parse_mapillary_images(payload, limit=limit))
    return images, "ok" if images else "empty"


def parse_mapillary_images(payload: dict, limit: int = 3) -> list[StreetSceneImage]:
    images: list[StreetSceneImage] = []
    for result in payload.get("data", [])[:limit]:
        image_url = result.get("thumb_2048_url") or result.get("thumb_1024_url")
        image_id = str(result.get("id") or "")
        if not image_id or not image_url:
            continue

        coordinates = parse_mapillary_coordinates(result.get("computed_geometry"))
        images.append(
            StreetSceneImage(
                id=f"mapillary:{image_id}",
                source="mapillary",
                title="Nearby street-level image",
                image_url=image_url,
                page_url=f"https://www.mapillary.com/app/?pKey={image_id}",
                coordinates=coordinates,
                captured_at=parse_mapillary_captured_at(result.get("captured_at")),
                attribution="Mapillary contributors",
            )
        )
    return images


def parse_mapillary_coordinates(geometry: dict | None) -> Coordinates | None:
    if not geometry or geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    try:
        return Coordinates(lat=float(coordinates[1]), lng=float(coordinates[0]))
    except (TypeError, ValueError):
        return None


def parse_mapillary_captured_at(value: int | str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def mapillary_bbox(coordinates: Coordinates) -> str:
    return ",".join(
        [
            f"{coordinates.lng - MAPILLARY_RADIUS_DEGREES:.6f}",
            f"{coordinates.lat - MAPILLARY_RADIUS_DEGREES:.6f}",
            f"{coordinates.lng + MAPILLARY_RADIUS_DEGREES:.6f}",
            f"{coordinates.lat + MAPILLARY_RADIUS_DEGREES:.6f}",
        ]
    )


@lru_cache(maxsize=512)
def fetch_google_street_view(
    lat: float,
    lng: float,
    heading: int | None = None,
) -> tuple[StreetSceneImage | None, str]:
    settings = get_settings()
    if not settings.google_maps_api_key:
        return None, "missing_key"

    coordinates = Coordinates(lat=lat, lng=lng)
    params = {
        "location": f"{coordinates.lat:.6f},{coordinates.lng:.6f}",
        "key": settings.google_maps_api_key,
        "source": "outdoor",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(
                "https://maps.googleapis.com/maps/api/streetview/metadata",
                params=params,
            )
            response.raise_for_status()
            metadata = response.json()
    except httpx.HTTPStatusError as exc:
        return None, f"http_{exc.response.status_code}"
    except Exception:
        return None, "request_failed"

    status = str(metadata.get("status") or "unknown").lower()
    if status != "ok":
        return None, status

    image_url = google_static_streetview_url(coordinates, settings.google_maps_api_key, heading=heading)
    location = metadata.get("location") or {}
    snapped = parse_google_coordinates(location) or coordinates
    title = "Google Street View"
    if metadata.get("date"):
        title = f"Google Street View · {metadata['date']}"

    return (
        StreetSceneImage(
            id=f"google:{metadata.get('pano_id') or coordinates.lat}:{coordinates.lng}",
            source="google_street_view",
            title=title,
            image_url=image_url,
            coordinates=snapped,
            captured_at=None,
            attribution=str(metadata.get("copyright") or "Google Street View"),
        ),
        "ok",
    )


def parse_google_coordinates(location: dict) -> Coordinates | None:
    try:
        return Coordinates(lat=float(location["lat"]), lng=float(location["lng"]))
    except (KeyError, TypeError, ValueError):
        return None


def google_static_streetview_url(
    coordinates: Coordinates,
    api_key: str,
    heading: int | None = None,
) -> str:
    params = {
        "size": "640x360",
        "location": f"{coordinates.lat:.6f},{coordinates.lng:.6f}",
        "fov": "85",
        "pitch": "0",
        "source": "outdoor",
        "key": api_key,
    }
    if heading is not None:
        params["heading"] = str(heading % 360)
    return f"https://maps.googleapis.com/maps/api/streetview?{urlencode(params)}"
