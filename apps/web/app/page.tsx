"use client";

import { useEffect, useMemo, useState } from "react";
import { BentoControls } from "@/components/BentoControls";
import { MapPanel } from "@/components/MapPanel";
import { NeighborhoodPulse } from "@/components/NeighborhoodPulse";
import { RecommendationCard } from "@/components/RecommendationCard";
import { StreetScenes } from "@/components/StreetScenes";
import { getNeighborhoodPulse, getRecommendations, parseContext } from "@/lib/api";
import type { HyperContext, ItineraryOption, NeighborhoodPulse as NeighborhoodPulseType } from "@/types/cityflaneur";

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
  const [pulseLoading, setPulseLoading] = useState(false);
  const [pulses, setPulses] = useState<NeighborhoodPulseType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useMemo(() => `session-${Math.random().toString(36).slice(2)}`, []);

  const selected = recommendations.find((option) => option.id === selectedId) ?? recommendations[0] ?? null;

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const parsed = await parseContext({
        ...context,
        local_datetime: new Date().toISOString()
      });
      const response = await getRecommendations(parsed);
      setContext(response.context);
      setRecommendations(response.recommendations);
      setSelectedId(response.recommendations[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to fetch recommendations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void submit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  return (
    <main className="app-shell">
      <BentoControls context={context} loading={loading} onChange={setContext} onSubmit={submit} />
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
            {recommendations.map((option) => (
              <RecommendationCard
                key={option.id}
                option={option}
                selected={selected?.id === option.id}
                context={context}
                sessionId={sessionId}
                onSelect={() => setSelectedId(option.id)}
              />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
