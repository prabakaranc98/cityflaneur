"use client";

import { useEffect, useState } from "react";
import { Camera, ExternalLink } from "lucide-react";
import { getStreetScenes } from "@/lib/api";
import type { ItineraryOption, StreetSceneImage } from "@/types/cityflaneur";

type SceneWithStop = StreetSceneImage & {
  stopName: string;
  stopNeighborhood: string;
};

type Props = {
  selected: ItineraryOption | null;
};

export function StreetScenes({ selected }: Props) {
  const [scenes, setScenes] = useState<SceneWithStop[]>([]);
  const [sourceNote, setSourceNote] = useState("street imagery");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selected) {
      setScenes([]);
      return;
    }

    let mounted = true;
    setLoading(true);
    Promise.all(
      selected.stops.slice(0, 3).map(async (stop) => {
        const response = await getStreetScenes(stop.coordinates.lat, stop.coordinates.lng, 2);
        return {
          response,
          stopName: stop.name,
          stopNeighborhood: stop.neighborhood
        };
      })
    )
      .then((results) => {
        if (!mounted) {
          return;
        }
        const nextScenes = results.flatMap(({ response, stopName, stopNeighborhood }) =>
          response.images.map((image) => ({ ...image, stopName, stopNeighborhood }))
        );
        const notes = Array.from(new Set(results.map(({ response }) => response.source_note)));
        setScenes(nextScenes.slice(0, 6));
        setSourceNote(notes.join(" · "));
      })
      .catch(() => {
        if (mounted) {
          setScenes([]);
          setSourceNote("street imagery unavailable");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [selected]);

  if (!selected) {
    return null;
  }

  return (
    <section className="streetscape-panel" aria-label="Street scenes for selected route">
      <div className="streetscape-header">
        <div>
          <p>Street view</p>
          <h3>Scenes near stops</h3>
        </div>
        <span>{loading ? "Loading" : sourceNote}</span>
      </div>
      {scenes.length > 0 ? (
        <div className="scene-strip">
          {scenes.map((scene) => {
            const content = (
              <>
                <img src={scene.image_url} alt={`${scene.stopName} street scene`} loading="lazy" />
                <span>
                  <b>{scene.stopName}</b>
                  <small>
                    {scene.source === "google_street_view" ? "Google Street View" : "Mapillary"} ·{" "}
                    {scene.stopNeighborhood}
                  </small>
                </span>
                {scene.page_url ? <ExternalLink aria-hidden="true" /> : null}
              </>
            );
            return scene.page_url ? (
              <a key={scene.id} href={scene.page_url} target="_blank" rel="noreferrer" className="scene-card">
                {content}
              </a>
            ) : (
              <div key={scene.id} className="scene-card">
                {content}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="streetscape-empty">
          <Camera aria-hidden="true" />
          <span>{loading ? "Checking nearby imagery" : sourceNote}</span>
        </div>
      )}
    </section>
  );
}
