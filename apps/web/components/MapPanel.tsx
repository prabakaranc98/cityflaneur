"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl, { type Map, type Marker } from "maplibre-gl";
import { getGridCells, getStreetScenes } from "@/lib/api";
import { MapillaryViewer } from "@/components/MapillaryViewer";
import type { GridCell, HyperContext, ItineraryOption } from "@/types/cityflaneur";

const MAPILLARY_TOKEN = process.env.NEXT_PUBLIC_MAPILLARY_ACCESS_TOKEN ?? "";

type Props = {
  context: HyperContext;
  selected: ItineraryOption | null;
};

type StreetViewStop = {
  name: string;
  neighborhood: string;
  lat: number;
  lng: number;
  mapillaryImageId: string | null;
  loading: boolean;
};

export function MapPanel({ context, selected }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [gridCells, setGridCells] = useState<GridCell[]>([]);
  const [streetView, setStreetView] = useState<StreetViewStop | null>(null);

  useEffect(() => {
    let mounted = true;
    getGridCells()
      .then((response) => {
        if (mounted) {
          setGridCells(response.cells);
        }
      })
      .catch(() => {
        if (mounted) {
          setGridCells([]);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [context.location.lng, context.location.lat],
      zoom: 13.4,
      pitch: 38,
      bearing: -10,
      style: {
        version: 8,
        sources: {
          carto: {
            type: "raster",
            tiles: [
              "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
              "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
              "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
              "https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png"
            ],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors © CARTO"
          }
        },
        layers: [
          {
            id: "carto-voyager",
            type: "raster",
            source: "carto",
            paint: {
              "raster-opacity": 0.98,
              "raster-resampling": "linear"
            }
          }
        ]
      }
    });
    map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }),
      "top-right"
    );
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [context.location.lat, context.location.lng]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    map.flyTo({
      center: [context.location.lng, context.location.lat],
      zoom: 13.4,
      pitch: 38,
      bearing: -10,
      essential: true
    });
  }, [context.location.lat, context.location.lng]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const updateGrid = () => {
      const data = buildGridGeoJson(gridCells);
      const source = map.getSource("grid-cells") as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(data);
        return;
      }
      map.addSource("grid-cells", { type: "geojson", data });
      map.addLayer({
        id: "grid-cell-fill",
        type: "fill",
        source: "grid-cells",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "place_count"],
            1,
            "rgba(31, 111, 139, 0.08)",
            3,
            "rgba(228, 87, 46, 0.16)",
            5,
            "rgba(228, 87, 46, 0.28)"
          ],
          "fill-opacity": 0.8
        }
      });
      map.addLayer({
        id: "grid-cell-line",
        type: "line",
        source: "grid-cells",
        paint: {
          "line-color": "rgba(31, 37, 40, 0.18)",
          "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.4, 15, 1.3]
        }
      });
    };

    if (map.isStyleLoaded()) {
      updateGrid();
    } else {
      map.once("load", updateGrid);
    }
  }, [gridCells]);

  useEffect(() => {
    setStreetView(null);
  }, [selected?.id]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) {
      return;
    }

    const updateRoute = () => {
      const data = buildRouteGeoJson(selected);
      const source = map.getSource("route") as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(data);
      } else {
        map.addSource("route", { type: "geojson", data });
        map.addLayer({
          id: "route-casing",
          type: "line",
          source: "route",
          layout: {
            "line-cap": "round",
            "line-join": "round"
          },
          paint: {
            "line-color": "#ffffff",
            "line-width": ["interpolate", ["linear"], ["zoom"], 12, 7, 16, 12],
            "line-opacity": 0.92
          }
        });
        map.addLayer({
          id: "route-line",
          type: "line",
          source: "route",
          layout: {
            "line-cap": "round",
            "line-join": "round"
          },
          paint: {
            "line-color": "#e4572e",
            "line-width": ["interpolate", ["linear"], ["zoom"], 12, 3, 16, 6],
            "line-opacity": 0.94
          }
        });
      }
    };

    if (map.isStyleLoaded()) {
      updateRoute();
    } else {
      map.once("load", updateRoute);
    }

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    const startMarker = new maplibregl.Marker({
      element: markerElement("S", "start")
    })
      .setLngLat([context.location.lng, context.location.lat])
      .setPopup(new maplibregl.Popup({ offset: 18 }).setDOMContent(popupNode("Start", "Current context")))
      .addTo(map);
    markersRef.current.push(startMarker);

    selected.stops.forEach((stop, index) => {
      const el = markerElement(String(index + 1), index === 0 ? "first" : "stop");
      el.title = `${stop.name} — click for street view`;
      el.style.cursor = "pointer";
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([stop.coordinates.lng, stop.coordinates.lat])
        .addTo(map);
      el.addEventListener("click", () => {
        const lat = stop.coordinates.lat;
        const lng = stop.coordinates.lng;
        setStreetView({ name: stop.name, neighborhood: stop.neighborhood, lat, lng, mapillaryImageId: null, loading: true });
        getStreetScenes(lat, lng, 3).then((res) => {
          const mapillaryImg = res.images.find((img) => img.source === "mapillary");
          // Image IDs come back as "mapillary:297628248839671" — strip the prefix
          const rawId = mapillaryImg?.id ?? "";
          const imageId = rawId.startsWith("mapillary:") ? rawId.slice("mapillary:".length) : rawId;
          setStreetView((prev) =>
            prev && prev.lat === lat ? { ...prev, mapillaryImageId: imageId || null, loading: false } : prev
          );
        }).catch(() => {
          setStreetView((prev) => prev && prev.lat === lat ? { ...prev, loading: false } : prev);
        });
      });
      markersRef.current.push(marker);
    });

    const bounds = new maplibregl.LngLatBounds();
    selected.route_geometry.coordinates.forEach((coordinate) => bounds.extend(coordinate));
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 80, maxZoom: 15.5, duration: 700 });
    }
  }, [context.location.lat, context.location.lng, selected]);

  return (
    <div className="map-wrap">
      <div ref={containerRef} className="map-panel" aria-label="Manhattan itinerary map" />

      {streetView && !streetView.loading && streetView.mapillaryImageId && MAPILLARY_TOKEN ? (
        <MapillaryViewer
          key={streetView.mapillaryImageId}
          imageId={streetView.mapillaryImageId}
          accessToken={MAPILLARY_TOKEN}
          stopName={streetView.name}
          neighborhood={streetView.neighborhood}
          onClose={() => setStreetView(null)}
        />
      ) : streetView ? (
        <div className="sv-overlay" role="dialog" aria-label={`Street view: ${streetView.name}`}>
          <div className="sv-header">
            <div>
              <strong>{streetView.name}</strong>
              <span>{streetView.neighborhood}</span>
            </div>
            <button className="sv-close" onClick={() => setStreetView(null)} aria-label="Close">✕</button>
          </div>
          <div className="sv-loading">
            {streetView.loading ? "Finding street imagery…" : "No Mapillary imagery at this location."}
          </div>
          {!streetView.loading ? (
            <div className="sv-actions">
              <a
                href={`https://www.mapillary.com/app/?lat=${streetView.lat}&lng=${streetView.lng}&z=17`}
                target="_blank" rel="noreferrer" className="sv-btn-secondary"
              >
                Browse Mapillary near here ↗
              </a>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="map-hud" aria-label="Map legend">
        <span>
          <i className="legend-route" />
          Route
        </span>
        <span>
          <i className="legend-grid" />
          POI grid
        </span>
        {selected ? (
          <span className="map-hud-hint">Click a stop marker for street view</span>
        ) : null}
        {selected ? <strong>{selected.estimated_duration_minutes} min</strong> : null}
      </div>
    </div>
  );
}

function buildRouteGeoJson(selected: ItineraryOption): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: selected.route_geometry
      }
    ]
  };
}

function buildGridGeoJson(cells: GridCell[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: cells.map((cell) => {
      const ring = cell.bounds.map((point) => [point.lng, point.lat]);
      if (ring.length > 0) {
        ring.push(ring[0]);
      }
      return {
        type: "Feature",
        properties: {
          id: cell.id,
          place_count: cell.place_count,
          label: cell.neighborhoods.slice(0, 2).join(", "),
          cell_size_m: cell.cell_size_m
        },
        geometry: {
          type: "Polygon",
          coordinates: [ring]
        }
      };
    })
  };
}

function markerElement(label: string, variant: "start" | "first" | "stop"): HTMLDivElement {
  const marker = document.createElement("div");
  marker.className = `map-marker ${variant}`;
  marker.textContent = label;
  return marker;
}

function popupNode(title: string, subtitle: string): HTMLDivElement {
  const node = document.createElement("div");
  node.className = "map-popup";

  const heading = document.createElement("strong");
  heading.textContent = title;
  node.appendChild(heading);

  const detail = document.createElement("span");
  detail.textContent = subtitle;
  node.appendChild(detail);

  return node;
}
