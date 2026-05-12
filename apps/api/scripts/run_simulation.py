from __future__ import annotations

from datetime import datetime

from app.engine.context import parse_context
from app.engine.recommender import recommend_itineraries
from app.models.schemas import (
    Budget,
    ContextParseRequest,
    Coordinates,
    GroupMode,
    Mood,
    WeatherCondition,
)


PERSONAS = [
    ContextParseRequest(
        location=Coordinates(lat=40.7359, lng=-73.9911),
        available_minutes=90,
        mood=Mood.calm,
        weather=WeatherCondition.rain,
        budget=Budget.low,
        group_mode=GroupMode.solo,
        note="quiet and not too much effort",
        local_datetime=datetime(2026, 5, 12, 18, 0),
    ),
    ContextParseRequest(
        location=Coordinates(lat=40.7423, lng=-74.0060),
        available_minutes=120,
        mood=Mood.hungry,
        weather=WeatherCondition.clear,
        budget=Budget.medium,
        group_mode=GroupMode.group,
        note="food and some walking with friends",
        local_datetime=datetime(2026, 5, 12, 13, 0),
    ),
    ContextParseRequest(
        location=Coordinates(lat=40.8039, lng=-73.9630),
        available_minutes=150,
        mood=Mood.curious,
        weather=WeatherCondition.cloudy,
        budget=Budget.low,
        group_mode=GroupMode.pair,
        note="art, history, architecture, something not obvious",
        local_datetime=datetime(2026, 5, 12, 11, 0),
    ),
]


def run() -> list[dict]:
    results: list[dict] = []
    for persona in PERSONAS:
        context = parse_context(persona)
        recommendations = recommend_itineraries(context)
        results.append(
            {
                "mood": context.mood.value,
                "weather": context.weather.value,
                "count": len(recommendations),
                "top_score": recommendations[0].scores["total"],
                "titles": [option.title for option in recommendations],
            }
        )
    return results


def main() -> None:
    for result in run():
        print(result)


if __name__ == "__main__":
    main()

