export type Mood = "calm" | "curious" | "hungry" | "social" | "focused" | "romantic";
export type Weather = "clear" | "cloudy" | "rain" | "snow" | "cold" | "hot" | "windy";
export type Budget = "free" | "low" | "medium" | "high";
export type GroupMode = "solo" | "pair" | "group";
export type Interest =
  | "food"
  | "cafes"
  | "books"
  | "parks"
  | "art"
  | "museums"
  | "architecture"
  | "scenic"
  | "history";

export type FlaneurProfile = {
  pace: "meander" | "moderate" | "purposeful";
  social_comfort: "introvert" | "ambivert" | "extrovert";
  familiarity: "tourist" | "occasional" | "local";
  discovery: "serendipity" | "balanced" | "reliable";
  mobility: "standard" | "prefers_flat" | "limited";
  spend_strictness: "anything" | "conscious" | "strict";
  visitor_type: "resident" | "student" | "international_student" | "visitor";
  origin_region: "north_america" | "europe" | "asia" | "latin_america" | "rest_of_world" | "local";
  completed_at: string;
};

export type Coordinates = {
  lat: number;
  lng: number;
};

export type TimeSignals = {
  hour_of_day: number;
  day_of_week: number;
  is_rush_hour: boolean;
  minutes_to_sunset: number;
  is_weekend: boolean;
};

export type HyperContext = {
  location: Coordinates;
  available_minutes: number;
  local_datetime?: string | null;
  weather: Weather;
  mood: Mood;
  stimulation_level: number;
  budget: Budget;
  group_mode: GroupMode;
  mobility_radius_m: number;
  interests: Interest[];
  note?: string | null;
  parsed_signals?: Record<string, unknown>;
  time_signals?: TimeSignals;
  weather_auto_detected?: boolean;
  profile?: FlaneurProfile;
};

export type WalkLeg = {
  from_name: string;
  to_name: string;
  distance_m: number;
  walking_minutes: number;
  transit_hint?: string | null;
};

export type ItineraryStop = {
  place_id: string;
  name: string;
  category: string;
  coordinates: Coordinates;
  neighborhood: string;
  role: string;
  dwell_minutes: number;
  arrival_window: string;
  indoor: boolean;
  nearest_subway?: string | null;
  walk_from_previous_m?: number | null;
};

export type RouteGeometry = {
  type: "LineString";
  coordinates: [number, number][];
};

export type ItineraryScores = {
  total: number;
  total_uncertainty?: number;
  algorithmic_score: number;
  context_fit: number;
  effort: number;
  duration_fit: number;
  budget_fit: number;
  weather_fit: number;
  crowd_fit: number;
  quality: number;
  novelty: number;
  diversity: number;
  personalization: number;
  agent_approval: number;
  agent_approval_sigma?: number;
  llm_critique: number;
  exploration_bonus: number;
  exploration_fraction: number;
  [key: string]: number | undefined;
};

export type ItineraryOption = {
  id: string;
  title: string;
  stops: ItineraryStop[];
  route_geometry: RouteGeometry;
  estimated_duration_minutes: number;
  total_walking_m: number;
  scores: ItineraryScores;
  explanation: string;
  caveats: string[];
  walk_legs: WalkLeg[];
};

export type RecommendationsResponse = {
  context: HyperContext;
  recommendations: ItineraryOption[];
  catalog_version: string;
  generated_at: string;
};

export type GridCell = {
  id: string;
  center: Coordinates;
  bounds: Coordinates[];
  x_index: number;
  y_index: number;
  cell_size_m: number;
  place_count: number;
  top_categories: string[];
  neighborhoods: string[];
};

export type GridCellsResponse = {
  cells: GridCell[];
  count: number;
};

export type PulseItem = {
  title: string;
  summary: string;
  url?: string | null;
  source: string;
  published_at?: string | null;
};

export type NeighborhoodPulse = {
  neighborhood: string;
  trivia: PulseItem[];
  headlines: PulseItem[];
  generated_at: string;
  source_note: string;
};

export type NeighborhoodPulseResponse = {
  pulses: NeighborhoodPulse[];
  count: number;
};

export type StreetSceneImage = {
  id: string;
  source: "mapillary" | "google_street_view";
  title: string;
  image_url: string;
  page_url?: string | null;
  coordinates?: Coordinates | null;
  captured_at?: string | null;
  attribution: string;
  provider_status: string;
};

export type StreetScenesResponse = {
  query: Coordinates;
  images: StreetSceneImage[];
  provider_status: Record<string, string>;
  generated_at: string;
  source_note: string;
};
