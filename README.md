# Cityflaneur

Cityflaneur is a Manhattan contextual urban recommendation system. Given a user's mood, budget, available time, weather, interests, and GPS location, it generates exactly three walkable itineraries using a pipeline of algorithmic route search, a simulated multi-agent approval panel, and an LLM critic — all backed by live POI data fetched from OpenStreetMap.

## Stack

- `apps/api`: FastAPI 3.11, Pydantic v2, uv. Recommendation engine, OSM Overpass ingestion, LLM adapters, agent simulation.
- `apps/web`: Next.js 14 App Router, TypeScript, MapLibre GL JS, Mapillary JS SDK. Map-first bento interface with interactive 360° street view.

## How Recommendations Work

### 1. Context parsing

`POST /api/context/parse` accepts structured bento inputs (mood, weather, budget, time, interests, group mode) plus an optional free-text note. When `ENABLE_LLM_ADAPTERS=true`, the note is parsed by an LLM (via OpenRouter) to extract signals like stimulation level, avoidance preferences, and implied interests. LLM signals augment rule-based parsing; explicit UI choices always override.

### 2. Live POI loading

When a recommendation request arrives, the engine fetches all named points of interest within the user's mobility radius from the **OpenStreetMap Overpass API** in a single query. Results are normalized into `Place` objects (category, coordinates, neighborhood, price level) and LRU-cached by location so repeat requests in the same area are instant. A curated seed catalog of ~55 Manhattan places acts as fallback if Overpass is unavailable or returns fewer than 8 results. Manhattan is partitioned into a full 1,080-cell 500 m grid (the `/api/grid-cells` response), which drives the map overlay and spatial filtering.

### 3. Candidate plan generation — beam search

Feasible places (within radius, within budget, currently open) are ranked by a multi-factor individual score:

| Weight | Factor |
|--------|--------|
| 32 % | Mood fit (tag matching against mood needles) |
| 26 % | Interest fit |
| 18 % | Proximity |
| 12 % | Weather fit (indoor preference in rain/snow) |
| 7 % | Crowd risk |
| 5 % | Quality rating |

The top 18 places seed a **beam search**: starting from each candidate first stop, routes of 2–4 stops are expanded greedily, keeping the 10 best partial routes at each step. Interest-anchored beams are run separately for each declared interest. After deduplication, up to 80 candidate plans are kept.

### 4. Transit-aware travel time

Walk legs are not estimated as straight-line walking. For each leg the engine computes:

```
travel_time = min(
    walk_time,                                            # haversine × 1.18 grid bias / 80 m·min⁻¹
    walk_to_station + 2 min wait + ride_at_500 m·min⁻¹  # subway if station within 600 m of both ends
)
```

~65 named subway stations are indexed; the nearest one to each stop is shown in the itinerary as a badge. Walk legs > 700 m that have a faster subway option display a "subway ~X min via StationName" hint.

### 5. Scoring — four-signal composite

Each candidate plan is scored without calling the LLM (fast pass). The final shortlist of three is then sent to the LLM critic — keeping the total LLM calls to 3 per request regardless of how many candidates were generated.

```
total = 0.58 × algorithmic  +  0.25 × agent_approval  +  0.12 × llm_critique  +  0.05 × exploration
```

**Algorithmic score** (deterministic, fast):

| Weight | Component |
|--------|-----------|
| 22 % | Context fit (mood + interest tag overlap) |
| 16 % | Effort (walk distance vs. mobility radius) |
| 13 % | Duration fit (time budget adherence) |
| 12 % | Budget fit |
| 11 % | Weather fit |
| 10 % | Personalization (note token matching) |
| 7 % | Place quality |
| 5 % | Novelty (local value signal) |
| 3 % | Diversity (category spread) |
| 4 % | Template bias |
| 1 % | Crowd fit |

**Agent approval** — five simulated personas vote on each plan:

