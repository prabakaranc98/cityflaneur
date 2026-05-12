from __future__ import annotations

from app.core.config import get_settings
from app.data.seed import SEED_PLACES
from app.engine.llm import OpenRouterItineraryCritic
from app.models.schemas import Coordinates, HyperContext, Mood, WeatherCondition
from app.services.pulse import fetch_exa_headlines
from app.services.streetscapes import build_street_scenes


TEST_POINT = Coordinates(lat=40.7359, lng=-73.9911)


def main() -> None:
    settings = get_settings()
    print("Provider smoke test; secret values are not printed.")
    print(probe_openrouter(settings))
    print(probe_exa(settings))
    print(probe_streetscapes(settings))


def probe_openrouter(settings) -> str:
    if not settings.openrouter_api_key:
        return "openrouter: missing_key"
    if not settings.enable_llm_adapters:
        return "openrouter: key_present_flag_off"

    context = HyperContext(
        location=TEST_POINT,
        mood=Mood.curious,
        weather=WeatherCondition.clear,
    )
    metrics = {
        "duration_fit": 0.8,
        "diversity": 0.9,
        "context_fit": 0.8,
        "effort": 0.7,
        "novelty": 0.7,
    }
    review = OpenRouterItineraryCritic().review(context, SEED_PLACES[:2], metrics)
    status = "ok" if review.provider.startswith("openrouter_itinerary_critic") else "fallback"
    return f"openrouter: {status} provider={review.provider} score={review.score}"


def probe_exa(settings) -> str:
    if not settings.exa_api_key:
        return "exa: missing_key"
    if not settings.enable_live_pulse:
        return "exa: key_present_flag_off"

    fetch_exa_headlines.cache_clear()
    items = fetch_exa_headlines("Chelsea", limit=1)
    return f"exa: {'ok' if items else 'empty_or_failed'} results={len(items)}"


def probe_streetscapes(settings) -> str:
    if not settings.enable_streetscapes:
        return "streetscapes: disabled"
    response = build_street_scenes(TEST_POINT, limit=3)
    statuses = ",".join(
        f"{provider}={status}" for provider, status in sorted(response.provider_status.items())
    )
    return f"streetscapes: images={len(response.images)} {statuses}"


if __name__ == "__main__":
    main()
