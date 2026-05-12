from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha1

from app.data.seed import SEED_PLACES
from app.engine.agents import agent_panel_score
from app.engine.geo import (
    category_matches,
    haversine_m,
    route_distance_m,
    route_geometry,
    walking_route_distance_m,
    walking_minutes,
)
from app.engine.llm import get_itinerary_critic
from app.engine.time import effective_datetime, is_place_open
from app.models.schemas import (
    Budget,
    HyperContext,
    Interest,
    ItineraryOption,
    ItineraryStop,
    Mood,
    Place,
    PlaceCategory,
    WeatherCondition,
)


BUDGET_MAX_PRICE = {
    Budget.free: 0,
    Budget.low: 2,
    Budget.medium: 3,
    Budget.high: 4,
}

DWELL_MINUTES = {
    PlaceCategory.cafe: 30,
    PlaceCategory.bookstore: 30,
    PlaceCategory.park: 25,
    PlaceCategory.gallery: 30,
    PlaceCategory.museum: 45,
    PlaceCategory.restaurant: 45,
    PlaceCategory.landmark: 25,
    PlaceCategory.market: 40,
    PlaceCategory.scenic: 25,
}

INTEREST_TO_NEEDLE = {
    Interest.food: "food",
    Interest.cafes: "cafe",
    Interest.books: "books",
    Interest.parks: "park",
    Interest.art: "art",
    Interest.museums: "museum",
    Interest.architecture: "architecture",
    Interest.scenic: "scenic",
    Interest.history: "history",
}

MOOD_NEEDLES: dict[Mood, tuple[str, ...]] = {
    Mood.calm: ("calm", "quiet", "low_stimulation", "park", "books"),
    Mood.curious: ("curious", "art", "history", "architecture", "museum"),
    Mood.hungry: ("hungry", "food", "cafe", "market", "comfort"),
    Mood.social: ("social", "lively", "market", "food", "art"),
    Mood.focused: ("focused", "books", "cafe", "low_stimulation"),
    Mood.romantic: ("romantic", "scenic", "classic", "art"),
}


@dataclass(frozen=True)
class Template:
    title: str
    needles: tuple[str, ...]
    roles: tuple[str, ...]
    mood_bias: tuple[Mood, ...] = ()


@dataclass(frozen=True)
class CandidatePlan:
    places: tuple[Place, ...]
    roles: tuple[str, ...]
    strategy: str
    search_seed: str


TEMPLATES: tuple[Template, ...] = (
    Template(
        title="Quiet Reset",
        needles=("books", "cafe", "park"),
        roles=("browse", "settle", "decompress"),
        mood_bias=(Mood.calm, Mood.focused),
    ),
    Template(
        title="Art and Coffee Loop",
        needles=("art", "cafe", "museum"),
        roles=("look", "pause", "go deeper"),
        mood_bias=(Mood.curious, Mood.social),
    ),
    Template(
        title="Low-Friction Food Walk",
        needles=("food", "park", "cafe"),
        roles=("eat", "walk it off", "finish light"),
        mood_bias=(Mood.hungry, Mood.social),
    ),
    Template(
        title="Street Texture Walk",
        needles=("architecture", "history", "cafe"),
        roles=("notice", "connect", "pause"),
        mood_bias=(Mood.curious, Mood.romantic),
    ),
    Template(
        title="Rain-Proof Browse",
        needles=("museum", "books", "cafe"),
        roles=("take cover", "browse", "warm up"),
        mood_bias=(Mood.calm, Mood.focused, Mood.curious),
    ),
    Template(
        title="Scenic Date Drift",
        needles=("scenic", "food", "art"),
        roles=("walk", "share", "linger"),
        mood_bias=(Mood.romantic, Mood.social),
    ),
)


