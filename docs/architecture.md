# Cityflaneur Manhattan MVP Architecture

## Runtime Shape

The first implementation is a working prototype with a deterministic core path:

1. The Next.js interface collects location, optional browser GPS, time budget, weather, mood, budget, group mode, interests, and one optional note.
2. FastAPI normalizes that input into `HyperContext`.
3. The recommender hard-filters feasible Manhattan places, composes route templates, scores candidates, diversifies the slate, and returns exactly three options.
4. The UI renders the selected route with MapLibre and logs lightweight feedback events.

## Recommendation Layer

The optimizer is intentionally explicit:

- Hard filters: budget, open hours, walking radius, weather safety.
- Candidate composition: 2-4 stops from weighted beam search, interest-biased starts, route repair, and final slate diversification.
- Scores: context fit, effort, weather fit, quality, novelty, and diversity.
- LLM boundary: future LLMs can parse intent, critique coherence, and write explanations, but they should not own feasibility or ranking.

## Data Layer

V1 uses a seeded Manhattan catalog. The ingestion boundary supports:

- OpenStreetMap/Overpass for POIs.
- NYC Open Data/Socrata for restaurants, inspections, parks, cultural assets, and civic datasets.
- NWS weather for current/forecast context.
- Commercial providers only behind adapters with explicit attribution and cache policies.

PostgreSQL with PostGIS and pgvector is the intended persistent store. The current API uses the seed catalog while database migrations and models are ready for ingestion work.

## Expansion

The borough/city expansion path is data-first:

- Add a city/borough bounding profile.
- Ingest and dedupe source-specific POIs.
- Generate stable meter-based grid cells for retrieval and route-cache keys.
- Run simulation personas for the new geography.
- Enable the geography in the API only after the simulator returns three feasible options for the target contexts.