| Agent | Vetoes if… |
|-------|-----------|
| `mood_matcher` | context fit < 0.45 |
| `friction_guardian` | walk effort > 0.85 |
| `comfort_scout` | rain + outdoor stop |
| `novelty_editor` | all stops in same category |
| `budget_realist` | a stop exceeds budget cap |

Approval score = fraction of agents approving × 0.8, plus bonuses for unanimous approval.

**LLM critique** — OpenRouter (default: `openai/gpt-4o-mini`) receives context, place list, and computed metrics. It returns a 0–1 coherence score plus plain-language caveats that are appended to the itinerary. Falls back to a deterministic heuristic critic if no API key is set.

**Exploration bonus** — a SHA-1-derived pseudo-random value seeded by context + route, ensuring identical contexts still occasionally surface less-obvious combinations.

The three highest-scoring plans after diversity filtering (no shared first stop, < 34 % place overlap) are returned.

### 6. Neighborhood pulse

`GET /api/neighborhood-pulse` returns up to two trivia cards per neighborhood. With `ENABLE_LLM_ADAPTERS=true`, cards are generated dynamically by the LLM with neighborhood-specific walking texture. With `ENABLE_LIVE_PULSE=true`, Exa live web search appends recent local headlines.

### 7. Street-level imagery

`GET /api/streetscapes` returns Mapillary community photos and Google Street View statics near each stop. The frontend renders an interactive Mapillary 360° panorama directly on the map when a stop marker is clicked (using the `mapillary-js` WebGL SDK). Google Street View statics serve as supplementary coverage.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Status + OSM cache hit/miss stats |
| `POST /api/context/parse` | Normalize bento inputs + LLM note parsing → `HyperContext` |
| `POST /api/recommendations` | Live OSM fetch → beam search → agent + LLM scoring → 3 itineraries |
| `GET /api/places` | Search POIs by location/radius (live OSM) or keyword (seed fallback) |
| `GET /api/grid-cells` | Full 1,080-cell Manhattan 500 m grid for map overlay |
| `GET /api/neighborhood-pulse` | LLM trivia + Exa live headlines per neighborhood |
| `GET /api/streetscapes` | Mapillary photos + Google Street View static near coordinates |
| `GET /api/admin/cache-info` | Overpass LRU cache statistics |

## Configuration

Copy `.env.example` to `.env`. All external integrations are off by default.

| Variable | Feature |
|----------|---------|
| `OPENROUTER_API_KEY` + `ENABLE_LLM_ADAPTERS=true` | LLM itinerary critique, note parsing, neighborhood trivia generation |
| `EXA_API_KEY` + `ENABLE_LIVE_PULSE=true` | Live neighborhood headlines via Exa web search |
| `MAPILLARY_ACCESS_TOKEN` + `ENABLE_STREETSCAPES=true` | Mapillary community street photos |
| `GOOGLE_MAPS_API_KEY` + `ENABLE_STREETSCAPES=true` | Google Street View static fallback |

## Local Development

Backend (requires Python 3.11+, recommended via `uv`):

```bash
cd apps/api
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
uv run pytest
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Then open `http://localhost:3000` (web) and `http://localhost:8000/health` (API).

## Tests

```bash
cd apps/api
uv run pytest                          # 32 unit tests, ~3 min
uv run pytest tests/test_live_apis.py  # live integration suite (requires API keys)
uv run python scripts/test_providers.py  # provider smoke test
```

The simulator runs representative Manhattan personas across mood, weather, budget, and group context combinations to catch recommendation failures before deployment.

## Docs

- [Backend guide](docs/backend.md): API flow, recommendation logic, local spin-up, and validation.
- [Data guide](docs/data.md): OSM ingestion, seed catalog, grid design, and data quality.
- [Algorithm roadmap](docs/algorithm-roadmap.md): planned improvements to scoring, routing, and personalization.
- [Planning algorithms](docs/planning-algorithms.md): beam search, orienteering, bandits, and simulator-guided planning notes.
- [Architecture](docs/architecture.md): runtime shape and expansion path.
