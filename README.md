# Cityflaneur

Cityflaneur is a Manhattan-first contextual urban recommendation prototype. It turns a mostly structured user context and optional browser GPS start point into exactly three walkable micro-itineraries using explicit constraints, algorithmic route search, simulated agent approval, and a semantic critic boundary for future LLM enrichment.

## Stack

- `apps/api`: FastAPI, Pydantic, SQLAlchemy, Alembic, seeded Manhattan catalog, recommendation engine, ingestion adapters, simulation scripts.
- `apps/web`: Next.js, React, TypeScript, MapLibre GL JS, map-first bento interface.
- `infra/postgres`: PostgreSQL image with PostGIS and pgvector support.
- `docker-compose.yml`: Postgres, Redis, API, and web services.

## Local Development

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`

Backend-only:

```bash
cd apps/api
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
```

Frontend-only:

```bash
cd apps/web
npm install
npm run dev
```

If the system Python is older than 3.11, use `uv` for the backend:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv run --python 3.11 --extra dev uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## API

- `POST /api/context/parse`: normalizes bento choices and optional notes into `HyperContext`.
- `POST /api/recommendations`: returns three scored Manhattan itinerary options.
- `POST /api/feedback`: records anonymous session feedback in the prototype store.
- `GET /api/places`: searches the seeded/debug POI catalog.
- `GET /api/grid-cells`: returns stable 500m Manhattan grid summaries for map overlays and future indexing.
- `GET /api/neighborhood-pulse`: returns curated trivia plus optional Exa live web results for selected neighborhoods.

## Data Posture

The prototype ships with a curated seed catalog so the app works immediately. Provider boundaries are in place for OpenStreetMap/Overpass, NYC Open Data/Socrata, NWS weather, and future commercial place providers. Commercial review/photo providers must remain adapter-based because attribution, caching, and licensing rules differ by source.

Optional keys:

- `OPENROUTER_API_KEY` + `ENABLE_LLM_ADAPTERS=true`: real LLM itinerary critique.
- `EXA_API_KEY` + `ENABLE_LIVE_PULSE=true`: live neighborhood pulse/headline context.

## Validation

```bash
make api-test
make simulation
make seed-snapshot
```

The simulator runs representative Manhattan personas across mood, weather, budget, and group context to catch obvious recommendation failures before a real pilot.

## Docs

- [Backend guide](docs/backend.md): API flow, recommendation logic, local spin-up, and validation.
- [Data guide](docs/data.md): current seed data, intended sources, ingestion path, and data quality priorities.
- [Algorithm roadmap](docs/algorithm-roadmap.md): distance, budget, optimization, LLM, and agent next steps.
- [Planning algorithms](docs/planning-algorithms.md): beam search, orienteering, local search, bandits, and simulator-guided planning candidates.
- [Architecture](docs/architecture.md): high-level runtime shape and expansion path.
