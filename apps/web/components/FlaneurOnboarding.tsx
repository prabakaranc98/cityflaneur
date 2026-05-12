"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, X } from "lucide-react";
import type { FlaneurProfile } from "@/types/cityflaneur";

type Props = {
  onComplete: (profile: FlaneurProfile | null) => void;
};

type Draft = Omit<FlaneurProfile, "completed_at">;

function isInternational(draft: Draft) {
  return draft.visitor_type === "international_student" || draft.visitor_type === "visitor";
}

const STEPS: {
  key: keyof Draft;
  question: string;
  options: { label: string; value: string; desc: string }[];
}[] = [
  {
    key: "pace",
    question: "How do you move through the city?",
    options: [
      { value: "meander", label: "Wander", desc: "Wherever the street takes me" },
      { value: "moderate", label: "Stroll", desc: "A pace with loose intent" },
      { value: "purposeful", label: "March", desc: "I know where I'm going" },
    ],
  },
  {
    key: "social_comfort",
    question: "How do you feel about crowds?",
    options: [
      { value: "introvert", label: "Quiet corners", desc: "I prefer low-traffic spots" },
      { value: "ambivert", label: "Either way", desc: "Depends on my mood" },
      { value: "extrovert", label: "The buzz", desc: "Energy of a lively street" },
    ],
  },
  {
    key: "familiarity",
    question: "How well do you know Manhattan?",
    options: [
      { value: "tourist", label: "Visiting", desc: "Show me the iconic spots" },
      { value: "occasional", label: "Regular", desc: "I know the basics" },
      { value: "local", label: "Local", desc: "Surprise me off the beaten path" },
    ],
  },
  {
    key: "discovery",
    question: "What kind of finds excite you most?",
    options: [
      { value: "serendipity", label: "Surprises", desc: "The unexpected detour" },
      { value: "balanced", label: "Mix", desc: "Some known, some new" },
      { value: "reliable", label: "Trusted", desc: "Places I know will work" },
    ],
  },
  {
    key: "mobility",
    question: "Any mobility considerations?",
    options: [
      { value: "standard", label: "Standard", desc: "Stairs, hills — no problem" },
      { value: "prefers_flat", label: "Prefer flat", desc: "Avoid steep inclines" },
      { value: "limited", label: "Limited range", desc: "Keep distances short" },
    ],
  },
  {
    key: "spend_strictness",
    question: "How strict is your budget?",
    options: [
      { value: "anything", label: "Flexible", desc: "I don't track closely" },
      { value: "conscious", label: "Mindful", desc: "I notice what I spend" },
      { value: "strict", label: "Strict", desc: "Budget is a hard limit" },
    ],
  },
  {
    key: "visitor_type",
    question: "What's your relationship to the city?",
    options: [
      { value: "resident", label: "I live here", desc: "New York is home" },
      { value: "student", label: "Student", desc: "Studying in the city" },
      { value: "international_student", label: "Intl. student", desc: "Studying here from abroad" },
      { value: "visitor", label: "Visiting", desc: "Just passing through" },
    ],
  },
  {
    key: "origin_region",
    question: "Where are you from?",
    options: [
      { value: "north_america", label: "North America", desc: "US, Canada, Mexico" },
      { value: "europe", label: "Europe", desc: "Including UK" },
      { value: "asia", label: "Asia", desc: "East, South, or Southeast Asia" },
      { value: "latin_america", label: "Latin America", desc: "South & Central America" },
      { value: "rest_of_world", label: "Elsewhere", desc: "Africa, Middle East, Oceania..." },
    ],
  },
];

const DEFAULT_DRAFT: Draft = {
  pace: "moderate",
  social_comfort: "ambivert",
  familiarity: "occasional",
  discovery: "balanced",
  mobility: "standard",
  spend_strictness: "conscious",
  visitor_type: "resident",
  origin_region: "local",
};

const ORIGIN_STEP_IDX = STEPS.findIndex((s) => s.key === "origin_region");

export function FlaneurOnboarding({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>({ ...DEFAULT_DRAFT });

  // Skip origin_region step for residents and students
  const visibleSteps = STEPS.filter((s, i) =>
    i !== ORIGIN_STEP_IDX || isInternational(draft)
  );
  const current = visibleSteps[step];
  const isLast = step === visibleSteps.length - 1;

  function pick(value: string) {
    const update: Partial<Draft> = { [current.key]: value as never };
    // If switching away from international, reset origin_region to local
    if (current.key === "visitor_type" && value !== "international_student" && value !== "visitor") {
      update.origin_region = "local";
    }
    setDraft((prev) => ({ ...prev, ...update }));
  }

  function advance() {
    if (isLast) {
      const profile: FlaneurProfile = { ...draft, completed_at: new Date().toISOString() };
      localStorage.setItem("flaneur_profile", JSON.stringify(profile));
      localStorage.setItem("flaneur_onboarding_seen", "true");
      onComplete(profile);
    } else {
      setStep((s) => s + 1);
    }
  }

  function skip() {
    localStorage.setItem("flaneur_onboarding_seen", "true");
    onComplete(null);
  }

  const selected = draft[current.key];

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-label="Flaneur profile">
      <div className="onboarding-modal">
        <div className="onboarding-header">
          <span className="onboarding-step-count">{step + 1} / {visibleSteps.length}</span>
          <button className="icon-btn" type="button" onClick={skip} title="Skip profile setup" aria-label="Skip">
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="onboarding-progress">
          <div className="onboarding-progress-fill" style={{ width: `${((step + 1) / visibleSteps.length) * 100}%` }} />
        </div>

        <p className="onboarding-question">{current.question}</p>

        <div className="onboarding-options">
          {current.options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`onboarding-option${selected === opt.value ? " active" : ""}`}
              onClick={() => pick(opt.value)}
            >
              <span className="onboarding-option-label">{opt.label}</span>
              <span className="onboarding-option-desc">{opt.desc}</span>
            </button>
          ))}
        </div>

        <div className="onboarding-nav">
          {step > 0 ? (
            <button className="icon-btn" type="button" onClick={() => setStep((s) => s - 1)} aria-label="Previous">
              <ArrowLeft size={16} aria-hidden="true" />
            </button>
          ) : <span />}
          <button className="primary-action onboarding-next" type="button" onClick={advance}>
            {isLast ? "Done" : "Next"}
            {!isLast ? <ArrowRight size={14} aria-hidden="true" /> : null}
          </button>
        </div>
      </div>
    </div>
  );
}
