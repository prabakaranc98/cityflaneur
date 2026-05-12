# Cityflaneur

Cityflaneur is a Manhattan contextual urban recommendation system. Given a user's mood, budget, available time, weather, interests, GPS location, and flaneur profile, it generates exactly three walkable itineraries using a pipeline of algorithmic route search, a simulated multi-agent approval panel, Monte Carlo uncertainty estimation, and an LLM critic — all backed by live POI data fetched from OpenStreetMap.

## What We're Improving

Four layers that together make recommendations hyper-local, hyper-contextual, and hyper-personal:

| Layer | Problem before | What changed |
|---|---|---|
| 0 — Real-time weather + time | User manually picked weather chip; no time-of-day awareness | Auto-detect weather via OpenMeteo GPS fetch; rush-hour and sunset signals affect routing and scoring |
| 1 — Flaneur profile | All users got the same scoring weights | 7-question onboarding builds a `FlaneurProfile` (localStorage); includes visitor type + country of origin; bandit context vector expanded d=20→28 |
| 2 — Urban rhythm + seasonal | Crowd risk was a static field; seasonal venues always "open" | Rule-based crowd multiplier per neighborhood×hour×day-type; seasonal POI gate (Union Square Greenmarket, Governors Island, etc.) |
| 3 — Monte Carlo validation | Agent scores were point estimates; bandit reward was noisy | K=8 Monte Carlo over perturbed agent weights → μ±σ per plan; "74 fit ±6" on cards; bandit uses LCB reward |

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
σ     = sqrt((0.25 × agent_σ)² + (0.12 × 0.05)²)   — propagated from K=8 Monte Carlo agent samples
```

The displayed score is `total ± σ` (e.g. "74 fit ±6"). The bandit uses a lower confidence bound reward: `0.6 × llm_critique + 0.4 × max(0, agent_approval − agent_σ)` so uncertain arms are penalised.

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

For the final 3 plans, each agent score is also sampled K=8 times with Box-Muller weight perturbation (variance per agent per component is pre-tuned). This produces a σ per agent; the mean σ across agents becomes `agent_approval_sigma`, which is shown as the "Confidence" bar on each card. The bandit context vector is d=28: mood (6) + weather (4) + budget (3) + time/stimulation (2) + agent scores (5) + flaneur profile (8).

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

## Next Steps — Algorithmic

The current engine is functional but uses several approximations worth replacing as the system matures.

### Routing

**Real pedestrian routing** — walk times are currently haversine × 1.18 Manhattan grid bias. Plugging in [OSRM](https://project-osrm.org/) or [Valhalla](https://valhalla.github.io/valhalla/) would give exact sidewalk-aware travel times including one-way streets, park cuts, and bridge crossings. This is the single highest-leverage improvement to itinerary quality.

**Real transit data** — the subway model uses ~65 hardcoded station coordinates with a flat 500 m·min⁻¹ ride speed. Replacing this with live [MTA GTFS-RT](https://api.mta.info/) feeds would capture actual headways, transfers, and real-time delays. The leg-time formula is already structured for a drop-in replacement.

### Search

**Local search post-beam** — beam search is greedy: it never revisits a committed stop. A 2-opt or 3-opt local search pass over each candidate plan (swapping or removing stops) would escape greedy local optima without the exponential cost of full enumeration. The problem is a constrained variant of the [orienteering problem](https://en.wikipedia.org/wiki/Orienteering_problem); approximate solvers (LKH-style) can close 90% of the gap in milliseconds.

**Learned beam width** — fixed width-10 beams waste compute when the top-1 candidate is already dominant. A bandit over beam widths (4 / 10 / 20) could allocate compute to contexts where diversity matters (e.g. open-ended "surprise me" moods) and cut it for constrained contexts (strict budget + short window).

### Scoring

**Learned scoring weights** — the 11-component algorithmic weights (22% context fit, 16% effort, etc.) are hand-tuned. Even a small offline dataset of accepted vs. rejected plans would let a linear model or Bradley–Terry ranker recover weights that better reflect actual user preferences without any architectural change.

**Time-of-day POI scoring** — the engine currently gates places by opening hours but does not prefer cafes in the morning, lunch spots at noon, or bars after 18:00. A time-of-day multiplier over place categories (keyed to `context.available_minutes` + current hour) would surface more temporally coherent routes.

**Dynamic crowd signals** — `crowd_risk` is a static per-place label. Wikipedia pageview velocity, Foursquare check-in density, or OSM `crowd_source` tags could give a live proxy for expected busyness at a given time.

### Exploration and Diversity

**Contextual bandits** — the SHA-1 exploration bonus is purely pseudo-random. A contextual multi-armed bandit (e.g. LinUCB keyed on mood × time-of-day × neighborhood) would surface under-explored place combinations when the model is uncertain and exploit known-good routes when it is confident. This replaces the flat 5% exploration weight.

**Pareto-optimal slate selection** — the current three-plan diversity filter (no shared first stop, < 34% overlap) is a post-hoc deduplication heuristic. Treating plan selection as a submodular coverage problem — maximize joint diversity subject to each plan being individually good — would produce slates where the three options are maximally complementary across mood, effort, and category dimensions.

### Personalization

**Preference learning** — there is no feedback store yet. Adding a lightweight signal (accept / modify / reject on a returned itinerary) and training a collaborative filter or matrix factorization over (user, place_category, mood) tuples would let the engine cold-start on OSM tags and warm-start on observed choices.

**LLM-in-the-loop construction** — the LLM currently acts only as a post-hoc critic. A more active role — using the LLM to propose alternative first stops when the beam produces homogeneous routes, or to resolve soft constraints from the free-text note that rule-based parsing misses — would make the note field meaningfully affect plan structure, not just the critique text.

## Docs

- [Backend guide](docs/backend.md): API flow, recommendation logic, local spin-up, and validation.
- [Data guide](docs/data.md): OSM ingestion, seed catalog, grid design, and data quality.
- [Bandit guide](docs/bandit.md): LinUCB design, before/after comparison, LLM reward loop, and monitoring.
- [Algorithm roadmap](docs/algorithm-roadmap.md): planned improvements to scoring, routing, and personalization.
- [Planning algorithms](docs/planning-algorithms.md): beam search, orienteering, bandits, and simulator-guided planning notes.
- [Architecture](docs/architecture.md): runtime shape and expansion path.
