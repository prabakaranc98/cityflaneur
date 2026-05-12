# Backend Guide

## What Runs

The backend is a FastAPI service in `apps/api`. It currently runs as a deterministic prototype over a seeded Manhattan place catalog, while the database, ingestion, and provider boundaries are ready for the next data-loading phase.

Runtime entry point:

- `app/main.py`: FastAPI app, CORS, and public API routes.
- `app/models/schemas.py`: API and domain models.
- `app/engine/context.py`: normalizes bento selections and optional notes into `HyperContext`.
- `app/engine/recommender.py`: filters places, generates candidate routes, scores options, and returns three itineraries.
- `app/engine/agents.py`: simulated persona panel for approval/rating.
- `app/engine/llm.py`: semantic critic boundary; currently deterministic, ready for an LLM provider.
- `app/services/pulse.py`: neighborhood trivia and optional Exa-powered live pulse.
- `app/data/seed.py`: current Manhattan seed catalog.
- `app/data/ingestion.py`: normalization helpers for future OSM and NYC Open Data rows.
- `app/data/providers.py`: source adapter boundaries for OSM, NYC Open Data, NWS weather, and commercial providers.
- `scripts/run_simulation.py`: persona simulation smoke test.

## API Flow

1. The web app submits bento selections and optional text to `POST /api/context/parse`.
2. The browser can fill `location` from GPS when the user allows it and the coordinate is inside the Manhattan MVP bounds.
3. The parser fills defaults, infers simple signals from text, deduplicates interests, and returns `HyperContext`.
4. The web app submits `HyperContext` to `POST /api/recommendations`.
5. The recommender applies hard filters for budget, hours, radius, and weather, then relaxes constraints only if the slate would otherwise be empty.
6. Candidate search generates many 2-4 stop routes using beam expansion, interest starts, walking-distance estimates, and time-budget repair.
7. Each candidate is scored algorithmically, rated by simulated agents, checked by the semantic critic, and then diversified.
8. The API returns exactly three `ItineraryOption` records when enough catalog data exists.
9. User actions post to `POST /api/feedback`; the prototype stores feedback in memory.

## Current Recommendation Logic

Hard filters:

- `price_level <= budget cap`
- `is_place_open(place, local_datetime)`
- straight-line distance from user location within `mobility_radius_m`
- indoor/rain-safe preference under rain or snow

Composition:

- Beam search starts from top-scoring places and expands route sequences.
- Interest-specific starts bias the search toward the user’s selected interests.
- Stop count is based on available time.
- Short trips are repaired with closer 2-stop pairs.
- If strict filters starve the catalog, a relaxed fallback widens distance and price by one level, then adds caveats.

Scoring:

- Algorithmic score: context fit, effort, duration fit, budget fit, weather fit, personalization, quality, novelty, diversity, and crowd fit.
- Agent approval: five simulated reviewers score mood fit, friction, comfort, novelty, and budget realism.
- Semantic critic: deterministic LLM-boundary check for coherence, repeated stops, weather mismatch, and rushed itineraries.
- Exploration bonus: small deterministic tie-breaker from context and candidate route so the slate is less repetitive.

Known limitation: distance is currently an approximate Manhattan walking estimate. The next production step should replace this with walking-network distance and duration from a routing engine.

## Location and Grid Indexing

Location:

- `HyperContext.location` is the route origin.
- The web UI supports browser geolocation through `navigator.geolocation`.
- V1 accepts GPS only inside Manhattan bounds because the seeded catalog and coordinate schema are Manhattan-first.
- Out-of-bounds GPS is shown as a UI status and the existing start point is preserved.

Grid:

- `app/engine/geo.py` projects Manhattan coordinates onto a local meter grid.
- Grid cell IDs use stable 500m keys such as `mnh-500m-012-009`.
- `GET /api/grid-cells` returns the exact cell bounds, center, index coordinates, place count, top categories, and neighborhoods.
- These IDs are ready to become retrieval/cache keys for place search, route-pair distances, weather exposure, and simulation diagnostics.

## Spin Up

Docker path:

```bash
cp .env.example .env
docker compose up --build
```

Local backend path:

```bash
cd apps/api
uv run --python 3.11 --extra dev uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Validation:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv run --python 3.11 --extra dev pytest
UV_CACHE_DIR=.uv-cache uv run --python 3.11 --extra dev python scripts/run_simulation.py
UV_CACHE_DIR=.uv-cache uv run --python 3.11 --extra dev python scripts/seed_catalog.py
```

Useful endpoints:

- `GET /health`
- `POST /api/context/parse`
- `POST /api/recommendations`
- `GET /api/places`
- `GET /api/grid-cells`
- `GET /api/neighborhood-pulse?neighborhoods=Chelsea&neighborhoods=SoHo`
- `POST /api/feedback`

## Optional API Keys

OpenRouter:

- Set `OPENROUTER_API_KEY`.
- Set `ENABLE_LLM_ADAPTERS=true`.
- Optional: set `OPENROUTER_MODEL`, default `openai/gpt-4o-mini`.
- Used for the itinerary semantic critic. If the call fails, the deterministic critic is used.

Exa:

- Set `EXA_API_KEY`.
- Set `ENABLE_LIVE_PULSE=true`.
- Used by `/api/neighborhood-pulse` for current neighborhood headlines/events.
- If no key is present, the endpoint returns curated local trivia only.
