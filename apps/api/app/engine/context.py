from __future__ import annotations

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
    mood = request.mood or infer_mood(note_lower) or Mood.calm
    weather = request.weather or infer_weather(note_lower) or WeatherCondition.clear
    interests = request.interests or []

    inferred_interests = infer_interests(note_lower)
    for interest in inferred_interests:
        if interest not in interests:
            interests.append(interest)
    if not interests:
        interests = list(MOOD_DEFAULT_INTERESTS[mood])

    stimulation_level = request.stimulation_level
    if stimulation_level is None:
        stimulation_level = 4 if mood in {Mood.social, Mood.hungry} else 2

    parsed_signals: dict[str, str | int | float | bool | list[str]] = {
        "source": "rules",
        "inferred_interests": [interest.value for interest in inferred_interests],
    }
    if note:
        parsed_signals["note_present"] = True

    return HyperContext(
        location=request.location or DEFAULT_LOCATION,
        available_minutes=request.available_minutes or 90,
        local_datetime=request.local_datetime,
        weather=weather,
        mood=mood,
        stimulation_level=stimulation_level,
        budget=request.budget or Budget.low,
        group_mode=request.group_mode or GroupMode.solo,
        mobility_radius_m=request.mobility_radius_m or 2600,
        interests=interests,
        note=note or None,
        parsed_signals=parsed_signals,
    )


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