def recommend_itineraries(
    context: HyperContext,
    places: list[Place] | None = None,
    limit: int = 3,
) -> list[ItineraryOption]:
    catalog = places or SEED_PLACES
    candidates = feasible_places(context, catalog)
    if len(candidates) < 6:
        candidates = relaxed_feasible_places(context, catalog)

    plans = generate_candidate_plans(context, candidates)
    options = [option for plan in plans if (option := build_option_from_plan(context, plan)) is not None]

    options.sort(key=lambda option: option.scores["total"], reverse=True)
    diverse = diversify(options, limit)
    if len(diverse) < limit:
        diverse.extend(fallback_options(context, candidates, limit - len(diverse), diverse))
    return diverse[:limit]


def generate_candidate_plans(context: HyperContext, candidates: list[Place]) -> list[CandidatePlan]:
    if len(candidates) < 2:
        return []

    ranked = sorted(
        candidates,
        key=lambda place: individual_place_score(context, place, context.location)
        + exploration_value(context, place.id) * 0.06,
        reverse=True,
    )[:18]

    plans: list[CandidatePlan] = []
    for stop_count in target_stop_counts(context.available_minutes):
        for first in ranked[:12]:
            plans.extend(expand_route_beam(context, ranked, first, stop_count))

    for interest in context.interests:
        needle = INTEREST_TO_NEEDLE[interest]
        starts = [place for place in ranked if category_matches(place, needle)]
        for start in starts[:4]:
            plans.extend(expand_route_beam(context, ranked, start, min(3, target_stop_count(context.available_minutes)), needle))

    deduped: dict[tuple[str, ...], CandidatePlan] = {}
    for plan in plans:
        key = tuple(place.id for place in plan.places)
        reversed_key = tuple(reversed(key))
        if key not in deduped and reversed_key not in deduped:
            deduped[key] = plan

    return sorted(
        deduped.values(),
        key=lambda plan: plan_seed_score(context, plan),
        reverse=True,
    )[:80]


def expand_route_beam(
    context: HyperContext,
    ranked: list[Place],
    first: Place,
    stop_count: int,
    strategy_hint: str | None = None,
) -> list[CandidatePlan]:
    beams: list[tuple[Place, ...]] = [(first,)]
    max_duration = context.available_minutes + 25
    max_leg = max(900, context.mobility_radius_m * 0.72)

    for _ in range(1, stop_count):
        expanded: list[tuple[float, tuple[Place, ...]]] = []
        for route in beams:
            cursor = route[-1].coordinates
            for place in ranked:
                if place.id in {existing.id for existing in route}:
                    continue
                if haversine_m(cursor, place.coordinates) > max_leg and len(route) > 1:
                    continue
                new_route = (*route, place)
                if duration_for_places(context, list(new_route)) > max_duration:
                    continue
                expanded.append((route_seed_value(context, new_route), new_route))
        expanded.sort(key=lambda item: item[0], reverse=True)
        beams = [route for _, route in expanded[:10]]
        if not beams:
            break

    plans: list[CandidatePlan] = []
    for route in beams:
        if len(route) >= 2:
            strategy = strategy_hint or infer_strategy(context, list(route))
            roles = tuple(role_for_stop(context, place, index, len(route)) for index, place in enumerate(route))
            plans.append(
                CandidatePlan(
                    places=route,
                    roles=roles,
                    strategy=strategy,
                    search_seed=stable_search_seed(context, route, strategy),
                )
            )
    return plans


