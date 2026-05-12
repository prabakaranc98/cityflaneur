from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.schemas import HyperContext, Mood, WeatherCondition


@dataclass(frozen=True)
class AgentProfile:
    name: str
    threshold: float
    weights: dict[str, float]


AGENT_PANEL: tuple[AgentProfile, ...] = (
    AgentProfile(
        name="mood_matcher",
        threshold=0.58,
        weights={"context_fit": 0.45, "personalization": 0.25, "weather_fit": 0.12, "quality": 0.10, "effort": 0.08},
    ),
    AgentProfile(
        name="friction_guardian",
        threshold=0.62,
        weights={"effort": 0.42, "duration_fit": 0.24, "budget_fit": 0.16, "weather_fit": 0.10, "quality": 0.08},
    ),
    AgentProfile(
        name="comfort_scout",
        threshold=0.60,
        weights={"weather_fit": 0.32, "crowd_fit": 0.26, "effort": 0.18, "context_fit": 0.16, "quality": 0.08},
    ),
    AgentProfile(
        name="novelty_editor",
        threshold=0.56,
        weights={"novelty": 0.34, "diversity": 0.26, "context_fit": 0.20, "quality": 0.12, "effort": 0.08},
    ),
    AgentProfile(
        name="budget_realist",
        threshold=0.64,
        weights={"budget_fit": 0.46, "effort": 0.18, "duration_fit": 0.16, "quality": 0.12, "weather_fit": 0.08},
    ),
)


AGENT_WEIGHT_VARIANCE: dict[str, dict[str, float]] = {
    "mood_matcher":      {"context_fit": 0.06, "personalization": 0.04, "weather_fit": 0.02, "quality": 0.02, "effort": 0.02},
    "friction_guardian": {"effort": 0.05, "duration_fit": 0.04, "budget_fit": 0.03, "weather_fit": 0.02, "quality": 0.01},
    "comfort_scout":     {"weather_fit": 0.05, "crowd_fit": 0.04, "effort": 0.03, "context_fit": 0.02, "quality": 0.01},
    "novelty_editor":    {"novelty": 0.05, "diversity": 0.04, "context_fit": 0.03, "quality": 0.02, "effort": 0.01},
    "budget_realist":    {"budget_fit": 0.06, "effort": 0.03, "duration_fit": 0.02, "quality": 0.02, "weather_fit": 0.01},
}


def _box_muller(mu: float, sigma: float) -> float:
    """Box-Muller transform for a single N(mu, sigma) sample — pure Python."""
    import random
    u1 = max(1e-15, random.random())
    u2 = random.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mu + sigma * z


def monte_carlo_agent_score(
    profile: AgentProfile,
    context: HyperContext,
    metrics: dict[str, float],
    K: int = 8,
) -> tuple[float, float]:
    """Return (mean, std_dev) of K agent scores with perturbed weights."""
    variances = AGENT_WEIGHT_VARIANCE.get(profile.name, {})
    samples: list[float] = []
    for _ in range(K):
        perturbed: dict[str, float] = {}
        for metric, w in profile.weights.items():
            sigma = variances.get(metric, 0.0)
            perturbed[metric] = max(0.0, _box_muller(w, sigma))
        # Renormalise so weights still sum to ~1
        total = sum(perturbed.values()) or 1.0
        perturbed = {k: v / total for k, v in perturbed.items()}
        score = sum(metrics.get(m, 0.0) * w for m, w in perturbed.items())
        score = min(1.0, max(0.0, score + context_adjustment(context, profile.name)))
        samples.append(score)
    mu = sum(samples) / K
    variance = sum((s - mu) ** 2 for s in samples) / K
    return mu, math.sqrt(variance)


def agent_panel_score(
    context: HyperContext,
    metrics: dict[str, float],
    run_mc: bool = False,
    mc_k: int = 8,
) -> dict[str, float]:
    profile_scores: dict[str, float] = {}
    approvals = 0
    weighted_total = 0.0
    total_weight = 0.0
    sigma_sum = 0.0

    for profile in AGENT_PANEL:
        if run_mc:
            score, sigma = monte_carlo_agent_score(profile, context, metrics, K=mc_k)
            profile_scores[f"agent_{profile.name}_sigma"] = round(sigma, 4)
            sigma_sum += sigma
        else:
            score = sum(metrics.get(metric, 0.0) * weight for metric, weight in profile.weights.items())
            score = min(1.0, max(0.0, score + context_adjustment(context, profile.name)))
        profile_scores[f"agent_{profile.name}"] = round(score, 4)
        if score >= profile.threshold:
            approvals += 1
        influence = agent_influence(context, profile.name)
        weighted_total += score * influence
        total_weight += influence

    approval_rate = approvals / len(AGENT_PANEL)
    weighted_average = weighted_total / max(total_weight, 1e-9)
    result = {
        **profile_scores,
        "agent_approval": round((approval_rate * 0.45) + (weighted_average * 0.55), 4),
        "agent_approval_count": float(approvals),
    }
    if run_mc:
        result["agent_approval_sigma"] = round(sigma_sum / len(AGENT_PANEL), 4)
    return result


def context_adjustment(context: HyperContext, agent_name: str) -> float:
    if agent_name == "comfort_scout" and context.weather in {
        WeatherCondition.rain,
        WeatherCondition.snow,
        WeatherCondition.cold,
        WeatherCondition.hot,
    }:
        return 0.03
    if agent_name == "novelty_editor" and context.mood in {Mood.curious, Mood.romantic}:
        return 0.035
    if agent_name == "friction_guardian" and context.available_minutes <= 75:
        return 0.03
    if agent_name == "budget_realist" and context.budget.value in {"free", "low"}:
        return 0.035
    return 0.0


def agent_influence(context: HyperContext, agent_name: str) -> float:
    if agent_name == "comfort_scout" and context.stimulation_level <= 2:
        return 1.35
    if agent_name == "novelty_editor" and context.stimulation_level >= 4:
        return 1.35
    if agent_name == "budget_realist" and context.budget.value in {"free", "low"}:
        return 1.25
    if agent_name == "mood_matcher":
        return 1.15
    return 1.0

