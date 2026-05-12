from app.data.seed import SEED_PLACES
from app.engine.geo import (
    build_grid_cells,
    grid_cell_bounds,
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