def build_option_from_plan(context: HyperContext, plan: CandidatePlan) -> ItineraryOption | None:
    selected = list(plan.places)
    if len(selected) < 2:
        return None

    distance_m = walking_route_distance_m(context.location, [place.coordinates for place in selected])
    duration = walking_minutes(distance_m) + sum(DWELL_MINUTES[place.category] for place in selected)
    if duration > context.available_minutes + 35:
        repaired = repair_short_route_from_places(context, selected)
        if repaired is None:
            return None
        selected = repaired
        distance_m = walking_route_distance_m(context.location, [place.coordinates for place in selected])
        duration = walking_minutes(distance_m) + sum(DWELL_MINUTES[place.category] for place in selected)

    metrics = score_itinerary(context, selected, distance_m)
    agents = agent_panel_score(context, metrics)
    critic = get_itinerary_critic().review(context, selected, metrics)
    exploration = route_exploration_bonus(context, selected, plan.search_seed)
    algorithmic_score = metrics["algorithmic_score"]
    total = (
        0.58 * algorithmic_score
        + 0.25 * agents["agent_approval"]
        + 0.12 * critic.score
        + 0.05 * exploration
    )
    scores = {
        **metrics,
        **agents,
        "llm_critique": critic.score,
        "exploration_bonus": round(exploration, 4),
        "total": round(max(0.0, min(1.0, total)), 4),
    }
    stop_models = build_stops_from_roles(context, selected, list(plan.roles))
    caveats = build_caveats(context, selected, duration) + critic.caveats
    title = titled_plan_option(plan.strategy, selected)

    return ItineraryOption(
        id=stable_itinerary_id(context, selected, title),
        title=title,
        stops=stop_models,
        route_geometry=route_geometry(context.location, [place.coordinates for place in selected]),
        estimated_duration_minutes=duration,
        total_walking_m=distance_m,
        scores=scores,
        explanation=explain_plan_option(context, selected, plan.strategy, agents["agent_approval_count"], critic.provider),
        caveats=dedupe_strings(caveats),
    )


def feasible_places(context: HyperContext, places: list[Place]) -> list[Place]:
    max_price = BUDGET_MAX_PRICE[context.budget]
    filtered = [
        place
        for place in places
        if place.price_level <= max_price
        and is_place_open(place, context.local_datetime)
        and haversine_m(context.location, place.coordinates) <= context.mobility_radius_m
    ]
    if context.weather in {WeatherCondition.rain, WeatherCondition.snow}:
        indoor = [place for place in filtered if place.indoor or "rain_safe" in place.atmosphere_tags]
        return indoor if len(indoor) >= 5 else filtered
    return filtered


def relaxed_feasible_places(context: HyperContext, places: list[Place]) -> list[Place]:
    max_price = min(4, BUDGET_MAX_PRICE[context.budget] + 1)
    expanded_radius = max(context.mobility_radius_m, 4200)
    filtered = [
        place
        for place in places
        if place.price_level <= max_price
        and haversine_m(context.location, place.coordinates) <= expanded_radius
    ]
    if context.weather in {WeatherCondition.rain, WeatherCondition.snow}:
        indoor = [place for place in filtered if place.indoor or "rain_safe" in place.atmosphere_tags]
        return indoor if len(indoor) >= 5 else filtered
    return filtered


def ordered_templates(context: HyperContext) -> list[Template]:
    templates = list(TEMPLATES)
    templates.sort(
        key=lambda template: (
            context.weather in {WeatherCondition.rain, WeatherCondition.snow}
            and "Rain-Proof" in template.title,
            context.mood in template.mood_bias,
            any(needle in template.needles for needle in interest_needles(context)),
        ),
        reverse=True,
    )
    return templates


