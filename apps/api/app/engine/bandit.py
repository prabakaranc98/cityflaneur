"""
LinUCB contextual bandit — learns which plan archetypes work for each user-context pattern.

Arms: "<primary_category>_<effort_tier>" strings  (e.g. "cafe_low", "museum_medium")

Context vector (d=28):
  mood one-hot       [6]   calm / curious / hungry / social / focused / romantic
  weather one-hot    [4]   good / cloudy / wet / extreme
  budget             [3]   low / medium / high
  time budget        [1]   available_minutes normalised to [0,1]
  stimulation        [1]   stimulation_level normalised to [0,1]
  agent scores       [5]   per-agent approval scores from the simulated panel
  profile            [8]   pace, social_comfort, familiarity, discovery,
                           mobility, spend_strictness, visitor_type, origin_region

Agent scores are context features so LinUCB learns which agents are predictive
of high LLM reward in each user-context situation — effectively learning the
per-context reliability of each simulated persona.

Reward: 0.6 × llm_critique + 0.4 × (agent_approval - sigma), fed back after LLM scoring.

A_inv is maintained via Sherman-Morrison rank-1 updates (no numpy required, O(d²) per step).
Arm parameters are persisted to JSON between requests so the bandit accumulates
experience across the lifetime of the server process.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.schemas import HyperContext

FEATURE_DIM: int = 28
ALPHA: float = 0.8  # UCB exploration coefficient; lower → more exploit, higher → more explore
_WEIGHTS_FILE = Path(__file__).parent.parent / "data" / "bandit_weights.json"

_AGENT_NAMES = [
    "mood_matcher",
    "friction_guardian",
    "comfort_scout",
    "novelty_editor",
    "budget_realist",
]


# ---------------------------------------------------------------------------
# Pure-Python matrix helpers (d ≤ 20, performance is not a concern)
# ---------------------------------------------------------------------------

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _mat_vec(M: list[list[float]], x: list[float]) -> list[float]:
    return [_dot(row, x) for row in M]


def _identity(d: int) -> list[list[float]]:
    return [[1.0 if i == j else 0.0 for j in range(d)] for i in range(d)]


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, z))))


# ---------------------------------------------------------------------------
# Core arm
# ---------------------------------------------------------------------------

class LinUCBArm:
    """
    One bandit arm.

    Maintains A_inv (inverse of A = I + sum x_t x_t^T) and b (= sum r_t x_t).
    The UCB score is sigmoid(theta·x + alpha * sqrt(x^T A_inv x)).
    Sherman-Morrison updates keep A_inv current without an explicit matrix inversion.
    """

    __slots__ = ("d", "A_inv", "b", "n_updates")

    def __init__(self, d: int) -> None:
        self.d = d
        self.A_inv: list[list[float]] = _identity(d)
        self.b: list[float] = [0.0] * d
        self.n_updates: int = 0

    def score(self, x: list[float], alpha: float) -> float:
        A_inv_x = _mat_vec(self.A_inv, x)
        theta = _mat_vec(self.A_inv, self.b)
        exploit = _dot(theta, x)
        explore = alpha * math.sqrt(max(0.0, _dot(x, A_inv_x)))
        return _sigmoid(exploit + explore)

    def update(self, x: list[float], reward: float) -> None:
        # Sherman-Morrison: A_inv ← A_inv − (A_inv x)(A_inv x)^T / (1 + x^T A_inv x)
        A_inv_x = _mat_vec(self.A_inv, x)
        denom = 1.0 + _dot(x, A_inv_x)
        for i in range(self.d):
            for j in range(self.d):
                self.A_inv[i][j] -= (A_inv_x[i] * A_inv_x[j]) / denom
        for i in range(self.d):
            self.b[i] += reward * x[i]
        self.n_updates += 1

    def to_dict(self) -> dict:
        return {"A_inv": self.A_inv, "b": self.b, "n_updates": self.n_updates}

    @classmethod
    def from_dict(cls, d: int, data: dict) -> "LinUCBArm":
        arm = cls(d)
        arm.A_inv = data["A_inv"]
        arm.b = data["b"]
        arm.n_updates = data.get("n_updates", 0)
        return arm


# ---------------------------------------------------------------------------
# Bandit — collection of arms with persistence
# ---------------------------------------------------------------------------

class LinUCBBandit:
    def __init__(self, alpha: float = ALPHA, d: int = FEATURE_DIM) -> None:
        self.alpha = alpha
        self.d = d
        self._arms: dict[str, LinUCBArm] = {}
        self._lock = Lock()
        self._load()

    def _arm(self, arm_id: str) -> LinUCBArm:
        if arm_id not in self._arms:
            self._arms[arm_id] = LinUCBArm(self.d)
        return self._arms[arm_id]

    def score_arm(self, arm_id: str, x: list[float]) -> float:
        """UCB score for an arm given context vector x, in (0, 1) via sigmoid."""
        return self._arm(arm_id).score(x, self.alpha)

    def update(self, arm_id: str, x: list[float], reward: float) -> None:
        """Record observed reward for arm; persists weights to disk."""
        with self._lock:
            self._arm(arm_id).update(x, reward)
            self._save()

    def arm_stats(self) -> dict[str, dict]:
        return {
            arm_id: {"n_updates": arm.n_updates}
            for arm_id, arm in self._arms.items()
        }

    def _load(self) -> None:
        try:
            raw = json.loads(_WEIGHTS_FILE.read_text())
            if raw.get("_version") != self.d:
                import logging
                logging.getLogger(__name__).warning(
                    "Bandit weights dimension mismatch (file=%s, expected=%d) — cold start",
                    raw.get("_version"), self.d,
                )
                return
            for arm_id, arm_data in raw.get("arms", {}).items():
                self._arms[arm_id] = LinUCBArm.from_dict(self.d, arm_data)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
            pass  # cold start — all arms initialise fresh on first access

    def _save(self) -> None:
        _WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"_version": self.d, "arms": {arm_id: arm.to_dict() for arm_id, arm in self._arms.items()}}
        _WEIGHTS_FILE.write_text(json.dumps(payload, separators=(",", ":")))


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

_bandit: LinUCBBandit | None = None
_bandit_init_lock = Lock()


def get_bandit() -> LinUCBBandit:
    global _bandit
    if _bandit is None:
        with _bandit_init_lock:
            if _bandit is None:
                _bandit = LinUCBBandit()
    return _bandit


# ---------------------------------------------------------------------------
# Feature encoding
# ---------------------------------------------------------------------------

def encode_context_and_agents(
    context: "HyperContext",
    agent_scores: dict[str, float],
) -> list[float]:
    """
    Build the 28-dim context feature vector.

    Combining user-level signals (mood, weather, budget, time, stimulation) with
    plan-level agent approval scores and flaneur profile lets the bandit learn which
    agent approval patterns are predictive of high LLM reward in each user situation.
    """
    from app.models.schemas import Budget, Mood, WeatherCondition

    moods = [Mood.calm, Mood.curious, Mood.hungry, Mood.social, Mood.focused, Mood.romantic]
    x: list[float] = [1.0 if context.mood == m else 0.0 for m in moods]  # [0:6]

    w = context.weather
    x += [
        1.0 if w == WeatherCondition.clear else 0.0,
        1.0 if w == WeatherCondition.cloudy else 0.0,
        1.0 if w in {WeatherCondition.rain, WeatherCondition.snow} else 0.0,
        1.0 if w in {WeatherCondition.cold, WeatherCondition.hot, WeatherCondition.windy} else 0.0,
    ]  # [6:10]

    x += [
        1.0 if context.budget in {Budget.free, Budget.low} else 0.0,
        1.0 if context.budget == Budget.medium else 0.0,
        1.0 if context.budget == Budget.high else 0.0,
    ]  # [10:13]

    x.append(min(1.0, context.available_minutes / 300.0))            # [13]
    x.append((context.stimulation_level - 1) / 4.0)                  # [14]

    for name in _AGENT_NAMES:
        x.append(float(agent_scores.get(f"agent_{name}", 0.5)))       # [15:20]

    # Profile dims [20:28] — defaults used when profile is None (skipped onboarding)
    p = context.profile
    x += [
        {"meander": 0.0, "moderate": 0.5, "purposeful": 1.0}.get(p.pace.value if p else "moderate", 0.5),
        {"introvert": 0.0, "ambivert": 0.5, "extrovert": 1.0}.get(p.social_comfort.value if p else "ambivert", 0.5),
        {"tourist": 0.0, "occasional": 0.5, "local": 1.0}.get(p.familiarity.value if p else "occasional", 0.5),
        {"serendipity": 0.0, "balanced": 0.5, "reliable": 1.0}.get(p.discovery.value if p else "balanced", 0.5),
        {"standard": 0.0, "prefers_flat": 0.5, "limited": 1.0}.get(p.mobility.value if p else "standard", 0.0),
        {"anything": 0.0, "conscious": 0.5, "strict": 1.0}.get(p.spend_strictness.value if p else "conscious", 0.5),
        {"resident": 0.0, "student": 0.33, "international_student": 0.67, "visitor": 1.0}.get(
            p.visitor_type.value if p else "resident", 0.0),
        {"local": 0.0, "north_america": 0.2, "europe": 0.4, "asia": 0.6, "latin_america": 0.8, "rest_of_world": 1.0}.get(
            p.origin_region.value if p else "local", 0.0),
    ]  # [20:28]

    return x  # len == FEATURE_DIM == 28


# ---------------------------------------------------------------------------
# Arm identification
# ---------------------------------------------------------------------------

def arm_id_for_places(
    places: list,
    total_walking_m: int,
    mobility_radius_m: int,
) -> str:
    """
    Derive archetype arm ID: <primary_category>_<effort_tier>.

    Primary category is the plurality category in the plan's stops.
    Effort tier (low / medium / high) is the ratio of total walking distance
    to the user's mobility radius — captures how far the plan stretches the user.
    """
    from collections import Counter

    cats: Counter = Counter(p.category.value for p in places)
    primary = cats.most_common(1)[0][0] if cats else "unknown"
    ratio = total_walking_m / max(mobility_radius_m, 1)
    effort = "low" if ratio < 0.3 else "high" if ratio > 0.7 else "medium"
    return f"{primary}_{effort}"
