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

export type Coordinates = {
  lat: number;
  lng: number;
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
};

export type RouteGeometry = {
  type: "LineString";
  coordinates: [number, number][];
};

export type ItineraryOption = {
  id: string;
  title: string;
  stops: ItineraryStop[];
  route_geometry: RouteGeometry;
  estimated_duration_minutes: number;
  total_walking_m: number;
  scores: Record<string, number>;
  explanation: string;
  caveats: string[];
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
