# Candidate Recommendation and Planning Algorithms

The recommender should stay constraint-first: retrieval, routing, budget math, hours, and weather feasibility are explicit code paths. LLMs and agents should critique, enrich, and explain candidates rather than decide feasibility.

## Algorithm 1: Weighted Beam Search

Status: current baseline.

How it works:

- Filter feasible places by radius, budget, hours, and weather.
- Rank individual places by mood, interests, distance, crowd fit, weather, and quality.
- Expand 2-4 stop routes from strong starts.
- Score each route with algorithmic metrics, simulated agent approval, and a semantic critic.
- Diversify the final slate to exactly three options.

Why keep it:

- Fast enough for interactive use.
- Easy to debug.
- Good cold-start behavior before feedback volume exists.

Weak spots:

- Can miss better routes if the first stop is not high-ranked.
- Needs route-pair distance caching once real walking-network distance is added.

## Algorithm 2: Constrained Orienteering

Status: next serious planner to prototype.

Model the trip as an orienteering problem: maximize utility from visited places under time, walking, budget, and weather constraints.

Good fit for Cityflaneur:

- Time budget is central.
- Route order matters.
- Place utility can combine mood fit, novelty, quality, budget, and agent approval.
- It naturally handles 2-4 stop micro-itineraries.

Implementation path:

- Build a pairwise walking-distance matrix for candidate places plus user origin.
- Use a bounded search, dynamic programming, or prize-collecting TSP heuristic over the top 30-80 candidates.
- Keep hard constraints separate from soft utility.
- Return route utility plus explicit constraint diagnostics.

## Algorithm 3: Multi-Objective Local Search

Status: useful after distance and data quality improve.

Start with a valid route, then mutate it:

- Replace one stop.
- Swap route order.
- Shorten or lengthen dwell time.
- Swap indoor/outdoor stops based on weather.
- Replace expensive food stops under low-budget contexts.

Score with Pareto-style objectives:

- Feasibility.
- Context fit.
- Effort.
- Budget fit.
- Novelty.
- Diversity.
- Simulated agent approval.

Why it helps:

- Finds routes beam search can miss.
- Makes tradeoffs visible.
- Works well with simulation tests.

## Algorithm 4: Contextual Bandit Re-Ranker

Status: later, after feedback logging is real.

Use user/session feedback to tune final ordering, not candidate feasibility.

Inputs:

- Structured context: mood, weather, group mode, budget, radius, time.
- Route features: categories, neighborhoods, walking distance, indoor ratio, novelty, price mix.
- Feedback: save, dismiss, started, completed, rating, show calmer, more social, closer.

Why wait:

- Bandits need enough feedback volume.
- Early sparse feedback can overfit and make the system feel random.
- We first need stable event logging and replayable offline evaluation.

## Algorithm 5: Simulator-Guided MCTS

Status: research track.

Use Monte Carlo tree search where each action adds a stop, changes route order, or chooses a dwell profile. Simulated personas act as rollout judges.

Useful when:

- The catalog is much larger.
- We add boroughs and city expansion.
- We need to evaluate many possible route narratives, not just top ranked places.

Risk:

- More compute and more moving parts.
- The simulator can encode wrong preferences if not validated against real feedback.

## Recommended Sequence

1. Keep weighted beam search as the interactive baseline.
2. Add real walking-network distance and route geometry.
3. Prototype constrained orienteering behind the same `recommend_itineraries` interface.
4. Compare beam search vs. orienteering in simulation.
5. Add local search mutations if routes remain repetitive.
6. Add contextual bandit re-ranking only after feedback quality is good enough.
