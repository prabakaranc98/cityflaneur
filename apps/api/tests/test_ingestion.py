from app.data.ingestion import dedupe_places, normalize_nyc_open_data_row, normalize_osm_feature


def test_normalize_osm_feature_maps_cafe():
    place = normalize_osm_feature(
        {
            "type": "node",
            "id": 1,
            "lat": 40.7359,
            "lon": -73.9911,
            "tags": {"name": "Test Coffee", "amenity": "cafe"},
        }
    )

    assert place is not None
    assert place.category == "cafe"
    assert place.attribution == "OpenStreetMap contributors"


def test_normalize_nyc_open_data_restaurant_row():
    place = normalize_nyc_open_data_row(
        {
            "camis": "123",
            "dba": "test diner",
            "latitude": "40.7359",
            "longitude": "-73.9911",
            "cuisine_description": "American",
            "boro": "Manhattan",
        }
    )

    assert place is not None
    assert place.name == "Test Diner"
    assert place.source == "nyc_open_data"


def test_dedupe_places_removes_same_name_nearby():
    place_a = normalize_osm_feature(
        {
            "type": "node",
            "id": 1,
            "lat": 40.7359,
            "lon": -73.9911,
            "tags": {"name": "Test Coffee", "amenity": "cafe"},
        }
    )
    place_b = normalize_osm_feature(
        {
            "type": "node",
            "id": 2,
            "lat": 40.73591,
            "lon": -73.9911,
            "tags": {"name": "Test Coffee", "amenity": "cafe"},
        }
    )

    assert place_a is not None and place_b is not None
    assert len(dedupe_places([place_a, place_b])) == 1

