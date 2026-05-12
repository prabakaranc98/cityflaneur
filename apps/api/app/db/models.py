from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlaceRecord(Base):
    __tablename__ = "places"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    neighborhood: Mapped[str] = mapped_column(String(120), index=True)
    lat: Mapped[float] = mapped_column(Float, index=True)
    lng: Mapped[float] = mapped_column(Float, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    atmosphere_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    opening_hours: Mapped[dict] = mapped_column(JSON, default=dict)
    price_level: Mapped[int] = mapped_column(Integer, default=1)
    rating: Mapped[float] = mapped_column(Float, default=4.0)
    quality_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[str] = mapped_column(String(160), index=True)
    attribution: Mapped[str] = mapped_column(Text)
    indoor: Mapped[bool] = mapped_column(default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    geom: Mapped[object | None] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeedbackRecord(Base):
    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(120), index=True)
    itinerary_id: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