def build_option(
    context: HyperContext,
    candidates: list[Place],
    template: Template,
) -> ItineraryOption | None:
    stop_count = target_stop_count(context.available_minutes)
    if context.weather in {WeatherCondition.rain, WeatherCondition.snow} and "Rain-Proof" in template.title:
        stop_count = min(3, stop_count)

    selected: list[Place] = []
    cursor = context.location
    for needle in template.needles[:stop_count]:
        choices = [
            place
            for place in candidates
            if place.id not in {selected_place.id for selected_place in selected}
            and category_matches(place, needle)
        ]
        if not choices:
            choices = [
                place
                for place in candidates
                if place.id not in {selected_place.id for selected_place in selected}
            ]
        if not choices:
            break
        choices.sort(
            key=lambda place: individual_place_score(context, place, cursor),
            reverse=True,
        )
        selected.append(choices[0])
        cursor = choices[0].coordinates

    if len(selected) < 2:
        return None

    selected = trim_to_time_budget(context, selected)
    if duration_for_places(context, selected) > context.available_minutes + 20:
        selected = repair_short_route(context, candidates, template) or selected
    if len(selected) < 2:
        return None

    stop_models = build_stops(context, selected, template)
    distance_m = walking_route_distance_m(context.location, [place.coordinates for place in selected])
    duration = walking_minutes(distance_m) + sum(stop.dwell_minutes for stop in stop_models)
    scores = score_itinerary(context, selected, distance_m, template)
    caveats = build_caveats(context, selected, duration)
    title = titled_option(context, template, selected)
    itinerary_id = stable_itinerary_id(context, selected, title)

    return ItineraryOption(
        id=itinerary_id,
        title=title,
        stops=stop_models,
        route_geometry=route_geometry(context.location, [place.coordinates for place in selected]),
        estimated_duration_minutes=duration,
        total_walking_m=distance_m,
        scores=scores,
        explanation=explain_option(context, selected, template),
        caveats=caveats,
    )


def target_stop_count(available_minutes: int) -> int:
    if available_minutes < 75:
        return 2
    if available_minutes < 150:
        return 3
    return 4


def target_stop_counts(available_minutes: int) -> list[int]:
    target = target_stop_count(available_minutes)
    counts = [target, max(2, target - 1), min(4, target + 1), 2]
    return list(dict.fromkeys(counts))


def individual_place_score(context: HyperContext, place: Place, cursor) -> float:
    distance = haversine_m(cursor, place.coordinates)
    distance_fit = max(0.0, 1.0 - distance / max(context.mobility_radius_m, 1))
    mood_fit = text_match_score(place, MOOD_NEEDLES[context.mood])
    interest_fit = text_match_score(place, tuple(interest_needles(context)))
    weather_fit = place_weather_fit(context, place)
    crowd_penalty = float(place.quality_signals.get("crowd_risk", 0.4))
    if context.stimulation_level >= 4:
        crowd_fit = crowd_penalty
    else:
        crowd_fit = 1.0 - crowd_penalty
    quality = place.rating / 5.0
    return (
        0.32 * mood_fit
        + 0.26 * interest_fit
        + 0.18 * distance_fit
        + 0.12 * weather_fit
        + 0.07 * crowd_fit
        + 0.05 * quality
    )


def score_itinerary(
    context: HyperContext,
    selected: list[Place],
    distance_m: int,
    template: Template | None = None,
) -> dict[str, float]:
    context_fit = average(
        max(
            text_match_score(place, MOOD_NEEDLES[context.mood]),
            text_match_score(place, tuple(interest_needles(context))),
        )
        for place in selected
    )
    effort = max(0.0, 1.0 - distance_m / max(context.mobility_radius_m * 1.4, 1))
    duration = walking_minutes(distance_m) + sum(DWELL_MINUTES[place.category] for place in selected)
    duration_fit = max(0.0, 1.0 - max(0, duration - context.available_minutes) / max(context.available_minutes, 1))
    weather_fit = average(place_weather_fit(context, place) for place in selected)
    quality = average(place.rating / 5.0 for place in selected)
    novelty = average(float(place.quality_signals.get("local_value", 0.6)) for place in selected)
    diversity = len({place.category for place in selected}) / max(len(selected), 1)
    crowd_fit = average(1.0 - float(place.quality_signals.get("crowd_risk", 0.4)) for place in selected)
    budget_fit = budget_fit_score(context, selected)
    personalization = personalization_score(context, selected)
    template_bias = 1.0 if template and context.mood in template.mood_bias else 0.78
    algorithmic_score = (
        0.22 * context_fit
        + 0.16 * effort
        + 0.13 * duration_fit
        + 0.12 * budget_fit
        + 0.11 * weather_fit
        + 0.10 * personalization
        + 0.07 * quality
        + 0.05 * novelty
        + 0.03 * diversity
        + 0.01 * crowd_fit
        + 0.04 * template_bias
    )
    return {
        "total": round(algorithmic_score, 4),
        "algorithmic_score": round(algorithmic_score, 4),
        "context_fit": round(context_fit, 4),
        "effort": round(effort, 4),
        "duration_fit": round(duration_fit, 4),
        "budget_fit": round(budget_fit, 4),
        "weather_fit": round(weather_fit, 4),
        "crowd_fit": round(crowd_fit, 4),
        "quality": round(quality, 4),
        "novelty": round(novelty, 4),
        "diversity": round(diversity, 4),
        "personalization": round(personalization, 4),
    }


