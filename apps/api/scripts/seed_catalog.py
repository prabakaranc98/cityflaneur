from __future__ import annotations

from collections import Counter

from app.data.seed import SEED_PLACES
from app.engine.geo import manhattan_grid_cell_id


def main() -> None:
    categories = Counter(place.category.value for place in SEED_PLACES)
    neighborhoods = Counter(place.neighborhood for place in SEED_PLACES)
    grid_cells = {manhattan_grid_cell_id(place.coordinates) for place in SEED_PLACES}
    print(f"seed_places={len(SEED_PLACES)}")
    print(f"grid_cells={len(grid_cells)}")
    print("categories=" + ",".join(f"{key}:{value}" for key, value in categories.items()))
    print("top_neighborhoods=" + ",".join(f"{key}:{value}" for key, value in neighborhoods.most_common(8)))


if __name__ == "__main__":
    main()

