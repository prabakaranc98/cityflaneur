from __future__ import annotations

import json

import httpx

from app.core.config import get_settings
from app.models.schemas import (
    Budget,
    ContextParseRequest,
    Coordinates,
    GroupMode,
    HyperContext,
    Interest,
    Mood,
    WeatherCondition,
)


DEFAULT_LOCATION = Coordinates(lat=40.7359, lng=-73.9911)

MOOD_DEFAULT_INTERESTS: dict[Mood, list[Interest]] = {
    Mood.calm: [Interest.parks, Interest.books, Interest.cafes],
    Mood.curious: [Interest.art, Interest.history, Interest.architecture],
    Mood.hungry: [Interest.food, Interest.cafes],
    Mood.social: [Interest.food, Interest.cafes, Interest.art],
    Mood.focused: [Interest.books, Interest.cafes],
    Mood.romantic: [Interest.scenic, Interest.food, Interest.art],
}

NOTE_INTEREST_KEYWORDS: dict[Interest, tuple[str, ...]] = {
    Interest.food: ("food", "eat", "dinner", "lunch", "hungry", "snack", "restaurant"),
    Interest.cafes: ("coffee", "cafe", "espresso", "tea"),
    Interest.books: ("book", "read", "bookstore", "library"),
    Interest.parks: ("park", "green", "garden", "outside", "walk"),
    Interest.art: ("art", "gallery", "creative", "installation"),
    Interest.museums: ("museum", "exhibit", "collection"),
    Interest.architecture: ("architecture", "building", "street", "facade"),
    Interest.scenic: ("view", "river", "scenic", "sunset"),
    Interest.history: ("history", "historic", "old new york"),
}


def parse_context(request: ContextParseRequest) -> HyperContext:
    note = (request.note or "").strip()
    note_lower = note.lower()

    llm_signals: dict[str, object] = {}
    settings = get_settings()
    if note and settings.enable_llm_adapters and settings.openrouter_api_key:
        llm_signals = _llm_parse_note(note, settings.openrouter_api_key, settings.openrouter_model)

    mood = request.mood or _coerce_mood(llm_signals.get("mood")) or infer_mood(note_lower) or Mood.calm
    weather = request.weather or _coerce_weather(llm_signals.get("weather")) or infer_weather(note_lower) or WeatherCondition.clear

    interests = list(request.interests or [])
    llm_interests = [_coerce_interest(v) for v in (llm_signals.get("interests") or [])]
    rule_interests = infer_interests(note_lower)
    for interest in [*llm_interests, *rule_interests]:
        if interest and interest not in interests:
            interests.append(interest)
    if not interests:
        interests = list(MOOD_DEFAULT_INTERESTS[mood])

    stimulation_level = request.stimulation_level
    if stimulation_level is None:
        stimulation_level = int(llm_signals.get("stimulation", 0)) or (4 if mood in {Mood.social, Mood.hungry} else 2)
    stimulation_level = max(1, min(5, stimulation_level))

    budget = request.budget or _coerce_budget(llm_signals.get("budget_hint")) or Budget.low

    parsed_signals: dict[str, str | int | float | bool | list[str]] = {
        "source": "llm+rules" if llm_signals else "rules",
        "inferred_interests": [interest.value for interest in rule_interests],
    }
    if llm_signals:
        if llm_signals.get("avoid_crowded"):
            parsed_signals["avoid_crowded"] = True
        if llm_signals.get("avoid_touristy"):
            parsed_signals["avoid_touristy"] = True
    if note:
        parsed_signals["note_present"] = True

    return HyperContext(
        location=request.location or DEFAULT_LOCATION,
        available_minutes=request.available_minutes or 90,
        local_datetime=request.local_datetime,
        weather=weather,
        mood=mood,
        stimulation_level=stimulation_level,
        budget=budget,
        group_mode=request.group_mode or GroupMode.solo,
        mobility_radius_m=request.mobility_radius_m or 2600,
        interests=interests,
        note=note or None,
        parsed_signals=parsed_signals,
    )


def _llm_parse_note(note: str, api_key: str, model: str) -> dict[str, object]:
    system = (
        "You are a context parser for Cityflaneur, a Manhattan urban exploration app. "
        "Extract structured intent from the user's note. Return compact JSON only. "
        "Optional fields (omit what you cannot infer): "
        "mood (calm|curious|hungry|social|focused|romantic), "
        "interests (array of food|cafes|books|parks|art|museums|architecture|scenic|history), "
        "weather (clear|cloudy|rain|snow|cold|hot|windy), "
        "stimulation (integer 1-5, 1=very calm 5=very buzzy), "
        "budget_hint (free|low|medium|high), "
        "avoid_crowded (boolean), avoid_touristy (boolean)."
    )
    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Cityflaneur",
                },
                json={
                    "model": model,
                    "temperature": 0.1,
                    "max_tokens": 150,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": f'Note: "{note}"'},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return dict(json.loads(content))
    except Exception:
        return {}


def _coerce_mood(value: object) -> Mood | None:
    try:
        return Mood(str(value))
    except (ValueError, TypeError):
        return None


def _coerce_weather(value: object) -> WeatherCondition | None:
    try:
        return WeatherCondition(str(value))
    except (ValueError, TypeError):
        return None


def _coerce_interest(value: object) -> Interest | None:
    try:
        return Interest(str(value))
    except (ValueError, TypeError):
        return None


def _coerce_budget(value: object) -> Budget | None:
    try:
        return Budget(str(value))
    except (ValueError, TypeError):
        return None


def infer_mood(note_lower: str) -> Mood | None:
    if any(term in note_lower for term in ("calm", "quiet", "decompress", "chill", "stressed")):
        return Mood.calm
    if any(term in note_lower for term in ("curious", "explore", "learn", "weird", "interesting")):
        return Mood.curious
    if any(term in note_lower for term in ("hungry", "dinner", "lunch", "eat", "food")):
        return Mood.hungry
    if any(term in note_lower for term in ("friend", "group", "social", "date")):
        return Mood.social
    if any(term in note_lower for term in ("work", "focus", "study", "read")):
        return Mood.focused
    if any(term in note_lower for term in ("romantic", "date", "sunset")):
        return Mood.romantic
    return None


def infer_weather(note_lower: str) -> WeatherCondition | None:
    if "rain" in note_lower or "drizzle" in note_lower:
        return WeatherCondition.rain
    if "snow" in note_lower:
        return WeatherCondition.snow
    if "cold" in note_lower:
        return WeatherCondition.cold
    if "hot" in note_lower or "humid" in note_lower:
        return WeatherCondition.hot
    if "wind" in note_lower:
        return WeatherCondition.windy
    return None


def infer_interests(note_lower: str) -> list[Interest]:
    inferred: list[Interest] = []
    for interest, keywords in NOTE_INTEREST_KEYWORDS.items():
        if any(keyword in note_lower for keyword in keywords):
            inferred.append(interest)
    return inferred

