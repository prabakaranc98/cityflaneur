from app.engine.context import parse_context
from app.models.schemas import ContextParseRequest, Interest, Mood, WeatherCondition


def test_parse_context_infers_mood_weather_and_interests_from_note():
    context = parse_context(
        ContextParseRequest(note="Rainy day, I want quiet books and coffee")
    )

    assert context.weather == WeatherCondition.rain
    assert context.mood == Mood.calm
    assert Interest.books in context.interests
    assert Interest.cafes in context.interests


def test_parse_context_uses_mood_defaults_when_interests_empty():
    context = parse_context(ContextParseRequest(mood=Mood.hungry))

    assert Interest.food in context.interests
    assert context.available_minutes == 90

