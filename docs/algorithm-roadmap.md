# Algorithm, Agent, and LLM Roadmap

## Current Baseline

The current system is now inspectable but less hardwired:

- Rule-based context parsing.
- Hard filters for budget, hours, radius, and weather.
- Beam-style candidate route search across the feasible place catalog.
- Weighted scoring across context fit, effort, duration, budget, weather, personalization, quality, novelty, crowd fit, and diversity.
- Simulated agent panel approval for mood fit, friction, comfort, novelty, and budget realism.
- Semantic critic boundary that can be replaced by a real LLM provider.
- Persona simulation for regression checks.

This is the right cold-start baseline because the failure modes are visible. The main weaknesses are approximate walking distance, sparse data, simple budget handling, and limited personalization memory.

See [Planning Algorithms](planning-algorithms.md) for the concrete planner candidates to test next: constrained orienteering, multi-objective local search, contextual bandits, and simulator-guided search.

## Next Algorithmic Upgrades

1. Replace approximate walking distance with real walking-network distance.
   - Add OSRM, Valhalla, OpenRouteService, or a local OSMnx/networkx graph.
   - Store walking distance, duration, and route geometry per candidate pair.
   - Penalize street complexity, crossings, steepness where available, and bad-weather exposure.

2. Make budget a richer constraint.
   - Keep `budget` as the user-facing input.
   - Convert it into expected total cost, per-stop price constraints, and category-specific allowances.
   - Treat free public stops differently from paid museums and restaurants.

3. Use constraint-first ranking.
   - Hard constraints: open hours, reachable duration, weather safety, max budget.
   - Soft objectives: mood fit, novelty, crowd comfort, neighborhood texture, diversity.
   - Return caveats when the system relaxes a hard constraint.

4. Upgrade itinerary search.
   - Keep current beam search as the fast path.
   - Add evolutionary mutation over stop replacement, route order, indoor/outdoor swaps, and dwell time.
   - Add route-pair caches once a routing engine exists.
   - Fitness: feasibility first, then multi-objective utility plus agent approval.

5. Add online learning only after logging is reliable.
   - Start with aggregate policy weight tuning.
   - Move to contextual bandits once feedback volume is enough.
   - Use dismiss/save/start/complete signals with context snapshots.

## LLM Roles

Use LLMs in narrow places where language and semantic judgment help:

- Intent parser: convert optional text into structured mood, constraints, interests, and latent needs.
- Semantic tagger: enrich places with atmosphere, use-case, and caveat tags from trusted source descriptions.
- Critic: review candidate itineraries for coherence, awkward transitions, and human plausibility.
- Explainer: produce concise user-facing explanations after deterministic scoring chooses the slate.

Do not let the LLM own route feasibility, budget arithmetic, or source attribution.

## Agent Layer

Useful agents for the next version:

- Data QA agent: checks new source records for missing coordinates, broken hours, duplicate names, bad attribution, and suspicious categories.
- Simulation agent: runs persona cohorts across time, weather, budget, and mood, then reports regressions.
- Itinerary critic agent: reviews the top candidates from the optimizer and flags incoherent routes.
- Feedback analysis agent: clusters feedback by context and recommends scoring-weight changes.

Agent outputs should be logged as structured diagnostics, not silently applied to production recommendations.

## Evaluation Gates

Before expanding beyond Manhattan:

- 95% of returned options fit the requested time budget or include an explicit caveat.
- 95% of options have valid open-hour status or explicit unknown-hour caveat.
- 90% of rainy/snowy contexts return mostly indoor or rain-safe stops.
- Average walking estimate uses network distance, not straight-line distance.
- Simulated personas receive three diverse options across morning, afternoon, evening, and late-night contexts.
