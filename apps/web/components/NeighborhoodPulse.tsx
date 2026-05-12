"use client";

import { Newspaper, Sparkles } from "lucide-react";
import type { NeighborhoodPulse as NeighborhoodPulseType } from "@/types/cityflaneur";

type Props = {
  pulses: NeighborhoodPulseType[];
  loading: boolean;
};

export function NeighborhoodPulse({ pulses, loading }: Props) {
  return (
    <section className="pulse-panel" aria-label="Neighborhood pulse">
      <div className="pulse-header">
        <div>
          <p>Pulse</p>
          <h3>Neighborhood texture</h3>
        </div>
        {loading ? <span>Loading</span> : <span>{pulses.length} areas</span>}
      </div>
      {pulses.length === 0 ? (
        <div className="pulse-empty">Select a route to load local context.</div>
      ) : (
        pulses.map((pulse) => (
          <article key={pulse.neighborhood} className="pulse-neighborhood">
            <div className="pulse-neighborhood-title">
              <strong>{pulse.neighborhood}</strong>
              <span>{pulse.source_note}</span>
            </div>
            <div className="pulse-items">
              {[...pulse.trivia, ...pulse.headlines].slice(0, 4).map((item) => {
                const Icon = item.source === "exa" ? Newspaper : Sparkles;
                const content = (
                  <>
                    <Icon aria-hidden="true" />
                    <span>
                      <b>{item.title}</b>
                      <small>{item.summary}</small>
                    </span>
                  </>
                );
                return item.url ? (
                  <a key={`${item.source}-${item.title}`} href={item.url} target="_blank" rel="noreferrer">
                    {content}
                  </a>
                ) : (
                  <div key={`${item.source}-${item.title}`}>{content}</div>
                );
              })}
            </div>
          </article>
        ))
      )}
    </section>
  );
}

