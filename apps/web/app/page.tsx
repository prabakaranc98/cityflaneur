"use client";

import { useEffect, useMemo, useState } from "react";
import { BentoControls } from "@/components/BentoControls";
import { FlaneurOnboarding } from "@/components/FlaneurOnboarding";
import { MapPanel } from "@/components/MapPanel";
import { NeighborhoodPulse } from "@/components/NeighborhoodPulse";
import { RecommendationCard } from "@/components/RecommendationCard";
import { StreetScenes } from "@/components/StreetScenes";
import { getNeighborhoodPulse, parseContext, streamRecommendations, type ProgressEvent } from "@/lib/api";
import type { FlaneurProfile, HyperContext, ItineraryOption, NeighborhoodPulse as NeighborhoodPulseType } from "@/types/cityflaneur";

const initialContext: HyperContext = {
  location: { lat: 40.7359, lng: -73.9911 },
  available_minutes: 90,
  local_datetime: null,
  weather: "clear",
  mood: "calm",
  stimulation_level: 2,
  budget: "low",
  group_mode: "solo",
  mobility_radius_m: 2600,
  interests: ["parks", "books", "cafes"],
  note: ""
};

export default function Home() {
  const [context, setContext] = useState<HyperContext>(initialContext);
  const [recommendations, setRecommendations] = useState<ItineraryOption[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [logEvents, setLogEvents] = useState<ProgressEvent[]>([]);
  const [pulseLoading, setPulseLoading] = useState(false);
  const [pulses, setPulses] = useState<NeighborhoodPulseType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [profile, setProfile] = useState<FlaneurProfile | null>(null);
  const sessionId = useMemo(() => `session-${Math.random().toString(36).slice(2)}`, []);

  useEffect(() => {
    const seen = localStorage.getItem("flaneur_onboarding_seen");
    if (!seen) {
      setShowOnboarding(true);
    }
    const stored = localStorage.getItem("flaneur_profile");
    if (stored) {
      try {
        setProfile(JSON.parse(stored) as FlaneurProfile);
      } catch {
        // ignore corrupt data
      }
    }
  }, []);

  const selected = recommendations.find((option) => option.id === selectedId) ?? recommendations[0] ?? null;

  // Accept optional context override so GPS updates can submit immediately
  // without waiting for React state to flush.
  async function submit(ctxOverride?: HyperContext) {
    const ctx = ctxOverride ?? context;
    setLoading(true);
    setLogEvents([]);
    setError(null);
    try {
      const parsed = await parseContext({
        ...ctx,
        local_datetime: new Date().toISOString(),
        profile: profile ?? undefined,
      });
      const response = await streamRecommendations(parsed, (event) => {
        setLogEvents((prev) => [...prev, event]);
      });
      setContext(response.context);
      setRecommendations(response.recommendations);
      setSelectedId(response.recommendations[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to fetch recommendations");
    } finally {
      setLoading(false);
    }
  }

  // No auto-submit on mount — user must click "Find three options"

  useEffect(() => {
    if (!selected) {
      setPulses([]);
      return;
    }
    const neighborhoods = Array.from(new Set(selected.stops.map((stop) => stop.neighborhood)));
    let mounted = true;
    setPulseLoading(true);
    getNeighborhoodPulse(neighborhoods)
      .then((response) => {
        if (mounted) {
          setPulses(response.pulses);
        }
      })
      .catch(() => {
        if (mounted) {
          setPulses([]);
        }
      })
      .finally(() => {
        if (mounted) {
          setPulseLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [selected]);

  function handleOnboardingComplete(p: FlaneurProfile | null) {
    setShowOnboarding(false);
    if (p) setProfile(p);
  }

  return (
    <main className="app-shell">
      {showOnboarding ? <FlaneurOnboarding onComplete={handleOnboardingComplete} /> : null}
      <BentoControls
        context={context}
        loading={loading}
        logEvents={logEvents}
        onChange={setContext}
        onSubmit={submit}
        onOpenProfile={() => setShowOnboarding(true)}
        onLocationFound={(location) => {
          // Just update the map center — don't auto-submit
          setContext((prev) => ({ ...prev, location }));
        }}
      />
      <section className="workspace" aria-label="Map and recommendations">
        <MapPanel context={context} selected={selected} />
        <div className="results-panel">
          <div className="results-header">
            <div>
              <p>Options</p>
              <h2>Three ways through Manhattan</h2>
            </div>
            {loading ? <span className="status-pill">Scoring</span> : <span className="status-pill">Ready</span>}
          </div>
          {selected ? (
            <div className="selected-summary">
              <div>
                <span>Selected</span>
                <strong>{selected.title}</strong>
              </div>
              <dl>
                <div>
                  <dt>Fit</dt>
                  <dd>{Math.round(selected.scores.total * 100)}</dd>
                </div>
                <div>
                  <dt>Walk</dt>
                  <dd>{(selected.total_walking_m / 1000).toFixed(1)} km</dd>
                </div>
                <div>
                  <dt>Stops</dt>
                  <dd>{selected.stops.length}</dd>
                </div>
              </dl>
            </div>
          ) : null}
          {error ? <div className="error-box">{error}</div> : null}
          <NeighborhoodPulse pulses={pulses} loading={pulseLoading} />
          <StreetScenes selected={selected} />
          <div className="recommendation-list">
            {recommendations.map((option, index) => (
              <RecommendationCard
                key={option.id}
                option={option}
                selected={selected?.id === option.id}
                context={context}
                sessionId={sessionId}
                rank={index + 1}
                onSelect={() => setSelectedId(option.id)}
              />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
