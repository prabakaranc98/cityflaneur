# Data Guide

## Current Data

V1 uses a curated seed catalog in `apps/api/app/data/seed.py` so the prototype works without provider keys or network ingestion.

Current seed snapshot:

- 24 Manhattan places.
- Stable 500m Manhattan grid cells generated from place coordinates.
- Categories: parks, landmarks, museums, cafes, bookstores, restaurants, scenic routes, markets, and galleries.
- Neighborhoods include Upper West Side, Midtown, East Village, Chelsea, Union Square, Greenwich Village, SoHo, Lower East Side, West Village, Bowery, and Meatpacking District.

Each `Place` includes:

- Stable `id`, `name`, `category`, coordinates, and neighborhood.
- Tags and atmosphere tags used by the recommender.
- Opening-hour windows.
- Price level from 0-4.
- Rating and simple quality signals.
- Source, source id, attribution, indoor/outdoor flag, and future embedding field.

## Intended Data Sources

Open-first sources:

- OpenStreetMap/Overpass for cafes, parks, museums, bookstores, landmarks, galleries, and pedestrian context.
- NYC Open Data/Socrata for restaurant inspection records, parks, cultural institutions, public facilities, street/plaza assets, and neighborhood/civic datasets.
- National Weather Service for point forecasts and weather context.
- OSM-compatible basemap tiles for rendering; the current frontend uses CARTO Voyager raster tiles with OpenStreetMap attribution.

Future commercial adapters:

- Google Places, Yelp, Foursquare, or similar providers can fill gaps in hours, ratings, reviews, and photos.
- They must stay behind provider adapters because attribution, caching, photo display, and review reuse rules differ by provider.
- Do not scrape reviews or photos.

Live context sources:

- Exa can power `/api/neighborhood-pulse` for recent neighborhood news, culture, food, and event context.
- The current fallback is curated trivia in `app/services/pulse.py`, so the product still works without a live key.
- Live pulse content is displayed as context, not as a hard recommendation constraint.

## Ingestion Shape

The ingestion layer should produce normalized `Place` records:

1. Fetch raw source records through a provider adapter.
2. Normalize source-specific fields into `Place`.
3. Bound records to Manhattan for V1.
4. Deduplicate by source id, name, and spatial proximity.
5. Enrich with category tags, atmosphere tags, price signals, hours, and quality signals.
6. Persist to Postgres/PostGIS with future pgvector embeddings.
7. Rebuild 500m grid-cell summaries used by retrieval, map overlays, routing caches, and simulation diagnostics.

The current helpers in `app/data/ingestion.py` already cover:

- Manhattan bounding checks.
- OSM feature normalization.
- NYC Open Data restaurant-style row normalization.
- Simple spatial/name dedupe.

## Data Quality Priorities

The next data pass should improve:

- Walking-network distance and route duration.
- Live or recently refreshed opening hours.
- Indoor/outdoor reliability.
- Price estimates.
- Crowd proxies.
- Photo and attribution handling.
- Richer tags for mood, effort, stimulation, and social fit.
