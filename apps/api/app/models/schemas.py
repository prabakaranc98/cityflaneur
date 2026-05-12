from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Mood(StrEnum):
    calm = "calm"
    curious = "curious"
    hungry = "hungry"
    social = "social"
    focused = "focused"
    romantic = "romantic"


class WeatherCondition(StrEnum):
    clear = "clear"
    cloudy = "cloudy"
    rain = "rain"
    snow = "snow"
    cold = "cold"
    hot = "hot"
    windy = "windy"


class Budget(StrEnum):
    free = "free"
    low = "low"
    medium = "medium"
    high = "high"


class GroupMode(StrEnum):
    solo = "solo"
    pair = "pair"
    group = "group"


class Interest(StrEnum):
    food = "food"
    cafes = "cafes"
    books = "books"
    parks = "parks"
    art = "art"
    museums = "museums"
    architecture = "architecture"
    scenic = "scenic"
    history = "history"


class PlaceCategory(StrEnum):
    cafe = "cafe"
    bookstore = "bookstore"
    park = "park"
    gallery = "gallery"
    museum = "museum"
    restaurant = "restaurant"
    landmark = "landmark"
    market = "market"
    scenic = "scenic"


class Pace(StrEnum):
    meander = "meander"
    moderate = "moderate"
    purposeful = "purposeful"


class SocialComfort(StrEnum):
    introvert = "introvert"
    ambivert = "ambivert"
    extrovert = "extrovert"


class NeighborhoodFamiliarity(StrEnum):
    tourist = "tourist"
    occasional = "occasional"
    local = "local"


class DiscoveryPreference(StrEnum):
    serendipity = "serendipity"
    balanced = "balanced"
    reliable = "reliable"


class MobilityLevel(StrEnum):
    standard = "standard"
    prefers_flat = "prefers_flat"
    limited = "limited"


class SpendStrictness(StrEnum):
    anything = "anything"
    conscious = "conscious"
    strict = "strict"


class VisitorType(StrEnum):
    resident = "resident"
    student = "student"
    international_student = "international_student"
    visitor = "visitor"


class OriginRegion(StrEnum):
    north_america = "north_america"
    europe = "europe"
    asia = "asia"
    latin_america = "latin_america"
    rest_of_world = "rest_of_world"
    local = "local"


class FlaneurProfile(BaseModel):
    pace: Pace = Pace.moderate
    social_comfort: SocialComfort = SocialComfort.ambivert
    familiarity: NeighborhoodFamiliarity = NeighborhoodFamiliarity.occasional
    discovery: DiscoveryPreference = DiscoveryPreference.balanced
    mobility: MobilityLevel = MobilityLevel.standard
    spend_strictness: SpendStrictness = SpendStrictness.conscious
    visitor_type: VisitorType = VisitorType.resident
    origin_region: OriginRegion = OriginRegion.local
    completed_at: datetime | None = None


class Coordinates(BaseModel):
    lat: float = Field(..., ge=40.68, le=40.89)
    lng: float = Field(..., ge=-74.05, le=-73.90)


class ContextParseRequest(BaseModel):
    location: Coordinates | None = None
    available_minutes: int | None = Field(default=None, ge=30, le=360)
    local_datetime: datetime | None = None
    weather: WeatherCondition | None = None
    mood: Mood | None = None
    stimulation_level: int | None = Field(default=None, ge=1, le=5)
    budget: Budget | None = None
    group_mode: GroupMode | None = None
    mobility_radius_m: int | None = Field(default=None, ge=500, le=15000)
    interests: list[Interest] | None = None
    note: str | None = Field(default=None, max_length=800)


