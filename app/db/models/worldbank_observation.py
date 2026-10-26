import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorldBankObservation(Base):
    __tablename__ = "worldbank_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worldbank_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worldbank_requests.id"), nullable=False
    )
    country: Mapped[str] = mapped_column(String, nullable=False)
    country_iso2: Mapped[str | None] = mapped_column(String, nullable=True)
    country_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    indicator_code: Mapped[str] = mapped_column(String, nullable=False)
    indicator_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    decimal_places: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    obs_status: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_worldbank_observations_worldbank_request_id", "worldbank_request_id"),
        Index("ix_worldbank_observations_country", "country"),
        Index("ix_worldbank_observations_country_iso2", "country_iso2"),
        Index("ix_worldbank_observations_indicator_code", "indicator_code"),
        Index("ix_worldbank_observations_year", "year"),
        Index("ix_worldbank_observations_series", "country_iso2", "indicator_code", "year"),
    )
