from app.data.seed import SEED_PLACES
from app.engine.geo import (
    build_grid_cells,
    full_manhattan_grid,
    grid_cell_bounds,
    grid_cells_in_radius,
    haversine_m,
    manhattan_grid_cell_id,
    manhattan_grid_indices,
)
from app.models.schemas import Coordinates


def test_manhattan_grid_id_is_stable_for_nearby_points():
    origin = Coordinates(lat=40.7359, lng=-73.9911)
    nearby = Coordinates(lat=40.7361, lng=-73.9910)

    assert manhattan_grid_cell_id(origin) == manhattan_grid_cell_id(nearby)


def test_grid_bounds_are_even_meter_cells():
    coordinates = Coordinates(lat=40.7359, lng=-73.9911)
    x_index, y_index = manhattan_grid_indices(coordinates)
    bounds = grid_cell_bounds(x_index, y_index)

    assert len(bounds) == 4
    horizontal_m = haversine_m(bounds[0], bounds[1])
    vertical_m = haversine_m(bounds[1], bounds[2])
    assert 475 <= horizontal_m <= 525
    assert 475 <= vertical_m <= 525


def test_grid_cells_include_index_metadata_and_exact_bounds():
    cells = build_grid_cells(SEED_PLACES)

    assert cells
    assert all(cell.cell_size_m == 500 for cell in cells)
    assert all(len(cell.bounds) == 4 for cell in cells)
    assert all(cell.id.startswith("mnh-500m-") for cell in cells)


def test_full_manhattan_grid_covers_entire_island():
    cells = full_manhattan_grid()
    assert len(cells) >= 1000  # ~1080 cells in the bounding box
    assert all(cell.cell_size_m == 500 for cell in cells)
    assert all(cell.id.startswith("mnh-500m-") for cell in cells)
    # All cells should be within Manhattan lat/lng bounds
    lats = [cell.center.lat for cell in cells]
    lngs = [cell.center.lng for cell in cells]
    assert min(lats) >= 40.68
    assert max(lats) <= 40.89
    assert min(lngs) >= -74.06
    assert max(lngs) <= -73.90


def test_grid_cells_in_radius_returns_plausible_count():
    origin = Coordinates(lat=40.7359, lng=-73.9911)
    cells_2km = grid_cells_in_radius(origin, 2000)
    cells_500m = grid_cells_in_radius(origin, 500)

    # 2km radius should include many more cells than 500m
    assert len(cells_2km) > len(cells_500m)
    # 500m radius should include at least the origin cell
    assert len(cells_500m) >= 1
    # All returned cell IDs should be unique
    ids = [c[2] for c in cells_2km]
    assert len(ids) == len(set(ids))
