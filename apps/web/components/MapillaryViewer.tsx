"use client";

import { useEffect, useRef } from "react";
import "mapillary-js/dist/mapillary.css";

type Props = {
  imageId: string;
  accessToken: string;
  onClose: () => void;
  stopName: string;
  neighborhood: string;
};

export function MapillaryViewer({ imageId, accessToken, onClose, stopName, neighborhood }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<unknown>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;

    // Dynamic import avoids SSR issues with the WebGL viewer
    import("mapillary-js").then(({ Viewer }) => {
      if (destroyed || !containerRef.current) return;

      const viewer = new Viewer({
        accessToken,
        container: containerRef.current,
        imageId,
        component: {
          cover: false,
          bearing: false,
          attribution: true,
          keyboard: true,
          zoom: false,
        },
      });

      viewerRef.current = viewer;

      // Ensure viewer resizes if its container changes size
      const ro = new ResizeObserver(() => {
        try { (viewer as { resize?: () => void }).resize?.(); } catch { /* ignore */ }
      });
      ro.observe(containerRef.current!);

      return () => {
        ro.disconnect();
      };
    });

    return () => {
      destroyed = true;
      const v = viewerRef.current as { remove?: () => void } | null;
      try { v?.remove?.(); } catch { /* ignore */ }
      viewerRef.current = null;
    };
  // imageId change navigates to new photo; accessToken is stable
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Navigate to a different image when imageId prop changes without remounting
  useEffect(() => {
    const v = viewerRef.current as { moveTo?: (id: string) => Promise<unknown> } | null;
    if (v?.moveTo) {
      v.moveTo(imageId).catch(() => {/* ignore */});
    }
  }, [imageId]);

  const googleUrl = `https://maps.google.com/maps?q=&layer=c&cbll=0,0`;

  return (
    <div className="sv-overlay" role="dialog" aria-label={`Street view: ${stopName}`}>
      <div className="sv-header">
        <div>
          <strong>{stopName}</strong>
          <span>{neighborhood} · Mapillary 360°</span>
        </div>
        <button className="sv-close" onClick={onClose} aria-label="Close street view">✕</button>
      </div>

      {/* Mapillary WebGL viewer fills the remaining space */}
      <div ref={containerRef} className="sv-viewer-canvas" />

      <div className="sv-actions">
        <a
          href={`https://www.mapillary.com/app/?pKey=${imageId}`}
          target="_blank"
          rel="noreferrer"
          className="sv-btn-secondary"
        >
          Open full Mapillary viewer ↗
        </a>
      </div>
    </div>
  );
}
