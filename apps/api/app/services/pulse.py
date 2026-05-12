from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.models.schemas import NeighborhoodPulse, PulseItem


_TRIVIA_FALLBACK: dict[str, list[PulseItem]] = {
    "Union Square": [
        PulseItem(title="A civic crossroads", summary="Union Square mixes public gathering, transit access, greenmarket, books, and political life.", source="curated_trivia"),
        PulseItem(title="Greenmarket energy", summary="A strong fit for routes combining quick food, browsing, and people-watching around the park.", source="curated_trivia"),
    ],
    "Greenwich Village": [
        PulseItem(title="Small streets, dense culture", summary="Routes here work best with time to wander between short stops on the quiet side streets.", source="curated_trivia"),
    ],
    "East Village": [
        PulseItem(title="Late-night texture", summary="Casual dining, parks, and independent spots cluster tightly — ideal for food-led itineraries.", source="curated_trivia"),
    ],
    "Chelsea": [
        PulseItem(title="Gallery density", summary="Galleries, the High Line, and market-style food sit close together — well-suited for art loops.", source="curated_trivia"),
    ],
    "SoHo": [
        PulseItem(title="Cast-iron walking fabric", summary="Architecture, bookstores, and cafes blend without long transitions on its cobblestone grid.", source="curated_trivia"),
    ],
    "Upper West Side": [
        PulseItem(title="Low-friction calm", summary="Parks, books, cafes, and quieter museums cluster well — a strong area for calm routes.", source="curated_trivia"),
    ],
    "Midtown": [
        PulseItem(title="Public landmarks close together", summary="Short architecture and landmark routes work when the itinerary avoids overloading the user.", source="curated_trivia"),
    ],
    "Lower East Side": [
        PulseItem(title="Food and history layers", summary="Classic food stops paired with cultural or historic context make for layered LES routes.", source="curated_trivia"),
    ],
    "Flatiron": [
        PulseItem(title="Crossroads of ambition", summary="The Flatiron Building and Madison Square Park anchor routes mixing architecture, food, and park time.", source="curated_trivia"),
    ],
    "Nolita": [
        PulseItem(title="Compact and curated", summary="Nolita's tight blocks hold independent bookstores, specialty coffee, and quiet restaurant streets.", source="curated_trivia"),
    ],
    "Financial District": [
        PulseItem(title="History underfoot", summary="Stone Street, Battery Park, and the Oculus offer architecture and waterfront options below Chambers St.", source="curated_trivia"),
    ],
    "Tribeca": [
        PulseItem(title="Gallery-quiet streets", summary="Tribeca's cobblestone streets and converted lofts hold art spaces and relaxed brunch spots.", source="curated_trivia"),
    ],
    "Harlem": [
        PulseItem(title="Music and soul", summary="The Apollo Theater, Morningside Park, and soul food institutions anchor Harlem's cultural itineraries.", source="curated_trivia"),
    ],
    "Upper East Side": [
        PulseItem(title="Museum mile density", summary="The Met, Guggenheim, Frick, and Carl Schurz Park make the UES strong for culture and park routes.", source="curated_trivia"),
    ],
    "West Village": [
        PulseItem(title="Winding charm", summary="Irregular streets and a high density of bookstores, cafes, and restaurants make every block a potential stop.", source="curated_trivia"),
    ],
    "Central Park": [
        PulseItem(title="Urban release valve", summary="Bethesda Fountain, Sheep Meadow, and the Conservatory Garden offer very different moods within one park.", source="curated_trivia"),
    ],
    "Meatpacking District": [
        PulseItem(title="High Line access", summary="The Meatpacking District connects the High Line, Whitney Museum, and Chelsea in a short walkable arc.", source="curated_trivia"),
    ],
}


def build_neighborhood_pulses(neighborhoods: list[str], limit: int = 3) -> list[NeighborhoodPulse]:
    unique = list(dict.fromkeys(neighborhood for neighborhood in neighborhoods if neighborhood))
    return [build_neighborhood_pulse(neighborhood, limit=limit) for neighborhood in unique[:5]]


def build_neighborhood_pulse(neighborhood: str, limit: int = 3) -> NeighborhoodPulse:
    headlines = fetch_exa_headlines(neighborhood, limit=limit)
    settings = get_settings()
    if settings.enable_llm_adapters and settings.openrouter_api_key:
        trivia = fetch_llm_trivia(neighborhood)
    else:
        trivia = _TRIVIA_FALLBACK.get(
            neighborhood,
            [PulseItem(title="Neighborhood context", summary=f"{neighborhood}, Manhattan.", source="curated_trivia")],
        )
    sources = ["curated trivia"]
    if headlines:
        sources.append("Exa live web")
    if trivia and trivia[0].source == "llm_context":
        sources[0] = "LLM context"
    return NeighborhoodPulse(
        neighborhood=neighborhood,
        trivia=list(trivia)[:2],
        headlines=headlines,
        generated_at=datetime.utcnow(),
        source_note=" + ".join(sources),
    )


@lru_cache(maxsize=256)
def fetch_llm_trivia(neighborhood: str) -> tuple[PulseItem, ...]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        return ()
    system = (
        "You are a Manhattan neighborhood expert for Cityflaneur, an urban exploration app. "
        "Write 2 short, specific, useful insight cards about the given neighborhood for someone planning a walk today. "
        "Focus on the texture, rhythm, and best use of the area — not generic tourist facts. "
        "Return compact JSON only: {\"items\": [{\"title\": str, \"summary\": str}, ...]} "
        "Summaries should be one sentence, under 160 characters."
    )
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Cityflaneur",
                },
                json={
                    "model": settings.openrouter_model,
                    "temperature": 0.5,
                    "max_tokens": 220,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Neighborhood: {neighborhood}, Manhattan, NYC"},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        items = [
            PulseItem(
                title=str(item.get("title") or ""),
                summary=str(item.get("summary") or ""),
                source="llm_context",
            )
            for item in parsed.get("items", [])[:2]
            if item.get("title") and item.get("summary")
        ]
        return tuple(items) if items else ()
    except Exception:
        return ()


@lru_cache(maxsize=128)
def fetch_exa_headlines(neighborhood: str, limit: int = 3) -> tuple[PulseItem, ...]:
    settings = get_settings()
    if not settings.enable_live_pulse or not settings.exa_api_key:
        return ()
    query = f"{neighborhood} Manhattan NYC local news events culture food things to do"
    try:
        with httpx.Client(timeout=9.0) as client:
            response = client.post(
                "https://api.exa.ai/search",
                headers={
                    "x-api-key": settings.exa_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "numResults": limit,
                    "type": "auto",
                    "contents": {
                        "text": {"maxCharacters": 400, "includeHtmlTags": False},
                    },
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except Exception:
        return ()

    items: list[PulseItem] = []
    for result in results[:limit]:
        raw_text = result.get("text") or ""
        if isinstance(raw_text, dict):
            raw_text = raw_text.get("text") or ""
        summary = " ".join(str(raw_text).split())[:220] or "Recent neighborhood result from Exa."
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

