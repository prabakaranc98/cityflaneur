from app.core.config import get_settings
from app.models.schemas import Coordinates
from app.services import streetscapes
from app.services.streetscapes import (
    build_street_scenes,
    google_static_streetview_url,
    mapillary_bbox,
    parse_mapillary_images,
)


def clear_settings_and_streetscape_caches():
    get_settings.cache_clear()
    streetscapes.fetch_mapillary_images.cache_clear()
    streetscapes.fetch_google_street_view.cache_clear()


def test_streetscapes_disabled_without_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_STREETSCAPES", "false")
    clear_settings_and_streetscape_caches()

    response = build_street_scenes(Coordinates(lat=40.7359, lng=-73.9911))

    assert response.images == []
    assert response.provider_status == {"streetscapes": "disabled"}


def test_streetscapes_reports_missing_provider_keys(monkeypatch):
    monkeypatch.setenv("ENABLE_STREETSCAPES", "true")
    monkeypatch.delenv("MAPILLARY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    clear_settings_and_streetscape_caches()

    response = build_street_scenes(Coordinates(lat=40.7359, lng=-73.9911))

    assert response.provider_status["mapillary"] == "missing_key"
    assert response.provider_status["google_street_view"] == "missing_key"


def test_mapillary_bbox_is_centered_on_location():
    bbox = mapillary_bbox(Coordinates(lat=40.7359, lng=-73.9911))

    assert bbox == "-73.991800,40.735200,-73.990400,40.736600"


def test_parse_mapillary_images_maps_payload_to_scene_image():
    images = parse_mapillary_images(
        {
            "data": [
                {
                    "id": "123",
                    "thumb_1024_url": "https://images.example/thumb.jpg",
                    "captured_at": 1_700_000_000_000,
                    "computed_geometry": {
                        "type": "Point",
                        "coordinates": [-73.9911, 40.7359],
                    },
                }
            ]
        }
    )

    assert len(images) == 1
    assert images[0].source == "mapillary"
    assert images[0].coordinates == Coordinates(lat=40.7359, lng=-73.9911)
    assert images[0].page_url == "https://www.mapillary.com/app/?pKey=123"


def test_google_static_streetview_url_contains_required_parameters():
    url = google_static_streetview_url(
        Coordinates(lat=40.7359, lng=-73.9911),
        "test-key",
        heading=91,
    )

    assert "maps.googleapis.com/maps/api/streetview" in url
    assert "location=40.735900%2C-73.991100" in url
    assert "heading=91" in url
    assert "key=test-key" in url