def text_match_score(place: Place, needles: tuple[str, ...]) -> float:
    if not needles:
        return 0.35
    haystack = {place.category.value, *place.tags, *place.atmosphere_tags}
    matches = sum(1 for needle in needles if needle in haystack)
    return min(1.0, 0.25 + matches / max(len(needles), 1))


def interest_needles(context: HyperContext) -> list[str]:
    return [INTEREST_TO_NEEDLE[interest] for interest in context.interests]


def place_weather_fit(context: HyperContext, place: Place) -> float:
    if context.weather in {WeatherCondition.rain, WeatherCondition.snow, WeatherCondition.cold, WeatherCondition.hot}:
        return 1.0 if place.indoor or "rain_safe" in place.atmosphere_tags else 0.25
    if context.weather == WeatherCondition.windy:
        return 0.85 if place.indoor else 0.55
    return 0.8 if place.indoor else 1.0


def trim_to_time_budget(context: HyperContext, selected: list[Place]) -> list[Place]:
    trimmed = list(selected)
    while len(trimmed) > 2:
        if duration_for_places(context, trimmed) <= context.available_minutes:
            return trimmed
        trimmed.pop()
    return trimmed


def duration_for_places(context: HyperContext, selected: list[Place]) -> int:
    distance = walking_route_distance_m(context.location, [place.coordinates for place in selected])
    dwell = sum(DWELL_MINUTES[place.category] for place in selected)
    return walking_minutes(distance) + dwell


def budget_fit_score(context: HyperContext, selected: list[Place]) -> float:
    cap = max(BUDGET_MAX_PRICE[context.budget], 1)
    if context.budget == Budget.free:
        return average(1.0 if place.price_level == 0 else 0.25 for place in selected)
    return average(max(0.0, 1.0 - max(0, place.price_level - cap) / 3.0) for place in selected)


def personalization_score(context: HyperContext, selected: list[Place]) -> float:
    note = (context.note or "").lower()
    if not note:
        return average(text_match_score(place, tuple(interest_needles(context))) for place in selected)
    note_tokens = {token.strip(".,!?;:()[]") for token in note.split() if len(token) > 2}
    if not note_tokens:
        return 0.45
    scores = []
    for place in selected:
        haystack = {place.category.value, *place.tags, *place.atmosphere_tags, place.neighborhood.lower()}
        matches = len(note_tokens.intersection(haystack))
        scores.append(min(1.0, 0.35 + matches / max(len(note_tokens), 1)))
    return average(scores)


def route_seed_value(context: HyperContext, route: tuple[Place, ...]) -> float:
    distance = walking_route_distance_m(context.location, [place.coordinates for place in route])
    metrics = score_itinerary(context, list(route), distance)
    transition_penalty = average_transition_penalty(context, route)
    return metrics["algorithmic_score"] - transition_penalty + route_exploration_bonus(context, list(route), "beam") * 0.08


def plan_seed_score(context: HyperContext, plan: CandidatePlan) -> float:
    distance = walking_route_distance_m(context.location, [place.coordinates for place in plan.places])
    metrics = score_itinerary(context, list(plan.places), distance)
    return metrics["algorithmic_score"] + route_exploration_bonus(context, list(plan.places), plan.search_seed) * 0.04


