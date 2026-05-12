# LinUCB Bandit — Design, Behaviour, and Expected Improvement

## Why a bandit?

Before the bandit, the exploration bonus in the scoring formula was a SHA-1 hash:

```
exploration = int(sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
```

This gives a pseudo-random value in [0, 1] seeded by `(context_note, place_ids)`. It introduces variety across repeated identical queries, but it has no memory — it cannot learn that a particular type of plan (e.g. `museum_medium` on a rainy curious day) reliably earns a high LLM score. Every request is treated as if it is the first.

The LinUCB bandit replaces this with a signal that starts similarly random, then becomes steadily more informed as the system processes requests.

---

## Architecture

```
Request arrives
│
├─ Beam search generates up to 80 candidate plans
│
├─ For each candidate (fast pass, no LLM):
│    ├─ score_itinerary()      → algorithmic_score
│    ├─ agent_panel_score()    → agent_approval  ←─── also feeds feature vector
│    └─ bandit.score_arm()     → exploration_bonus  (UCB score, replaces SHA-1)
│         context vector:
│           mood (6) · weather (4) · budget (3)
│           time_norm (1) · stimulation (1)
│           agent scores (5)     ← per-agent float from the simulated panel
│
├─ diversify() selects final 3 candidates
│
└─ For each of the 3 finalists (LLM pass):
     ├─ LLM critic reviews plan → critic.score
     └─ bandit.update(arm, x, reward)
           reward = 0.6 × critic.score + 0.4 × agent_approval
           arm    = "<primary_category>_<effort_tier>"
                    e.g.  "cafe_low", "museum_medium", "park_high"
```

The update uses Sherman-Morrison rank-1 updates to maintain `A⁻¹` without a matrix inversion at each step (O(d²) per update, d=20).

---

## Context vector (d = 20)

| Index | Feature | Notes |
|-------|---------|-------|
| 0–5 | Mood one-hot | calm / curious / hungry / social / focused / romantic |
| 6–9 | Weather one-hot | good / cloudy / wet (rain+snow) / extreme (cold+hot+windy) |
| 10–12 | Budget one-hot | low+free / medium / high |
| 13 | Time budget | `available_minutes / 300`, clipped to [0,1] |
| 14 | Stimulation | `(level − 1) / 4`, range [0,1] |
| 15–19 | Agent scores | mood_matcher / friction_guardian / comfort_scout / novelty_editor / budget_realist |

The agent scores in the feature vector are the key design choice. By including them, LinUCB learns statements like:

> "When `friction_guardian` approves (low effort) but `novelty_editor` does not (low category diversity), in a calm + short-time context, the LLM critic tends to score `cafe_low` plans higher than `park_medium`."

Without those agent features, the bandit can only track which archetypes do well per *user context*. With them it can track which archetypes do well per *combined user + agent-approval pattern*.

---

## Arms

An arm is a string `<primary_category>_<effort_tier>`:

- **primary_category** — plurality category across the plan's stops (cafe, museum, park, bookstore, restaurant, gallery, landmark, market, scenic)
- **effort_tier** — ratio of total walking distance to mobility radius: `low` (< 30 %), `medium` (30–70 %), `high` (> 70 %)

At cold start there are no arms. Each unique `(category, effort)` combination encountered creates a new arm with A=I, b=0. The expected number of active arms is ~15–25 for a city the size of Manhattan.

---

## Before vs After: exploration behaviour

| Property | SHA-1 hash (before) | LinUCB (after) |
|----------|-------------------|----------------|
| Cold start value | pseudo-random ≈ 0.5 | sigmoid(0 + α√(x·x)) ≈ **0.84** for typical x |
| Convergence | never — same seed → same value | decreases as A accumulates context observations |
| Variety across identical queries | yes (seed includes place IDs) | yes — exploration term remains non-zero until arm is very well observed |
| Learning | none | `θ·x` term grows toward learned expected reward |
| Agent feedback | none | agent scores are features → arm learns which agent patterns predict LLM scores |
| Persistent across requests | no | yes — weights saved to `app/data/bandit_weights.json` |

### Cold-start behaviour

On the very first request, no arm has been observed. The UCB score for any arm is:

```
sigmoid(0 + 0.8 × √(x · A_inv · x)) = sigmoid(0.8 × ‖x‖)
```

For a typical context vector with 6 active features in {0, 1} and 5 agent scores near 0.5–0.7:

