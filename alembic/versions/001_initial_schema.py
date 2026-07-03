"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(), nullable=False, server_default="worldbank"),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])

    op.create_table(
        "worldbank_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingestion_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingestion_runs.id"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("indicator_code", sa.String(), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("query_params", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worldbank_requests_ingestion_run_id", "worldbank_requests", ["ingestion_run_id"])
    op.create_index("ix_worldbank_requests_endpoint", "worldbank_requests", ["endpoint"])
    op.create_index("ix_worldbank_requests_country", "worldbank_requests", ["country"])
    op.create_index("ix_worldbank_requests_indicator_code", "worldbank_requests", ["indicator_code"])
    op.create_index("ix_worldbank_requests_start_year", "worldbank_requests", ["start_year"])
    op.create_index("ix_worldbank_requests_end_year", "worldbank_requests", ["end_year"])

    op.create_table(
        "raw_api_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "worldbank_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worldbank_requests.id"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_raw_api_responses_worldbank_request_id", "raw_api_responses", ["worldbank_request_id"])
    op.create_index("ix_raw_api_responses_endpoint", "raw_api_responses", ["endpoint"])

    op.create_table(
        "worldbank_countries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "worldbank_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worldbank_requests.id"),
            nullable=True,
        ),
        sa.Column("country_id", sa.String(), nullable=False),
        sa.Column("iso2_code", sa.String(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("region_id", sa.String(), nullable=True),
        sa.Column("region_name", sa.Text(), nullable=True),
        sa.Column("income_level_id", sa.String(), nullable=True),
        sa.Column("income_level_name", sa.Text(), nullable=True),
        sa.Column("lending_type_id", sa.String(), nullable=True),
        sa.Column("lending_type_name", sa.Text(), nullable=True),
        sa.Column("capital_city", sa.Text(), nullable=True),
        sa.Column("longitude", sa.Numeric(), nullable=True),
        sa.Column("latitude", sa.Numeric(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worldbank_countries_country_id", "worldbank_countries", ["country_id"])
    op.create_index("ix_worldbank_countries_iso2_code", "worldbank_countries", ["iso2_code"])
    op.create_index("ix_worldbank_countries_region_id", "worldbank_countries", ["region_id"])
    op.create_index("ix_worldbank_countries_income_level_id", "worldbank_countries", ["income_level_id"])

    op.create_table(
        "worldbank_indicators_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator_code", sa.String(), nullable=False),
        sa.Column("indicator_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("source_organization", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("expected_unit", sa.String(), nullable=True),
        sa.Column("marketmind_dimension", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_worldbank_indicators_catalog_indicator_code", "worldbank_indicators_catalog", ["indicator_code"]
    )
    op.create_index("ix_worldbank_indicators_catalog_category", "worldbank_indicators_catalog", ["category"])
    op.create_index(
        "ix_worldbank_indicators_catalog_marketmind_dimension",
        "worldbank_indicators_catalog",
        ["marketmind_dimension"],
    )
    op.create_index("ix_worldbank_indicators_catalog_is_active", "worldbank_indicators_catalog", ["is_active"])

    op.create_table(
        "worldbank_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "worldbank_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worldbank_requests.id"),
            nullable=False,
        ),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("country_iso2", sa.String(), nullable=True),
        sa.Column("country_name", sa.Text(), nullable=True),
        sa.Column("indicator_code", sa.String(), nullable=False),
        sa.Column("indicator_name", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("decimal_places", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("obs_status", sa.String(), nullable=True),
        sa.Column("normalized_value", sa.Numeric(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_worldbank_observations_worldbank_request_id", "worldbank_observations", ["worldbank_request_id"]
    )
    op.create_index("ix_worldbank_observations_country", "worldbank_observations", ["country"])
    op.create_index("ix_worldbank_observations_country_iso2", "worldbank_observations", ["country_iso2"])
    op.create_index("ix_worldbank_observations_indicator_code", "worldbank_observations", ["indicator_code"])
    op.create_index("ix_worldbank_observations_year", "worldbank_observations", ["year"])


def downgrade() -> None:
    op.drop_table("worldbank_observations")
    op.drop_table("worldbank_indicators_catalog")
    op.drop_table("worldbank_countries")
    op.drop_table("raw_api_responses")
    op.drop_table("worldbank_requests")
    op.drop_table("ingestion_runs")
