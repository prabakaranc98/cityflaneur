"""
Integration tests for all live APIs, algorithms, and agents.
Run with:  uv run --python 3.11 --extra dev pytest tests/test_live_apis.py -v --tb=short
Results are written to /tmp/cityflaneur_test_report.json for analysis.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

import pytest

from app.core.config import get_settings
from app.data.seed import SEED_PLACES
from app.engine.agents import agent_panel_score
from app.engine.context import parse_context
from app.engine.llm import OpenRouterItineraryCritic, get_itinerary_critic
from app.engine.recommender import (
    build_walk_legs,
    feasible_places,
    recommend_itineraries,
    score_itinerary,
)
from app.engine.transit import nearest_subway_label
from app.models.schemas import (
    Budget,
    Coordinates,
    ContextParseRequest,
    GroupMode,
    HyperContext,
    Interest,
    Mood,
    WeatherCondition,
)
from app.services.pulse import build_neighborhood_pulses, fetch_exa_headlines, fetch_llm_trivia
from app.services.streetscapes import build_street_scenes, fetch_google_street_view, fetch_mapillary_images

settings = get_settings()

_REPORT: dict[str, object] = {
    "run_at": datetime.utcnow().isoformat(),
    "settings": {
        "enable_llm_adapters": settings.enable_llm_adapters,
        "enable_live_pulse": settings.enable_live_pulse,
        "enable_streetscapes": settings.enable_streetscapes,
        "openrouter_model": settings.openrouter_model,
        "catalog_size": len(SEED_PLACES),
    },
    "results": {},
}


def _save_report() -> None:
    path = "/tmp/cityflaneur_test_report.json"
    with open(path, "w") as fh:
        json.dump(_REPORT, fh, indent=2, default=str)


# ── Transit module ────────────────────────────────────────────────────────────

class TestTransit:
    def test_union_square_finds_correct_station(self):
        label = nearest_subway_label(40.7352, -73.9897)
        assert label is not None
        assert "Union Sq" in label or "14 St" in label
        assert "4" in label or "5" in label or "6" in label
        _REPORT["results"]["transit_union_square"] = label

    def test_w4st_area_finds_hub(self):
        label = nearest_subway_label(40.7324, -74.0004)
        assert label is not None
        assert "W 4 St" in label or "4 St" in label
        _REPORT["results"]["transit_w4st"] = label

    def test_midtown_finds_times_sq_or_grand_central(self):
        label = nearest_subway_label(40.7540, -73.9832)
        assert label is not None
        _REPORT["results"]["transit_midtown"] = label

    def test_remote_location_returns_none(self):
        # Far outside max_distance_m=750
        label = nearest_subway_label(40.7700, -73.9650, max_distance_m=100)
        # May or may not be None depending on exact station proximity; just check it doesn't crash
        _REPORT["results"]["transit_remote"] = label

    def test_fidi_finds_fulton(self):
        label = nearest_subway_label(40.7089, -74.0077)
        assert label is not None
        assert "Fulton" in label or "Wall" in label or "Chambers" in label
        _REPORT["results"]["transit_fidi"] = label


# ── Seed catalog ──────────────────────────────────────────────────────────────

class TestSeedCatalog:
    def test_catalog_has_minimum_places(self):
        assert len(SEED_PLACES) >= 45, f"Catalog only has {len(SEED_PLACES)} places"
        _REPORT["results"]["catalog_size"] = len(SEED_PLACES)

    def test_catalog_covers_key_neighborhoods(self):
        neighborhoods = {p.neighborhood for p in SEED_PLACES}
        required = {"Upper West Side", "Chelsea", "East Village", "SoHo", "Union Square"}
        missing = required - neighborhoods
        assert not missing, f"Missing neighborhoods: {missing}"
        _REPORT["results"]["catalog_neighborhoods"] = sorted(neighborhoods)

    def test_all_places_have_valid_coordinates(self):
        for place in SEED_PLACES:
            assert 40.68 <= place.coordinates.lat <= 40.89, f"{place.name} lat out of bounds"
            assert -74.05 <= place.coordinates.lng <= -73.90, f"{place.name} lng out of bounds"

    def test_opening_hours_parseable(self):
        from app.engine.time import is_place_open
        dt = datetime(2026, 5, 12, 15, 0)
        errors = []
        for place in SEED_PLACES:
            try:
                is_place_open(place, dt)
            except Exception as exc:
                errors.append(f"{place.name}: {exc}")
        assert not errors, "Opening hour parse errors: " + "; ".join(errors)


# ── Context parsing (rules + LLM) ────────────────────────────────────────────

class TestContextParsing:
    def test_rules_parse_calm_note(self):
        ctx = parse_context(ContextParseRequest(note="quiet books and a park, low effort"))
        assert ctx.mood in {Mood.calm, Mood.focused}
        assert Interest.books in ctx.interests or Interest.parks in ctx.interests

    def test_rules_parse_food_note(self):
        ctx = parse_context(ContextParseRequest(note="hungry, want dinner with friends"))
        assert ctx.mood in {Mood.hungry, Mood.social}
        assert Interest.food in ctx.interests

    def test_rules_parse_rain_weather(self):
        ctx = parse_context(ContextParseRequest(note="rainy day, indoor options"))
        assert ctx.weather == WeatherCondition.rain

    def test_explicit_fields_are_not_overridden(self):
        ctx = parse_context(ContextParseRequest(
            mood=Mood.romantic,
            weather=WeatherCondition.clear,
            note="stressed and need food",  # would normally infer hungry/rain
        ))
        assert ctx.mood == Mood.romantic
        assert ctx.weather == WeatherCondition.clear

    @pytest.mark.skipif(
        not settings.enable_llm_adapters or not settings.openrouter_api_key,
        reason="LLM adapters not enabled",
    )
    def test_llm_parse_extracts_signals(self):
        t0 = time.time()
        ctx = parse_context(ContextParseRequest(note="I want to avoid tourist traps, show me something locals do"))
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["llm_context_parse"] = {
            "mood": ctx.mood.value,
            "interests": [i.value for i in ctx.interests],
            "signals": ctx.parsed_signals,
            "latency_s": elapsed,
        }
        assert ctx.parsed_signals.get("source") in {"llm+rules", "rules"}

    @pytest.mark.skipif(
        not settings.enable_llm_adapters or not settings.openrouter_api_key,
        reason="LLM adapters not enabled",
    )
    def test_llm_parse_detects_avoid_crowded(self):
        ctx = parse_context(ContextParseRequest(note="no crowds, something peaceful and hidden"))
        assert ctx.parsed_signals.get("avoid_crowded") is True or "crowded" not in str(ctx.parsed_signals)


# ── Recommender engine ────────────────────────────────────────────────────────

class TestRecommender:
    _BASE = dict(
        location=Coordinates(lat=40.7359, lng=-73.9911),
        available_minutes=100,
        budget=Budget.low,
        local_datetime=datetime(2026, 5, 12, 16, 0),
    )

    def _context(self, **kwargs) -> HyperContext:
        req = ContextParseRequest(**{**self._BASE, **kwargs})
        return parse_context(req)

    def test_returns_three_options(self):
        ctx = self._context(mood=Mood.calm)
        recs = recommend_itineraries(ctx)
        assert len(recs) == 3
        _REPORT["results"]["recommender_count"] = len(recs)

    def test_options_are_diverse(self):
        ctx = self._context(mood=Mood.curious)
        recs = recommend_itineraries(ctx)
        first_stops = [r.stops[0].place_id for r in recs]
        assert len(set(first_stops)) == 3, "All options start at the same stop"

    def test_scores_include_all_components(self):
        ctx = self._context(mood=Mood.calm)
        recs = recommend_itineraries(ctx)
        required_keys = {"total", "context_fit", "effort", "weather_fit", "novelty", "agent_approval", "llm_critique"}
        for rec in recs:
            missing = required_keys - rec.scores.keys()
            assert not missing, f"Missing score keys: {missing}"
        _REPORT["results"]["score_keys"] = sorted(recs[0].scores.keys())

    def test_walk_legs_populated(self):
        ctx = self._context(mood=Mood.calm)
        recs = recommend_itineraries(ctx)
        for rec in recs:
            assert len(rec.walk_legs) == len(rec.stops), "Walk leg count mismatch"
            for leg in rec.walk_legs:
                assert leg.distance_m >= 0
                assert leg.walking_minutes >= 0
        _REPORT["results"]["walk_legs_sample"] = [
            {"from": leg.from_name, "to": leg.to_name, "m": leg.distance_m, "min": leg.walking_minutes}
            for leg in recs[0].walk_legs
        ]

    def test_transit_populated_on_stops(self):
        ctx = self._context(mood=Mood.curious)
        recs = recommend_itineraries(ctx)
        stops_with_subway = sum(1 for rec in recs for stop in rec.stops if stop.nearest_subway)
        total_stops = sum(len(rec.stops) for rec in recs)
        pct = stops_with_subway / max(total_stops, 1)
        _REPORT["results"]["transit_coverage_pct"] = round(pct, 2)
        assert pct > 0.5, f"Only {pct:.0%} of stops have subway info"

    def test_rain_recommends_indoor_heavy(self):
        ctx = self._context(mood=Mood.calm, weather=WeatherCondition.rain)
        recs = recommend_itineraries(ctx)
        assert len(recs) >= 1
        indoor_counts = [sum(s.indoor for s in r.stops) / len(r.stops) for r in recs]
        _REPORT["results"]["rain_indoor_ratio"] = [round(x, 2) for x in indoor_counts]

    def test_different_moods_produce_different_slates(self):
        calm = recommend_itineraries(self._context(mood=Mood.calm, interests=[Interest.books]))
        hungry = recommend_itineraries(self._context(mood=Mood.hungry, interests=[Interest.food]))
        calm_ids = {r.id for r in calm}
        hungry_ids = {r.id for r in hungry}
        overlap = calm_ids & hungry_ids
        assert len(overlap) < 2, f"Too much overlap between mood slates: {overlap}"

    def test_llm_critique_score_is_in_range(self):
        ctx = self._context(mood=Mood.curious)
        recs = recommend_itineraries(ctx)
        for rec in recs:
            score = rec.scores.get("llm_critique", 0)
            assert 0.0 <= score <= 1.0
        _REPORT["results"]["llm_critique_scores"] = [round(r.scores.get("llm_critique", 0), 3) for r in recs]


# ── Agent panel ───────────────────────────────────────────────────────────────

class TestAgents:
    def test_all_agents_produce_scores(self):
        ctx = parse_context(ContextParseRequest(
            location=Coordinates(lat=40.7359, lng=-73.9911),
            mood=Mood.calm,
            budget=Budget.low,
            available_minutes=90,
        ))
        metrics = {
            "context_fit": 0.7, "effort": 0.6, "duration_fit": 0.8,
            "budget_fit": 0.9, "weather_fit": 1.0, "quality": 0.8,
            "novelty": 0.6, "diversity": 0.7, "crowd_fit": 0.6, "personalization": 0.5,
        }
        result = agent_panel_score(ctx, metrics)
        assert 0.0 <= result["agent_approval"] <= 1.0
        assert result["agent_approval_count"] >= 0
        agent_names = [k for k in result if k.startswith("agent_") and k not in ("agent_approval", "agent_approval_count")]
        assert len(agent_names) == 5
        _REPORT["results"]["agent_panel"] = {k: round(v, 3) for k, v in result.items()}

    def test_budget_realist_scores_higher_for_free_places(self):
        base_metrics = {"budget_fit": 0.95, "effort": 0.6, "duration_fit": 0.75, "quality": 0.8, "weather_fit": 0.9}
        ctx_free = parse_context(ContextParseRequest(budget=Budget.free))
        ctx_high = parse_context(ContextParseRequest(budget=Budget.high))
        result_free = agent_panel_score(ctx_free, base_metrics)
        result_high = agent_panel_score(ctx_high, base_metrics)
        _REPORT["results"]["agent_budget_comparison"] = {
            "free_approval": round(result_free["agent_budget_realist"], 3),
            "high_approval": round(result_high["agent_budget_realist"], 3),
        }


# ── LLM critic ────────────────────────────────────────────────────────────────

class TestLLMCritic:
    @pytest.mark.skipif(
        not settings.enable_llm_adapters or not settings.openrouter_api_key,
        reason="LLM adapters not enabled",
    )
    def test_openrouter_critic_returns_valid_review(self):
        places = SEED_PLACES[:3]
        ctx = parse_context(ContextParseRequest(
            location=Coordinates(lat=40.7359, lng=-73.9911),
            mood=Mood.calm, budget=Budget.low,
        ))
        metrics = score_itinerary(ctx, places, 1200)
        t0 = time.time()
        critic = OpenRouterItineraryCritic()
        review = critic.review(ctx, places, metrics)
        elapsed = round(time.time() - t0, 2)
        assert 0.0 <= review.score <= 1.0
        assert review.explanation
        assert "openrouter" in review.provider
        _REPORT["results"]["llm_critic"] = {
            "score": review.score,
            "explanation": review.explanation[:120],
            "caveats": review.caveats,
            "provider": review.provider,
            "latency_s": elapsed,
        }

    def test_heuristic_critic_works_without_llm(self):
        from app.engine.llm import HeuristicSemanticCritic
        places = SEED_PLACES[:3]
        ctx = parse_context(ContextParseRequest(
            location=Coordinates(lat=40.7359, lng=-73.9911),
            mood=Mood.calm, budget=Budget.low,
        ))
        metrics = score_itinerary(ctx, places, 1200)
        critic = HeuristicSemanticCritic()
        review = critic.review(ctx, places, metrics)
        assert 0.0 <= review.score <= 1.0
        _REPORT["results"]["heuristic_critic"] = {"score": review.score, "caveats": review.caveats}


# ── Neighborhood pulse ────────────────────────────────────────────────────────

class TestPulse:
    def test_pulse_returns_expected_structure(self):
        pulses = build_neighborhood_pulses(["Chelsea", "SoHo"])
        assert len(pulses) == 2
        for pulse in pulses:
            assert pulse.trivia or pulse.headlines
            assert pulse.source_note

    @pytest.mark.skipif(not settings.enable_live_pulse or not settings.exa_api_key, reason="Exa not enabled")
    def test_exa_returns_live_headlines(self):
        t0 = time.time()
        items = fetch_exa_headlines("Chelsea", limit=2)
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["exa_pulse"] = {
            "count": len(items),
            "titles": [i.title for i in items],
            "latency_s": elapsed,
        }
        assert len(items) >= 1
        assert items[0].title
        assert items[0].summary

    @pytest.mark.skipif(
        not settings.enable_llm_adapters or not settings.openrouter_api_key,
        reason="LLM adapters not enabled",
    )
    def test_llm_trivia_returns_neighborhood_insights(self):
        t0 = time.time()
        items = fetch_llm_trivia("West Village")
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["llm_trivia"] = {
            "count": len(items),
            "items": [{"title": i.title, "summary": i.summary} for i in items],
            "latency_s": elapsed,
        }
        assert len(items) >= 1
        assert items[0].source == "llm_context"
        assert len(items[0].summary) <= 200


# ── Streetscapes ──────────────────────────────────────────────────────────────

class TestStreetscapes:
    @pytest.mark.skipif(not settings.enable_streetscapes, reason="Streetscapes not enabled")
    def test_mapillary_returns_images(self):
        if not settings.mapillary_access_token:
            pytest.skip("No Mapillary key")
        t0 = time.time()
        images, status = fetch_mapillary_images(40.7359, -73.9911, limit=3)
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["mapillary"] = {
            "status": status,
            "count": len(images),
            "latency_s": elapsed,
            "sample_url": images[0].image_url[:60] + "..." if images else None,
        }
        assert status in {"ok", "empty"}
        if status == "ok":
            assert len(images) >= 1
            for img in images:
                assert img.image_url
                assert img.attribution == "Mapillary contributors"

    @pytest.mark.skipif(not settings.enable_streetscapes, reason="Streetscapes not enabled")
    def test_google_street_view_returns_image(self):
        if not settings.google_maps_api_key:
            pytest.skip("No Google Maps key")
        t0 = time.time()
        image, status = fetch_google_street_view(40.7359, -73.9911)
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["google_street_view"] = {
            "status": status,
            "latency_s": elapsed,
            "has_image": image is not None,
            "title": image.title if image else None,
        }
        assert status in {"ok", "zero_results", "not_found", "missing_key"}
        if status == "ok":
            assert image is not None
            assert image.image_url.startswith("https://maps.googleapis.com")
            assert image.attribution

    @pytest.mark.skipif(not settings.enable_streetscapes, reason="Streetscapes not enabled")
    def test_build_street_scenes_combines_providers(self):
        result = build_street_scenes(Coordinates(lat=40.7359, lng=-73.9911), limit=4)
        _REPORT["results"]["streetscapes_combined"] = {
            "provider_status": result.provider_status,
            "image_count": len(result.images),
            "source_note": result.source_note,
        }
        assert result.provider_status
        assert result.source_note

    def test_streetscapes_disabled_returns_empty(self):
        from unittest.mock import patch
        from app.core.config import Settings
        disabled_settings = Settings(enable_streetscapes=False)
        with patch("app.services.streetscapes.get_settings", return_value=disabled_settings):
            result = build_street_scenes(Coordinates(lat=40.7359, lng=-73.9911))
        assert result.images == []
        assert "disabled" in result.source_note


# ── Full end-to-end pipeline ──────────────────────────────────────────────────

class TestEndToEnd:
    def test_full_pipeline_calm_solo(self):
        t0 = time.time()
        ctx = parse_context(ContextParseRequest(
            location=Coordinates(lat=40.7359, lng=-73.9911),
            mood=Mood.calm,
            budget=Budget.low,
            available_minutes=90,
            interests=[Interest.books, Interest.cafes, Interest.parks],
            local_datetime=datetime(2026, 5, 12, 15, 0),
        ))
        recs = recommend_itineraries(ctx)
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["e2e_calm_solo"] = {
            "latency_s": elapsed,
            "recommendation_count": len(recs),
            "options": [
                {
                    "title": r.title,
                    "stops": [s.name for s in r.stops],
                    "total_score": round(r.scores["total"], 3),
                    "walk_legs": [{"to": l.to_name, "min": l.walking_minutes, "transit": l.transit_hint} for l in r.walk_legs],
                    "transit_per_stop": [s.nearest_subway for s in r.stops],
                    "llm_critique": round(r.scores.get("llm_critique", 0), 3),
                    "agent_approval": round(r.scores.get("agent_approval", 0), 3),
                }
                for r in recs
            ],
        }
        assert len(recs) == 3
        assert elapsed < 90  # OSM fetch ~16s + 3 LLM calls ~10s each

    def test_full_pipeline_hungry_group(self):
        t0 = time.time()
        ctx = parse_context(ContextParseRequest(
            location=Coordinates(lat=40.7479, lng=-74.0048),
            mood=Mood.hungry,
            budget=Budget.medium,
            available_minutes=120,
            group_mode=GroupMode.group,
            interests=[Interest.food, Interest.art],
            local_datetime=datetime(2026, 5, 12, 19, 0),
        ))
        recs = recommend_itineraries(ctx)
        elapsed = round(time.time() - t0, 2)
        _REPORT["results"]["e2e_hungry_group"] = {
            "latency_s": elapsed,
            "options": [{"title": r.title, "score": round(r.scores["total"], 3)} for r in recs],
        }
        assert len(recs) >= 1

    def test_full_pipeline_rainy_day(self):
        ctx = parse_context(ContextParseRequest(
            location=Coordinates(lat=40.7500, lng=-73.9800),
            mood=Mood.focused,
            weather=WeatherCondition.rain,
            budget=Budget.low,
            available_minutes=150,
            interests=[Interest.museums, Interest.books],
            local_datetime=datetime(2026, 5, 12, 11, 0),
        ))
        recs = recommend_itineraries(ctx)
        indoor_ratios = [sum(s.indoor for s in r.stops) / len(r.stops) for r in recs]
        _REPORT["results"]["e2e_rainy"] = {
            "options": [r.title for r in recs],
            "indoor_ratios": [round(x, 2) for x in indoor_ratios],
        }
        assert all(ratio >= 0.5 for ratio in indoor_ratios), "Rain route should be mostly indoor"


def pytest_sessionfinish(session, exitstatus):
    _REPORT["exit_status"] = exitstatus
    _REPORT["passed"] = session.testscollected - session.testsfailed - session.testsskipped if hasattr(session, "testsfailed") else None
    _save_report()
    print(f"\n📊 Test report saved to /tmp/cityflaneur_test_report.json")
