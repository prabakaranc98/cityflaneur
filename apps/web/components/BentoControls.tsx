"use client";

import { useState } from "react";
import {
  BookOpen,
  Building2,
  CloudRain,
  CloudSun,
  Cloudy,
  Coffee,
  Eye,
  Gauge,
  Landmark,
  Loader2,
  LocateFixed,
  MapPin,
  Moon,
  Palette,
  Snowflake,
  SunMedium,
  ThermometerSun,
  Trees,
  UserRound,
  UsersRound,
  WalletCards
} from "lucide-react";
import type { Budget, GroupMode, HyperContext, Interest, Mood, Weather } from "@/types/cityflaneur";

const moods = [
  { label: "Calm", value: "calm", icon: Moon },
  { label: "Curious", value: "curious", icon: Eye },
  { label: "Hungry", value: "hungry", icon: Coffee },
  { label: "Social", value: "social", icon: UsersRound },
  { label: "Focused", value: "focused", icon: BookOpen },
  { label: "Date", value: "romantic", icon: SunMedium }
] satisfies { label: string; value: Mood; icon: typeof Moon }[];

const weather = [
  { label: "Clear", value: "clear", icon: CloudSun },
  { label: "Cloudy", value: "cloudy", icon: Cloudy },
  { label: "Rain", value: "rain", icon: CloudRain },
  { label: "Cold", value: "cold", icon: Snowflake },
  { label: "Hot", value: "hot", icon: ThermometerSun }
] satisfies { label: string; value: Weather; icon: typeof Moon }[];

const interests = [
  { label: "Food", value: "food", icon: Coffee },
  { label: "Coffee", value: "cafes", icon: Coffee },
  { label: "Books", value: "books", icon: BookOpen },
  { label: "Parks", value: "parks", icon: Trees },
  { label: "Art", value: "art", icon: Palette },
  { label: "Museums", value: "museums", icon: Landmark },
  { label: "Streets", value: "architecture", icon: Building2 },
  { label: "Views", value: "scenic", icon: Eye }
] satisfies { label: string; value: Interest; icon: typeof Moon }[];

const budgets: { label: string; value: Budget }[] = [
  { label: "Free", value: "free" },
  { label: "$", value: "low" },
  { label: "$$", value: "medium" },
  { label: "$$$", value: "high" }
];

const groups: { label: string; value: GroupMode }[] = [
  { label: "Solo", value: "solo" },
  { label: "Pair", value: "pair" },
  { label: "Group", value: "group" }
];

const MANHATTAN_BOUNDS = {
  minLat: 40.68,
  maxLat: 40.89,
  minLng: -74.05,
  maxLng: -73.9
};

type Props = {
  context: HyperContext;
  loading: boolean;
  onChange: (context: HyperContext) => void;
  onSubmit: () => void;
};