class HyperContext(BaseModel):
    location: Coordinates = Field(
        default_factory=lambda: Coordinates(lat=40.7359, lng=-73.9911)
    )
    available_minutes: int = Field(default=90, ge=30, le=360)
    local_datetime: datetime | None = None
    weather: WeatherCondition = WeatherCondition.clear
    mood: Mood = Mood.calm
    stimulation_level: int = Field(default=2, ge=1, le=5)
    budget: Budget = Budget.low
    group_mode: GroupMode = GroupMode.solo
    mobility_radius_m: int = Field(default=2600, ge=500, le=15000)
    interests: list[Interest] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=800)
    parsed_signals: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)
    time_signals: dict[str, float | int | bool] | None = None
    weather_auto_detected: bool = False
    profile: FlaneurProfile | None = None

    @field_validator("interests")
    @classmethod
    def dedupe_interests(cls, interests: list[Interest]) -> list[Interest]:
        seen: set[Interest] = set()
        deduped: list[Interest] = []
        for interest in interests:
            if interest not in seen:
                seen.add(interest)
                deduped.append(interest)
        return deduped


class Place(BaseModel):
    id: str
    name: str
    category: PlaceCategory
    coordinates: Coordinates
    neighborhood: str
    tags: list[str] = Field(default_factory=list)
    atmosphere_tags: list[str] = Field(default_factory=list)
    opening_hours: dict[str, list[str]] = Field(default_factory=dict)
    price_level: int = Field(default=1, ge=0, le=4)
    rating: float = Field(default=4.0, ge=0.0, le=5.0)
    quality_signals: dict[str, float | int | str] = Field(default_factory=dict)
    source: str
    source_id: str
    attribution: str
    indoor: bool = True
    embedding: list[float] = Field(default_factory=list)


class WalkLeg(BaseModel):
    from_name: str
    to_name: str
    distance_m: int
    walking_minutes: int
    transit_hint: str | None = None


class ItineraryStop(BaseModel):
    place_id: str
    name: str
    category: PlaceCategory
    coordinates: Coordinates
    neighborhood: str
    role: str
    dwell_minutes: int
    arrival_window: str
    indoor: bool
    nearest_subway: str | None = None
    walk_from_previous_m: int | None = None


class RouteGeometry(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]]


class ItineraryOption(BaseModel):
    id: str
    title: str
    stops: list[ItineraryStop]
    route_geometry: RouteGeometry
    estimated_duration_minutes: int
    total_walking_m: int
    scores: dict[str, float]
    explanation: str
    caveats: list[str] = Field(default_factory=list)
    walk_legs: list[WalkLeg] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    context: HyperContext
    recommendations: list[ItineraryOption]
    catalog_version: str
    generated_at: datetime


class PlacesResponse(BaseModel):
    places: list[Place]
    count: int


class GridCell(BaseModel):
    id: str
    center: Coordinates
    bounds: list[Coordinates]
    x_index: int
    y_index: int
    cell_size_m: int
    place_count: int
    top_categories: list[PlaceCategory]
    neighborhoods: list[str]


class GridCellsResponse(BaseModel):
    cells: list[GridCell]
    count: int


class FeedbackAction(StrEnum):
    save = "save"
    dismiss = "dismiss"
    started_route = "started_route"
    completed = "completed"
    rating = "rating"
    show_calmer = "show_calmer"
    more_social = "more_social"
    closer = "closer"


class FeedbackEvent(BaseModel):
    session_id: str = Field(..., min_length=3, max_length=120)
    itinerary_id: str
    action: FeedbackAction
    rating: int | None = Field(default=None, ge=1, le=5)
    context_snapshot: HyperContext | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackResponse(BaseModel):
    accepted: bool
    stored_events: int


class PulseItem(BaseModel):
    title: str
    summary: str
    url: str | None = None
    source: str
    published_at: datetime | None = None


class NeighborhoodPulse(BaseModel):
    neighborhood: str
    trivia: list[PulseItem] = Field(default_factory=list)
    headlines: list[PulseItem] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_note: str


class NeighborhoodPulseResponse(BaseModel):
    pulses: list[NeighborhoodPulse]
    count: int


class StreetSceneImage(BaseModel):
    id: str
    source: Literal["mapillary", "google_street_view"]
    title: str
    image_url: str
    page_url: str | None = None
    coordinates: Coordinates | None = None
    captured_at: datetime | None = None
    attribution: str
    provider_status: str = "ok"


class StreetScenesResponse(BaseModel):
    query: Coordinates
    images: list[StreetSceneImage] = Field(default_factory=list)
    provider_status: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_note: str