def average_transition_penalty(context: HyperContext, route: tuple[Place, ...]) -> float:
    if len(route) < 2:
        return 0.0
    legs = [
        haversine_m(route[index].coordinates, route[index + 1].coordinates)
        for index in range(len(route) - 1)
    ]
    long_leg_penalties = [max(0.0, leg - context.mobility_radius_m * 0.45) / max(context.mobility_radius_m, 1) for leg in legs]
    return min(0.18, average(long_leg_penalties))


def exploration_value(context: HyperContext, key: str) -> float:
    raw = "|".join(
        [
            context.mood.value,
            context.weather.value,
            str(context.available_minutes),
            str(context.stimulation_level),
            context.note or "",
            key,
        ]
    )
    return int(sha1(raw.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def route_exploration_bonus(context: HyperContext, selected: list[Place], seed: str) -> float:
    raw = "|".join([seed, context.note or "", *[place.id for place in selected]])
    return int(sha1(raw.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def repair_short_route(
    context: HyperContext,
    candidates: list[Place],
    template: Template,
) -> list[Place] | None:
    if len(candidates) < 2:
        return None
    needles = template.needles[:2]
    first_choices = matching_or_all(candidates, needles[0])
    second_choices = matching_or_all(candidates, needles[1] if len(needles) > 1 else needles[0])
    max_duration = max(context.available_minutes + 20, 65)
    pairs: list[tuple[float, list[Place]]] = []

    for first in first_choices:
        for second in second_choices:
            if first.id == second.id:
                continue
            pair = [first, second]
            duration = duration_for_places(context, pair)
            if duration > max_duration:
                continue
            distance = route_distance_m(context.location, [place.coordinates for place in pair])
            score = score_itinerary(context, pair, distance, template)["total"]
            pairs.append((score, pair))

    if pairs:
        pairs.sort(key=lambda item: item[0], reverse=True)
        return pairs[0][1]

    closest = sorted(
        (
            [first, second]
            for first in candidates
            for second in candidates
            if first.id != second.id
        ),
        key=lambda pair: duration_for_places(context, pair),
    )
    return closest[0] if closest else None


def repair_short_route_from_places(context: HyperContext, selected: list[Place]) -> list[Place] | None:
    if len(selected) < 2:
        return None
    pairs = sorted(
        (
            [first, second]
            for first in selected
            for second in selected
            if first.id != second.id
        ),
        key=lambda pair: duration_for_places(context, pair),
    )
    for pair in pairs:
        if duration_for_places(context, pair) <= context.available_minutes + 25:
            return pair
    return pairs[0] if pairs else None


def matching_or_all(candidates: list[Place], needle: str) -> list[Place]:
    matches = [place for place in candidates if category_matches(place, needle)]
    return matches or candidates


def infer_strategy(context: HyperContext, selected: list[Place]) -> str:
    categories = {place.category for place in selected}
    tags = {tag for place in selected for tag in [*place.tags, *place.atmosphere_tags]}
    if context.weather in {WeatherCondition.rain, WeatherCondition.snow} and all(place.indoor for place in selected):
        return "weather-proof"
    if PlaceCategory.restaurant in categories or PlaceCategory.market in categories or "food" in tags:
        return "food-led"
    if PlaceCategory.bookstore in categories and (PlaceCategory.cafe in categories or "calm" in tags):
        return "quiet-focus"
    if PlaceCategory.museum in categories or PlaceCategory.gallery in categories or "art" in tags:
        return "culture-loop"
    if PlaceCategory.park in categories or PlaceCategory.scenic in categories:
        return "open-air"
    if "history" in tags or "architecture" in tags:
        return "urban-texture"
    return f"{context.mood.value}-fit"


def role_for_stop(context: HyperContext, place: Place, index: int, route_length: int) -> str:
    if index == 0:
        if context.mood == Mood.calm:
            return "ease in"
        if context.mood == Mood.hungry:
            return "anchor"
        return "start"
    if index == route_length - 1:
        return "finish"
    if place.category in {PlaceCategory.cafe, PlaceCategory.restaurant, PlaceCategory.market}:
        return "pause"
    if place.category in {PlaceCategory.museum, PlaceCategory.gallery, PlaceCategory.landmark}:
        return "explore"
    if place.category in {PlaceCategory.park, PlaceCategory.scenic}:
        return "decompress"
    return "browse"


def stable_search_seed(context: HyperContext, route: tuple[Place, ...], strategy: str) -> str:
    raw = "|".join([context.mood.value, context.weather.value, strategy, *[place.id for place in route]])
    return sha1(raw.encode("utf-8")).hexdigest()[:10]


def build_stops(context: HyperContext, selected: list[Place], template: Template) -> list[ItineraryStop]:
    start = effective_datetime(context.local_datetime)
    elapsed = 0
    cursor = context.location
    stops: list[ItineraryStop] = []
    for index, place in enumerate(selected):
        walk = walking_minutes(int(haversine_m(cursor, place.coordinates)))
        elapsed += walk
        arrival = start + timedelta(minutes=elapsed)
        dwell = DWELL_MINUTES[place.category]
        role = template.roles[min(index, len(template.roles) - 1)]
        stops.append(
            ItineraryStop(
                place_id=place.id,
                name=place.name,
                category=place.category,
                coordinates=place.coordinates,
                neighborhood=place.neighborhood,
                role=role,
                dwell_minutes=dwell,
                arrival_window=arrival.strftime("%-I:%M %p"),
                indoor=place.indoor,
            )
        )
        elapsed += dwell
        cursor = place.coordinates
    return stops


def build_stops_from_roles(context: HyperContext, selected: list[Place], roles: list[str]) -> list[ItineraryStop]:
    start = effective_datetime(context.local_datetime)
    elapsed = 0
    cursor = context.location
    stops: list[ItineraryStop] = []
    for index, place in enumerate(selected):
        walk = walking_minutes(int(walking_route_distance_m(cursor, [place.coordinates])))
        elapsed += walk
        arrival = start + timedelta(minutes=elapsed)
        dwell = DWELL_MINUTES[place.category]
        stops.append(
            ItineraryStop(
                place_id=place.id,
                name=place.name,
                category=place.category,
                coordinates=place.coordinates,
                neighborhood=place.neighborhood,
                role=roles[index] if index < len(roles) else role_for_stop(context, place, index, len(selected)),
                dwell_minutes=dwell,
                arrival_window=arrival.strftime("%-I:%M %p"),
                indoor=place.indoor,
            )
        )
        elapsed += dwell
        cursor = place.coordinates
    return stops


def build_caveats(context: HyperContext, selected: list[Place], duration: int) -> list[str]:
    caveats: list[str] = []
    if duration > context.available_minutes:
        caveats.append("A little over the time target; shorten the final stop if needed.")
    if any(not is_place_open(place, context.local_datetime) for place in selected):
        caveats.append("Check live hours before leaving; this fallback relaxes opening-hour filters.")
    if context.weather in {WeatherCondition.rain, WeatherCondition.snow} and any(not p.indoor for p in selected):
        caveats.append("Includes a short outdoor segment despite poor weather.")
    if any(float(place.quality_signals.get("crowd_risk", 0.0)) > 0.75 for place in selected):
        caveats.append("One stop can be crowded at peak times.")
    return caveats


def explain_option(context: HyperContext, selected: list[Place], template: Template) -> str:
    names = ", ".join(place.name for place in selected)
    weather_phrase = (
        "with mostly indoor cover"
        if context.weather in {WeatherCondition.rain, WeatherCondition.snow, WeatherCondition.cold, WeatherCondition.hot}
        else "with a walkable outdoor rhythm"
    )
    return (
        f"{template.title} fits a {context.mood.value} mood {weather_phrase}: {names}. "
        "It balances explicit constraints with a small amount of neighborhood texture."
    )


def explain_plan_option(
    context: HyperContext,
    selected: list[Place],
    strategy: str,
    approval_count: float,
    critic_provider: str,
) -> str:
    names = ", ".join(place.name for place in selected)
    weather_phrase = (
        "mostly indoors"
        if context.weather in {WeatherCondition.rain, WeatherCondition.snow, WeatherCondition.cold, WeatherCondition.hot}
        else "with a walkable city rhythm"
    )
    return (
        f"Generated by candidate search, then rated by simulated agents: {int(approval_count)}/5 approved. "
        f"The {strategy.replace('-', ' ')} route runs {weather_phrase}: {names}. "
        f"{critic_provider.replace('_', ' ')} checked coherence."
    )


def titled_option(context: HyperContext, template: Template, selected: list[Place]) -> str:
    neighborhoods = list(dict.fromkeys(place.neighborhood for place in selected))
    if len(neighborhoods) == 1:
        return f"{template.title} in {neighborhoods[0]}"
    return f"{template.title}: {neighborhoods[0]} to {neighborhoods[-1]}"


def titled_plan_option(strategy: str, selected: list[Place]) -> str:
    neighborhoods = list(dict.fromkeys(place.neighborhood for place in selected))
    category_names = list(dict.fromkeys(place.category.value.replace("_", " ") for place in selected))
    label = {
        "weather-proof": "Weather-Proof Pick",
        "food-led": "Food-Led Route",
        "quiet-focus": "Quiet Focus Route",
        "culture-loop": "Culture Loop",
        "open-air": "Open-Air Drift",
        "urban-texture": "Urban Texture Walk",
    }.get(strategy, f"{strategy.replace('-', ' ').title()} Route")
    if len(category_names) >= 2:
        label = f"{label}: {category_names[0].title()} + {category_names[1].title()}"
    if len(neighborhoods) == 1:
        return f"{label} in {neighborhoods[0]}"
    return f"{label}: {neighborhoods[0]} to {neighborhoods[-1]}"


def stable_itinerary_id(context: HyperContext, selected: list[Place], title: str) -> str:
    raw = "|".join([title, context.mood.value, *[place.id for place in selected]])
    return "itin-" + sha1(raw.encode("utf-8")).hexdigest()[:12]


def diversify(options: list[ItineraryOption], limit: int) -> list[ItineraryOption]:
    selected: list[ItineraryOption] = []
    used_first_stops: set[str] = set()
    used_places: set[str] = set()
    for option in options:
        first_stop = option.stops[0].place_id
        option_places = {stop.place_id for stop in option.stops}
        overlap = len(option_places.intersection(used_places)) / max(len(option_places), 1)
        if first_stop in used_first_stops or overlap > 0.34:
            continue
        selected.append(option)
        used_first_stops.add(first_stop)
        used_places.update(option_places)
        if len(selected) == limit:
            return selected
    for option in options:
        if option.id not in {chosen.id for chosen in selected}:
            selected.append(option)
        if len(selected) == limit:
            break
    return selected


def fallback_options(
    context: HyperContext,
    candidates: list[Place],
    count: int,
    existing: list[ItineraryOption],
) -> list[ItineraryOption]:
    if count <= 0:
        return []
    used = {stop.place_id for option in existing for stop in option.stops}
    ranked = sorted(
        [place for place in candidates if place.id not in used],
        key=lambda place: individual_place_score(context, place, context.location),
        reverse=True,
    )
    fallback: list[ItineraryOption] = []
    for index in range(0, len(ranked), 2):
        pair = ranked[index : index + 2]
        if len(pair) < 2:
            break
        template = Template(
            title="Nearby Micro-Loop",
            needles=(pair[0].category.value, pair[1].category.value),
            roles=("start", "finish"),
        )
        option = build_option(context, pair, template)
        if option is not None:
            fallback.append(option)
        if len(fallback) == count:
            break
    return fallback


def average(values) -> float:
    realized = list(values)
    if not realized:
        return 0.0
    return sum(realized) / len(realized)


def dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
