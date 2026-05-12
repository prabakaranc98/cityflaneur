"""initial tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "places",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("neighborhood", sa.String(length=120), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("atmosphere_tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("opening_hours", sa.JSON(), nullable=False),
        sa.Column("price_level", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("quality_signals", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("indoor", sa.Boolean(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_places_category", "places", ["category"])
    op.create_index("ix_places_name", "places", ["name"])
    op.create_index("ix_places_neighborhood", "places", ["neighborhood"])
    op.create_index("ix_places_source_id", "places", ["source_id"])
    op.create_index("ix_places_geom", "places", ["geom"], postgresql_using="gist")

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=120), nullable=False),
        sa.Column("itinerary_id", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_feedback_events_session_id", "feedback_events", ["session_id"])
    op.create_index("ix_feedback_events_itinerary_id", "feedback_events", ["itinerary_id"])
    op.create_index("ix_feedback_events_action", "feedback_events", ["action"])


def downgrade() -> None:
    op.drop_table("feedback_events")
    op.drop_table("places")
