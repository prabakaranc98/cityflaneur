from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.data.seed import SEED_PLACES
from app.engine.context import parse_context
from app.engine.geo import build_grid_cells, full_manhattan_grid
from app.engine.recommender import recommend_itineraries
from app.models.schemas import (
    ContextParseRequest,
    Coordinates,
    FeedbackEvent,
    FeedbackResponse,
    GridCellsResponse,
    HyperContext,
    NeighborhoodPulseResponse,
    PlaceCategory,
    PlacesResponse,
    RecommendationsResponse,
    StreetScenesResponse,
)
from app.services.feedback import feedback_store
from app.services.pulse import build_neighborhood_pulses
from app.services.streetscapes import build_street_scenes

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    from app.data.poi_cache import cache_info
    return {"status": "ok", "catalog_version": settings.default_catalog_version, "osm_cache": cache_info()}


@app.get("/api/admin/cache-info")
def cache_info_endpoint() -> dict[str, object]:
    from app.data.poi_cache import cache_info
    return cache_info()


@app.get("/api/admin/bandit-stats")
def bandit_stats_endpoint() -> dict[str, object]:
    """Return per-arm update counts for the LinUCB exploration bandit."""
    from app.engine.bandit import get_bandit
    bandit = get_bandit()
    return {"alpha": bandit.alpha, "feature_dim": bandit.d, "arms": bandit.arm_stats()}


@app.post("/api/context/parse", response_model=HyperContext)
def parse_context_endpoint(request: ContextParseRequest) -> HyperContext:
    return parse_context(request)


@app.post("/api/recommendations", response_model=RecommendationsResponse)
def recommendations_endpoint(context: HyperContext) -> RecommendationsResponse:
    return RecommendationsResponse(
        context=context,
        recommendations=recommend_itineraries(context),
        catalog_version=settings.default_catalog_version,
        generated_at=datetime.utcnow(),
    )


@app.post("/api/feedback", response_model=FeedbackResponse)
def feedback_endpoint(event: FeedbackEvent) -> FeedbackResponse:
    stored = feedback_store.append(event)
    return FeedbackResponse(accepted=True, stored_events=stored)


@app.get("/api/places", response_model=PlacesResponse)
def places_endpoint(
    q: str | None = Query(default=None, min_length=1),
    category: PlaceCategory | None = None,
    neighborhood: str | None = None,
    lat: float | None = Query(default=None, ge=40.68, le=40.89),
    lng: float | None = Query(default=None, ge=-74.05, le=-73.90),
    radius_m: int = Query(default=2000, ge=200, le=5000),
    limit: int = Query(default=100, ge=1, le=500),
) -> PlacesResponse:
    if lat is not None and lng is not None:
        from app.data.poi_cache import pois_for_context
        osm_places = pois_for_context(lat, lng, float(radius_m))
        places = osm_places if osm_places else SEED_PLACES
    else:
        places = SEED_PLACES
    if q:
        needle = q.lower()
        places = [
            place
            for place in places
            if needle in place.name.lower()
            or needle in place.neighborhood.lower()
            or needle in " ".join(place.tags + place.atmosphere_tags).lower()
        ]
    if category:
        places = [place for place in places if place.category == category]
    if neighborhood:
        places = [
            place for place in places if neighborhood.lower() in place.neighborhood.lower()
        ]
    limited = places[:limit]
    return PlacesResponse(places=limited, count=len(limited))


@app.get("/api/grid-cells", response_model=GridCellsResponse)
def grid_cells_endpoint() -> GridCellsResponse:
    cells = full_manhattan_grid()
    return GridCellsResponse(cells=cells, count=len(cells))


@app.get("/api/neighborhood-pulse", response_model=NeighborhoodPulseResponse)
def neighborhood_pulse_endpoint(
    neighborhoods: list[str] = Query(default=[]),
    limit: int = Query(default=3, ge=1, le=5),
) -> NeighborhoodPulseResponse:
    pulses = build_neighborhood_pulses(neighborhoods, limit=limit)
    return NeighborhoodPulseResponse(pulses=pulses, count=len(pulses))


@app.get("/api/streetscapes", response_model=StreetScenesResponse)
def streetscapes_endpoint(
    lat: float = Query(..., ge=40.68, le=40.89),
    lng: float = Query(..., ge=-74.05, le=-73.90),
    limit: int = Query(default=4, ge=1, le=8),
    heading: int | None = Query(default=None, ge=0, le=359),
) -> StreetScenesResponse:
    return build_street_scenes(Coordinates(lat=lat, lng=lng), limit=limit, heading=heading)