export function BentoControls({ context, loading, onChange, onSubmit }: Props) {
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoStatus, setGeoStatus] = useState("Manual start");

  function patch(update: Partial<HyperContext>) {
    onChange({ ...context, ...update });
  }

  function toggleInterest(value: Interest) {
    const next = context.interests.includes(value)
      ? context.interests.filter((interest) => interest !== value)
      : [...context.interests, value];
    patch({ interests: next });
  }

  function requestBrowserLocation() {
    if (!navigator.geolocation) {
      setGeoStatus("GPS unavailable in this browser");
      return;
    }

    setGeoBusy(true);
    setGeoStatus("Locating");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextLocation = {
          lat: Number(position.coords.latitude.toFixed(5)),
          lng: Number(position.coords.longitude.toFixed(5))
        };
        if (!isWithinManhattanBounds(nextLocation)) {
          setGeoStatus("GPS outside Manhattan MVP");
          setGeoBusy(false);
          return;
        }

        patch({
          location: nextLocation,
          parsed_signals: {
            ...(context.parsed_signals ?? {}),
            location_source: "browser_gps",
            location_accuracy_m: Math.round(position.coords.accuracy)
          }
        });
        setGeoStatus(`GPS +- ${Math.round(position.coords.accuracy)}m`);
        setGeoBusy(false);
      },
      (error) => {
        setGeoStatus(geolocationErrorMessage(error));
        setGeoBusy(false);
      },
      { enableHighAccuracy: true, maximumAge: 60_000, timeout: 10_000 }
    );
  }

  return (
    <section className="control-panel" aria-label="Trip controls">
      <div className="control-header">
        <div>
          <p>Cityflaneur</p>
          <h1>Manhattan now</h1>
        </div>
        <MapPin aria-hidden="true" />
      </div>

      <div className="context-strip" aria-label="Current context">
        <span>
          <Gauge aria-hidden="true" />
          {context.available_minutes}m
        </span>
        <span>
          <WalletCards aria-hidden="true" />
          {context.budget}
        </span>
        <span>
          <UserRound aria-hidden="true" />
          {context.group_mode}
        </span>
      </div>

      <div className="bento-grid">
        <div className="bento-block wide">
          <label>Start</label>
          <div className="location-tools">
            <button className="gps-button" type="button" onClick={requestBrowserLocation} disabled={geoBusy}>
              {geoBusy ? <Loader2 className="spin" aria-hidden="true" /> : <LocateFixed aria-hidden="true" />}
              Use GPS
            </button>
            <span className={geoStatus.includes("outside") || geoStatus.includes("unavailable") ? "location-status warning" : "location-status"}>
              {geoStatus}
            </span>
          </div>
          <div className="location-row">
            <input
              type="number"
              step="0.0001"
              value={context.location.lat}
              onChange={(event) =>
                patch({ location: { ...context.location, lat: Number(event.target.value) } })
              }
              aria-label="Latitude"
            />
            <input
              type="number"
              step="0.0001"
              value={context.location.lng}
              onChange={(event) =>
                patch({ location: { ...context.location, lng: Number(event.target.value) } })
              }
              aria-label="Longitude"
            />
          </div>
        </div>

        <div className="bento-block">
          <label htmlFor="minutes">Minutes</label>
          <input
            id="minutes"
            type="range"
            min={30}
            max={360}
            step={15}
            value={context.available_minutes}
            onChange={(event) => patch({ available_minutes: Number(event.target.value) })}
          />
          <div className="range-value">{context.available_minutes} min</div>
        </div>

        <div className="bento-block">
          <label htmlFor="radius">Radius</label>
          <input
            id="radius"
            type="range"
            min={500}
            max={8000}
            step={100}
            value={context.mobility_radius_m}
            onChange={(event) => patch({ mobility_radius_m: Number(event.target.value) })}
          />
          <div className="range-value">{(context.mobility_radius_m / 1000).toFixed(1)} km</div>
        </div>

        <div className="bento-block wide">
          <label htmlFor="stimulation">Energy</label>
          <input
            id="stimulation"
            type="range"
            min={1}
            max={5}
            step={1}
            value={context.stimulation_level}
            onChange={(event) => patch({ stimulation_level: Number(event.target.value) })}
          />
          <div className="range-value">{context.stimulation_level}/5</div>
        </div>

        <div className="bento-block wide">
          <label>Mood</label>
          <div className="chip-grid">
            {moods.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.value}
                  className={context.mood === item.value ? "chip active" : "chip"}
                  onClick={() => patch({ mood: item.value })}
                  type="button"
                >
                  <Icon aria-hidden="true" />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="bento-block wide">
          <label>Weather</label>
          <div className="chip-grid">
            {weather.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.value}
                  className={context.weather === item.value ? "chip active" : "chip"}
                  onClick={() => patch({ weather: item.value })}
                  type="button"
                >
                  <Icon aria-hidden="true" />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="bento-block wide">
          <label>Interests</label>
          <div className="chip-grid">
            {interests.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.value}
                  className={context.interests.includes(item.value) ? "chip active" : "chip"}
                  onClick={() => toggleInterest(item.value)}
                  type="button"
                >
                  <Icon aria-hidden="true" />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="bento-block">
          <label>Budget</label>
          <div className="segment-row">
            {budgets.map((item) => (
              <button
                key={item.value}
                className={context.budget === item.value ? "segment active" : "segment"}
                type="button"
                onClick={() => patch({ budget: item.value })}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="bento-block">
          <label>Group</label>
          <div className="segment-row">
            {groups.map((item) => (
              <button
                key={item.value}
                className={context.group_mode === item.value ? "segment active" : "segment"}
                type="button"
                onClick={() => patch({ group_mode: item.value })}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="bento-block wide">
          <label htmlFor="note">Optional note</label>
          <textarea
            id="note"
            value={context.note ?? ""}
            onChange={(event) => patch({ note: event.target.value })}
            placeholder="quiet coffee and books, rainy evening"
          />
        </div>
      </div>

      <button className="primary-action" type="button" disabled={loading} onClick={onSubmit}>
        {loading ? "Finding routes" : "Find three options"}
        <UsersRound aria-hidden="true" />
      </button>
    </section>
  );
}

function isWithinManhattanBounds(location: { lat: number; lng: number }) {
  return (
    location.lat >= MANHATTAN_BOUNDS.minLat &&
    location.lat <= MANHATTAN_BOUNDS.maxLat &&
    location.lng >= MANHATTAN_BOUNDS.minLng &&
    location.lng <= MANHATTAN_BOUNDS.maxLng
  );
}

function geolocationErrorMessage(error: GeolocationPositionError) {
  if (error.code === error.PERMISSION_DENIED) {
    return "GPS permission denied";
  }
  if (error.code === error.TIMEOUT) {
    return "GPS timed out";
  }
  return "GPS unavailable";
}
