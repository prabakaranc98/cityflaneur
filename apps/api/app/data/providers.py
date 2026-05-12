from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.schemas import Place


class PlaceProvider(Protocol):
    name: str

    async def fetch_places(self) -> list[Place]:
        ...


@dataclass(frozen=True)
class OSMOverpassProvider:
    """Adapter placeholder for OpenStreetMap Overpass ingestion."""

    endpoint: str = "https://overpass-api.de/api/interpreter"
    name: str = "osm_overpass"

    async def fetch_places(self) -> list[Place]:
        raise NotImplementedError("Wire this adapter to app.data.ingestion.normalize_osm_feature.")


@dataclass(frozen=True)
class NYCOpenDataProvider:
    """Adapter placeholder for Socrata-backed NYC Open Data datasets."""

    base_url: str = "https://data.cityofnewyork.us/resource"
    name: str = "nyc_open_data"

    async def fetch_places(self) -> list[Place]:
        raise NotImplementedError("Wire this adapter to Socrata SODA datasets.")


@dataclass(frozen=True)
class NWSWeatherProvider:
    """Adapter placeholder for National Weather Service point forecasts."""

    base_url: str = "https://api.weather.gov"
    name: str = "nws_weather"

    async def fetch_forecast(self, lat: float, lng: float) -> dict:
        raise NotImplementedError("Fetch /points/{lat},{lng} then the returned forecast URL.")


@dataclass(frozen=True)
class CommercialPlaceProvider:
    """Paid/provider boundary for future reviews, ratings, hours, and photos."""

    name: str

    async def fetch_places(self) -> list[Place]:
        raise NotImplementedError("Commercial providers must preserve attribution and cache rules.")

