from __future__ import annotations

from datetime import datetime
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.models.schemas import NeighborhoodPulse, PulseItem


TRIVIA: dict[str, list[PulseItem]] = {
    "Union Square": [
        PulseItem(
            title="A civic crossroads",
            summary="Union Square has long mixed public gathering, transit access, markets, books, and political life.",
            source="curated_trivia",
        ),
        PulseItem(
            title="Greenmarket energy",
            summary="The area is a strong fit for routes that combine quick food, browsing, and people-watching.",
            source="curated_trivia",
        ),
    ],
    "Greenwich Village": [
        PulseItem(
            title="Small streets, dense culture",
            summary="Greenwich Village routes often work best when they leave time for wandering between short stops.",
            source="curated_trivia",
        ),
    ],
    "East Village": [
        PulseItem(
            title="Late-night texture",
            summary="The East Village is useful for food-led itineraries because casual dining, parks, and independent spots cluster tightly.",
            source="curated_trivia",
        ),
    ],
    "Chelsea": [
        PulseItem(
            title="Gallery density",
            summary="Chelsea is well suited for art loops because galleries, the High Line, and market-style food sit close together.",
            source="curated_trivia",
        ),
    ],
    "SoHo": [
        PulseItem(
            title="Cast-iron walking fabric",
            summary="SoHo routes can blend architecture, shopping streets, bookstores, and cafes without long transitions.",
            source="curated_trivia",
        ),
    ],
    "Upper West Side": [
        PulseItem(
            title="Low-friction calm",
            summary="The Upper West Side is a strong calm-route area because parks, books, cafes, and quieter museums cluster well.",
            source="curated_trivia",
        ),
    ],
    "Midtown": [
        PulseItem(
            title="Public landmarks close together",
            summary="Midtown can support short architecture and landmark routes when the itinerary avoids overloading the user.",
            source="curated_trivia",
        ),
    ],
    "Lower East Side": [
        PulseItem(
            title="Food and history layers",
            summary="Lower East Side picks work well when the route balances classic food stops with cultural or historic context.",
            source="curated_trivia",
        ),
    ],
}


def build_neighborhood_pulses(neighborhoods: list[str], limit: int = 3) -> list[NeighborhoodPulse]:
    unique = list(dict.fromkeys(neighborhood for neighborhood in neighborhoods if neighborhood))
    return [build_neighborhood_pulse(neighborhood, limit=limit) for neighborhood in unique[:5]]


def build_neighborhood_pulse(neighborhood: str, limit: int = 3) -> NeighborhoodPulse:
    headlines = fetch_exa_headlines(neighborhood, limit=limit)
    trivia = TRIVIA.get(
        neighborhood,
        [
            PulseItem(
                title="Neighborhood context",
                summary=f"{neighborhood} needs richer sourced data; using curated fallback context for now.",
                source="curated_trivia",
            )
        ],
    )
    source_note = "curated trivia"
    if headlines:
        source_note = "curated trivia + Exa live web search"
    return NeighborhoodPulse(
        neighborhood=neighborhood,
        trivia=trivia[:2],
        headlines=headlines,
        generated_at=datetime.utcnow(),
        source_note=source_note,
    )


@lru_cache(maxsize=128)
def fetch_exa_headlines(neighborhood: str, limit: int = 3) -> tuple[PulseItem, ...]:
    settings = get_settings()
    if not settings.enable_live_pulse or not settings.exa_api_key:
        return ()
    query = f"latest local news events culture food {neighborhood} Manhattan NYC"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                "https://api.exa.ai/search",
                headers={
                    "x-api-key": settings.exa_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "numResults": limit,
                    "text": True,
                    "type": "auto",
                    "category": "news",
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except Exception:
        return ()

    items: list[PulseItem] = []
    for result in results[:limit]:
        text = result.get("text") or result.get("summary") or ""
        summary = " ".join(text.split())[:220] or "Recent neighborhood result from Exa."
        published_at = parse_datetime(result.get("publishedDate"))
        items.append(
            PulseItem(
                title=result.get("title") or "Neighborhood update",
                summary=summary,
                url=result.get("url"),
                source="exa",
                published_at=published_at,
            )
        )
    return tuple(items)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

