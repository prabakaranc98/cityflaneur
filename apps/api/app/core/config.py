from __future__ import annotations

import os
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel

load_dotenv(find_dotenv(usecwd=True))


class Settings(BaseModel):
    app_name: str = "Cityflaneur API"
    environment: str = os.getenv("CITYFLANEUR_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://cityflaneur:cityflaneur@localhost:5432/cityflaneur",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    default_catalog_version: str = "seed-manhattan-v1"
    enable_llm_adapters: bool = os.getenv("ENABLE_LLM_ADAPTERS", "false").lower() == "true"
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    exa_api_key: str | None = os.getenv("EXA_API_KEY")
    enable_live_pulse: bool = os.getenv("ENABLE_LIVE_PULSE", "false").lower() == "true"
    enable_streetscapes: bool = os.getenv("ENABLE_STREETSCAPES", "false").lower() == "true"
    mapillary_access_token: str | None = os.getenv("MAPILLARY_ACCESS_TOKEN")
    google_maps_api_key: str | None = os.getenv("GOOGLE_MAPS_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
