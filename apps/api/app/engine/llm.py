from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.models.schemas import HyperContext, Place, WeatherCondition


@dataclass(frozen=True)
class LLMReview:
    score: float
    explanation: str
    caveats: list[str]
    provider: str


class ItineraryCritic(Protocol):
    def review(
        self,
        context: HyperContext,
        places: list[Place],
        metrics: dict[str, float],
    ) -> LLMReview:
        ...


class HeuristicSemanticCritic:
    """LLM boundary stand-in: deterministic semantic checks until a model provider is enabled."""

    provider = "heuristic_semantic_critic"

    def review(
        self,
        context: HyperContext,
        places: list[Place],
        metrics: dict[str, float],
    ) -> LLMReview:
        caveats: list[str] = []
        score = 0.72

        if metrics.get("duration_fit", 0) < 0.55:
            caveats.append("Semantic critic: this route may feel rushed for the stated time.")
            score -= 0.08
        if metrics.get("diversity", 0) < 0.55:
            caveats.append("Semantic critic: the stops may feel too similar.")
            score -= 0.05
        if context.weather in {WeatherCondition.rain, WeatherCondition.snow} and any(not place.indoor for place in places):
            caveats.append("Semantic critic: weather risk remains because one stop is outdoors.")
            score -= 0.07
        if metrics.get("context_fit", 0) > 0.70 and metrics.get("effort", 0) > 0.55:
            score += 0.10
        if metrics.get("novelty", 0) > 0.80:
            score += 0.04

        names = ", ".join(place.name for place in places)
        return LLMReview(
            score=round(max(0.0, min(1.0, score)), 4),
            explanation=f"Semantic critic checked coherence for {names}.",
            caveats=caveats,
            provider=self.provider,
        )


class OpenRouterItineraryCritic:
    provider = "openrouter_itinerary_critic"

    def __init__(self, fallback: ItineraryCritic | None = None) -> None:
        self.settings = get_settings()
        self.fallback = fallback or HeuristicSemanticCritic()

    def review(
        self,
        context: HyperContext,
        places: list[Place],
        metrics: dict[str, float],
    ) -> LLMReview:
        if not self.settings.openrouter_api_key:
            return self.fallback.review(context, places, metrics)

        payload = {
            "model": self.settings.openrouter_model,
            "temperature": 0.2,
            "max_tokens": 260,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Cityflaneur's itinerary critic. Return compact JSON only with "
                        "score between 0 and 1, explanation as one sentence, and caveats as a short array. "
                        "Critique coherence, personalization, weather fit, time fit, and awkward transitions. "
                        "Do not invent facts about venues."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "context": context.model_dump(mode="json"),
                            "places": [
                                {
                                    "name": place.name,
                                    "category": place.category.value,
                                    "neighborhood": place.neighborhood,
                                    "tags": place.tags,
                                    "atmosphere_tags": place.atmosphere_tags,
                                    "price_level": place.price_level,
                                    "indoor": place.indoor,
                                }
                                for place in places
                            ],
                            "metrics": metrics,
                        }
                    ),
                },
            ],
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "Cityflaneur",
                    },
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            score = float(parsed.get("score", 0.7))
            explanation = str(parsed.get("explanation", "OpenRouter critic checked coherence."))
            caveats = [str(caveat) for caveat in parsed.get("caveats", [])][:3]
            return LLMReview(
                score=round(max(0.0, min(1.0, score)), 4),
                explanation=explanation,
                caveats=caveats,
                provider=f"{self.provider}:{self.settings.openrouter_model}",
            )
        except Exception as exc:
            fallback = self.fallback.review(context, places, metrics)
            return LLMReview(
                score=fallback.score,
                explanation=f"{fallback.explanation} OpenRouter fallback used: {type(exc).__name__}.",
                caveats=fallback.caveats,
                provider=fallback.provider,
            )


def get_itinerary_critic() -> ItineraryCritic:
    settings = get_settings()
    if settings.enable_llm_adapters and settings.openrouter_api_key:
        return OpenRouterItineraryCritic()
    return HeuristicSemanticCritic()
