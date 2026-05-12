"use client";

import { Check, Clock3, CloudSun, Compass, Footprints, Heart, Navigation, Sparkles, Train, X } from "lucide-react";
import type { HyperContext, ItineraryOption, WalkLeg } from "@/types/cityflaneur";
import { sendFeedback } from "@/lib/api";

type Props = {
  option: ItineraryOption;
  selected: boolean;
  context: HyperContext;
  sessionId: string;
  onSelect: () => void;
};

export function RecommendationCard({ option, selected, context, sessionId, onSelect }: Props) {
  async function feedback(action: "save" | "dismiss" | "started_route" | "completed") {
    await sendFeedback(sessionId, option, action, context);
  }

  return (
    <article className={selected ? "recommendation-card selected" : "recommendation-card"}>
      <button className="card-select" type="button" onClick={onSelect}>
        <span>
          <small>{Math.round(option.scores.total * 100)} fit</small>
          {option.title}
        </span>
        <Navigation aria-hidden="true" />
      </button>
      <p>{option.explanation}</p>
      <div className="metrics">
        <span>
          <Clock3 aria-hidden="true" />
          {option.estimated_duration_minutes} min
        </span>
        <span>
          <Footprints aria-hidden="true" />
          {(option.total_walking_m / 1000).toFixed(1)} km
        </span>
        <span>
          <Compass aria-hidden="true" />
          {option.stops.length} stops
        </span>
      </div>
      <div className="score-grid" aria-label={`${option.title} score profile`}>
        <ScoreBar label="Context" value={option.scores.context_fit ?? 0} />
        <ScoreBar label="Effort" value={option.scores.effort ?? 0} />
        <ScoreBar label="Weather" value={option.scores.weather_fit ?? 0} icon="weather" />
        <ScoreBar label="Novelty" value={option.scores.novelty ?? 0} icon="novelty" />
      </div>
      <ol>
        {option.stops.map((stop, index) => {
          const leg = option.walk_legs?.[index];
          return (
            <li key={stop.place_id}>
              {leg && (
                <div className="walk-leg">
                  <Footprints aria-hidden="true" />
                  <span>{leg.walking_minutes} min walk{leg.distance_m > 0 ? ` (${leg.distance_m}m)` : ""}</span>
                  {leg.transit_hint ? (
                    <span className="transit-hint">
                      <Train aria-hidden="true" />
                      {leg.transit_hint}
                    </span>
                  ) : null}
                </div>
              )}
              <strong>{stop.name}</strong>
              <span>
                {stop.role} · {stop.dwell_minutes} min · {stop.arrival_window}
              </span>
              {stop.nearest_subway ? (
                <span className="subway-badge">
                  <Train aria-hidden="true" />
                  {stop.nearest_subway}
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
      {option.caveats.length > 0 ? (
        <div className="caveats">
          {option.caveats.map((caveat) => (
            <span key={caveat}>{caveat}</span>
          ))}
        </div>
      ) : null}
      <div className="card-actions">
        <button type="button" aria-label="Save" onClick={() => feedback("save")}>
          <Heart aria-hidden="true" />
        </button>
        <button type="button" aria-label="Start route" onClick={() => feedback("started_route")}>
          <Check aria-hidden="true" />
        </button>
        <button type="button" aria-label="Dismiss" onClick={() => feedback("dismiss")}>
          <X aria-hidden="true" />
        </button>
      </div>
    </article>
  );
}

function ScoreBar({
  label,
  value,
  icon
}: {
  label: string;
  value: number;
  icon?: "weather" | "novelty";
}) {
  const Icon = icon === "weather" ? CloudSun : icon === "novelty" ? Sparkles : Compass;
  const percent = Math.max(0, Math.min(100, Math.round(value * 100)));

  return (
    <div className="score-row">
      <span>
        <Icon aria-hidden="true" />
        {label}
      </span>
      <div className="score-track">
        <i style={{ width: `${percent}%` }} />
      </div>
      <b>{percent}</b>
    </div>
  );
}