```
‖x‖ ≈ √(6 × 1² + 1 × 0.4² + 1 × 0.5² + 5 × 0.65²) ≈ √(6 + 0.16 + 0.25 + 2.11) ≈ 2.94
UCB  ≈ sigmoid(0.8 × 2.94) ≈ sigmoid(2.35) ≈ 0.91
```

Cold-start exploration bonus ≈ **0.91**, slightly higher than the SHA-1 average of 0.5. This biases new plan types toward the top of the candidate list — exactly what you want before any feedback is available.

### After 10 reward updates

After 10 updates with rewards clustered around 0.75 (typical LLM score for a decent plan):

```
θ ≈ A⁻¹ b  →  θ·x ≈ 0.55–0.70
exploration term shrinks as A accumulates x_t x_t^T  →  ≈ 0.3–0.5
UCB ≈ sigmoid(0.7 + 0.4) ≈ sigmoid(1.1) ≈ 0.75
```

The score stabilises near the expected reward, and the exploration term contributes less. Plans that consistently earn high LLM scores in a given user context climb; plans that earn low scores are deprioritised without being eliminated (UCB guarantees they stay explorable).

### After 50–100 updates (mature behaviour)

At this point `θ·x` is a reliable predictor of LLM critique score. The exploration term has shrunk substantially for frequently seen context patterns. The bandit acts more like a learned lookup: "for a rainy, calm, low-budget user with high agent approval from comfort_scout, `bookstore_medium` consistently scores 0.78 with the LLM critic."

---

## LLM as reward oracle — validation loop

The LLM critic is called 3 times per request (once per finalist plan). Its score in [0, 1] is the primary reward signal. This means:

1. **Every request trains the bandit** with at most 3 high-quality reward observations.
2. The LLM's assessment of coherence, personalization, weather fit, and transitions becomes the bandit's ground truth for what "good" means.
3. **The bandit is not a replacement for the LLM** — it is a pre-filter that surfaces plans likely to earn high LLM scores, reducing the gap between the 80-candidate fast pass and what the LLM would have scored all 80 candidates.

Over time, the bandit shifts work from the LLM (slow, expensive) back to the algorithmic fast pass: plans that the bandit scores high are those the LLM has already validated in similar contexts. The LLM still runs on each finalist to catch novelty that the bandit has not yet seen.

### What the LLM validates but the bandit can miss (at cold start)

| LLM checks | Bandit representation |
|-----------|----------------------|
| Awkward stop transitions ("museum then rowdy bar") | Not in features; learned indirectly through repeated patterns |
| Venue-specific coherence | Captured in arm's arm_id (category + effort), not venue names |
| Weather risk for specific outdoor stops | Partially captured via weather feature × agent comfort_scout score |
| Free-text note alignment | Not in feature vector (note is too sparse to encode usefully) |

These gaps mean the LLM remains important for newly seen arm/context combinations where the bandit is still uncertain.

---

## Monitoring — `GET /api/admin/bandit-stats`

```json
{
  "alpha": 0.8,
  "feature_dim": 20,
  "arms": {
    "cafe_low":       {"n_updates": 47},
    "museum_medium":  {"n_updates": 31},
    "park_low":       {"n_updates": 28},
    "bookstore_low":  {"n_updates": 19},
    "restaurant_medium": {"n_updates": 12},
    "gallery_medium": {"n_updates": 3}
  }
}
```

`n_updates` is the number of times the arm's parameters were updated with a real LLM reward. Arms with fewer than ~10 updates are still mostly in exploration mode. Arms approaching 50+ have reliable θ estimates.

If one arm dominates (e.g. `park_low` at 200 updates and `gallery_medium` at 2), it suggests the diversity filter in `diversify()` is not surfacing enough gallery routes — worth investigating whether the OSM fetch is returning few gallery POIs.

---

## Limitations and future directions

- **No cross-session user identity**: all requests contribute to shared arm parameters, not per-user profiles. This is intentional for now (no login, no PII), but a user-specific cold-start layer would improve early-session quality.
- **Feature dimension is fixed at d=20**: adding new agent types or context dimensions requires re-initialising arm matrices (or extending with fresh columns, which changes the Sherman-Morrison update structure).
- **Reward is immediate, not delayed**: the bandit treats the LLM critique score as ground truth immediately. A user-facing accept/reject signal would be a richer reward, but requires feedback infrastructure.
- **`bandit_weights.json` is not transactional**: concurrent uvicorn workers writing to the same file could produce corrupt JSON. For multi-worker deployments, replace file persistence with a Redis key or atomic file swap.
