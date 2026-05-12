from __future__ import annotations

import os
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field

load_dotenv(find_dotenv(usecwd=True))


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]


class Settings(BaseModel):
    app_name: str = "Cityflaneur API"
    environment: str = Field(
        default_factory=lambda: os.getenv("CITYFLANEUR_ENV", "development")
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://cityflaneur:cityflaneur@localhost:5432/cityflaneur",
        )
    )
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    cors_origins: list[str] = Field(default_factory=cors_origins)
    default_catalog_version: str = "seed-manhattan-v1"
    enable_llm_adapters: bool = Field(default_factory=lambda: env_bool("ENABLE_LLM_ADAPTERS"))
    openrouter_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))
    openrouter_model: str = Field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    )
    exa_api_key: str | None = Field(default_factory=lambda: os.getenv("EXA_API_KEY"))
    enable_live_pulse: bool = Field(default_factory=lambda: env_bool("ENABLE_LIVE_PULSE"))
    enable_streetscapes: bool = Field(default_factory=lambda: env_bool("ENABLE_STREETSCAPES"))
    mapillary_access_token: str | None = Field(
        default_factory=lambda: os.getenv("MAPILLARY_ACCESS_TOKEN")
    )
    google_maps_api_key: str | None = Field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
