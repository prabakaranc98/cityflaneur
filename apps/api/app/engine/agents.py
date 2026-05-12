from __future__ import annotations

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


def agent_panel_score(context: HyperContext, metrics: dict[str, float]) -> dict[str, float]:
    profile_scores: dict[str, float] = {}
    approvals = 0
    weighted_total = 0.0
    total_weight = 0.0

    for profile in AGENT_PANEL:
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
    return {
        **profile_scores,
        "agent_approval": round((approval_rate * 0.45) + (weighted_average * 0.55), 4),
        "agent_approval_count": float(approvals),
    }


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

