"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

type Props = { onClose: () => void };

const STEPS: { n: number; title: string; tag: string; body: string; formula?: string }[] = [
  {
    n: 1,
    title: "Context parsing",
    tag: "POST /api/context/parse",
    body: "Your mood, weather, budget, time, interests, and optional note are normalised into a HyperContext. When an LLM adapter is enabled the note is parsed to extract stimulation level, avoidances, and implied interests — these augment but never override your explicit UI choices.",
  },
  {
    n: 2,
    title: "Live POI loading",
    tag: "OpenStreetMap Overpass",
    body: "All named places within your mobility radius are fetched from OpenStreetMap in a single Overpass query, LRU-cached by location so repeat requests in the same area are instant. A fallback catalog of ~55 curated Manhattan places is used if Overpass returns fewer than 8 results.",
  },
  {
    n: 3,
    title: "Candidate plan generation",
    tag: "Beam search w=10",
    body: "Places are scored individually: 32% mood fit, 26% interest fit, 18% proximity, 12% weather, 7% crowd risk, 5% quality. The top 18 seed a beam search that expands routes of 2-4 stops, keeping the 10 best partial routes at each step. Interest-anchored beams run separately for each declared interest. Up to 80 deduplicated candidates are kept.",
  },
  {
    n: 4,
    title: "Transit-aware travel time",
    tag: "~65 subway stations",
    body: "Walk legs use haversine x 1.18 Manhattan grid bias. For legs over 700 m the engine checks if a subway station is within 600 m of both ends and picks the faster option. A subway hint appears on the route card when transit wins.",
    formula: "travel = min(walk, walk_to_station + 2 min wait + ride)",
  },
  {
    n: 5,
    title: "Four-signal composite score",
    tag: "LLM called 3x per request",
    body: "Each candidate gets a fast algorithmic score (11 components). The LLM critic is called only for the final 3 shortlisted plans — not all 80 — keeping latency low. The LinUCB bandit replaces the random exploration bonus with a learned UCB signal.",
    formula: "total = 0.58 * algorithmic + 0.25 * agents + 0.12 * LLM + 0.05 * bandit",
  },
  {
    n: 6,
    title: "Simulated agent panel",
    tag: "5 personas",
    body: "Five rule-based agents vote on each plan: mood_matcher (context fit >= 0.58), friction_guardian (walk effort <= 0.85), comfort_scout (indoor when wet), novelty_editor (category diversity), budget_realist (price cap). Approval = fraction approving x 0.8 + unanimous bonus.",
  },
  {
    n: 7,
    title: "LinUCB bandit exploration",
    tag: "Learns over time",
    body: "A contextual bandit (LinUCB, d=20) replaces the SHA-1 hash exploration bonus. Arms are plan archetypes like cafe_low or museum_medium. The context vector includes all 5 agent scores so the bandit learns which agents are reliable predictors of high LLM critique in each mood/weather situation. Reward is fed back after each LLM score.",
    formula: "UCB = sigmoid(theta*x + alpha * sqrt(x^T * A_inv * x))",
  },
  {
    n: 8,
    title: "Street view on marker click",
    tag: "Mapillary JS SDK",
    body: "Clicking a stop marker fetches Mapillary community photos near that location. If found, the interactive Mapillary 360 degree WebGL viewer opens inline on the map. Fall-back shows a direct Mapillary browse link.",
  },
];

export function HowItWorks({ onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="How Cityflaneur works"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-panel">
        <div className="modal-header">
          <div>
            <p className="modal-eyebrow">Behind the scenes</p>
            <h2 className="modal-title">How it works</h2>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <X size={17} />
          </button>
        </div>

        <div className="pipeline-steps">
          {STEPS.map((step) => (
            <div key={step.n} className="pipeline-step">
              <div className="step-badge">{step.n}</div>
              <div className="step-body">
                <div className="step-header-row">
                  <h3>{step.title}</h3>
                  <span className="step-tag">{step.tag}</span>
                </div>
                <p>{step.body}</p>
                {step.formula ? <div className="formula-box">{step.formula}</div> : null}
              </div>
            </div>
          ))}
        </div>

        <div className="modal-footer">
          <a
            href="http://localhost:8000/health"
            target="_blank"
            rel="noreferrer"
            className="modal-link"
          >
            API health
          </a>
          <a
            href="http://localhost:8000/api/admin/bandit-stats"
            target="_blank"
            rel="noreferrer"
            className="modal-link"
          >
            Bandit stats
          </a>
        </div>
      </div>
    </div>
  );
}
