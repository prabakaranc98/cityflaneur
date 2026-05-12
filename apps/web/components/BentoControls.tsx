"use client";

import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Building2,
  CheckCircle2,
  CloudRain,
  CloudSun,
  Cloudy,
  Coffee,
  Eye,
  Gauge,
  Info,
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
  UserCog,
  UserRound,
  UsersRound,
  WalletCards
} from "lucide-react";
import type { Budget, GroupMode, HyperContext, Interest, Mood, Weather } from "@/types/cityflaneur";
import type { ProgressEvent } from "@/lib/api";
import { fetchWeatherAndTime } from "@/lib/weather";
import { HowItWorks } from "@/components/HowItWorks";

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
  logEvents: ProgressEvent[];
  onChange: (context: HyperContext) => void;
  onSubmit: () => void;
  onOpenProfile?: () => void;
  onLocationFound?: (location: { lat: number; lng: number }) => void;
};

export function BentoControls({ context, loading, logEvents, onChange, onSubmit, onOpenProfile, onLocationFound }: Props) {
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoLabel, setGeoLabel] = useState("Detecting location…");
  const [geoLocked, setGeoLocked] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [weatherLabel, setWeatherLabel] = useState<string | null>(null);
  const [hasManualWeather, setHasManualWeather] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-request GPS on mount — just updates map center, does not submit
  useEffect(() => {
    requestBrowserLocation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logEvents]);

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
      setGeoLabel("GPS unavailable — using midtown default");
      return;
    }
    setGeoBusy(true);
    setGeoLabel("Detecting location…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextLocation = {
          lat: Number(position.coords.latitude.toFixed(5)),
          lng: Number(position.coords.longitude.toFixed(5))
        };
        if (!isWithinManhattanBounds(nextLocation)) {
          setGeoLabel("Outside Manhattan — using midtown default");
          setGeoBusy(false);
          return;
        }
        setGeoLabel(`GPS locked  ±${Math.round(position.coords.accuracy)} m`);
        setGeoLocked(true);
        setGeoBusy(false);
        if (onLocationFound) onLocationFound(nextLocation);
        // Auto-detect weather unless user has manually chosen one
        fetchWeatherAndTime(nextLocation.lat, nextLocation.lng).then((result) => {
          setWeatherLabel(result.label);
          if (!hasManualWeather) {
            patch({
              weather: result.condition,
              weather_auto_detected: true,
              time_signals: result.time_signals,
            });
          }
        });
      },
      (error) => {
        setGeoLabel(geolocationErrorMessage(error) + " — using midtown default");
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
        <div className="control-header-actions">
          {onOpenProfile ? (
            <button
              className="icon-btn"
              type="button"
              title="Your flaneur profile"
              aria-label="Your flaneur profile"
              onClick={onOpenProfile}
            >
              <UserCog size={17} aria-hidden="true" />
            </button>
          ) : null}
          <button
            className="icon-btn"
            type="button"
            title="How it works"
            aria-label="How it works"
            onClick={() => setShowInfo(true)}
          >
            <Info size={17} aria-hidden="true" />
          </button>
          <MapPin aria-hidden="true" />
        </div>
      </div>
      {showInfo ? <HowItWorks onClose={() => setShowInfo(false)} /> : null}

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
          <div className="location-chip" aria-label="Current location">
            <button
              className={`location-chip-btn${geoLocked ? " locked" : ""}`}
              type="button"
              onClick={requestBrowserLocation}
              disabled={geoBusy}
              title="Re-detect GPS location"
            >
              {geoBusy
                ? <Loader2 size={14} className="spin" aria-hidden="true" />
                : <LocateFixed size={14} aria-hidden="true" />}
            </button>
            <span className={`location-chip-label${geoLocked ? "" : " muted"}`}>
              {geoLabel}
            </span>
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
            max={15000}
            step={250}
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
          <label>
            Weather
            {weatherLabel && !hasManualWeather ? (
              <span className="weather-auto-pill" title={weatherLabel}>Auto</span>
            ) : null}
          </label>
          <div className="chip-grid">
            {weather.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.value}
                  className={context.weather === item.value ? "chip active" : "chip"}
                  onClick={() => { setHasManualWeather(true); patch({ weather: item.value, weather_auto_detected: false }); }}
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

      <button className="primary-action" type="button" disabled={loading} onClick={() => onSubmit()}>
        {loading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : null}
        {loading ? "Searching…" : "Find three options"}
        {!loading ? <UsersRound aria-hidden="true" /> : null}
      </button>

      {(loading || logEvents.length > 0) ? (
        <div className="progress-log" aria-live="polite" aria-label="Pipeline progress">
          {logEvents.map((event, i) => (
            <div key={i} className="log-line">
              <CheckCircle2 size={13} className="log-icon done" aria-hidden="true" />
              <span>{event.msg}</span>
            </div>
          ))}
          {loading ? (
            <div className="log-line active">
              <Loader2 size={13} className="spin log-icon" aria-hidden="true" />
              <span>Working…</span>
            </div>
          ) : null}
          <div ref={logEndRef} />
        </div>
      ) : null}
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
