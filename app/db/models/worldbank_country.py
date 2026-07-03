import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorldBankCountry(Base):
    __tablename__ = "worldbank_countries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worldbank_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worldbank_requests.id"), nullable=True
    )
    country_id: Mapped[str] = mapped_column(String, nullable=False)
    iso2_code: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    region_id: Mapped[str | None] = mapped_column(String, nullable=True)
    region_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    income_level_id: Mapped[str | None] = mapped_column(String, nullable=True)
    income_level_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    lending_type_id: Mapped[str | None] = mapped_column(String, nullable=True)
    lending_type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    capital_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_worldbank_countries_country_id", "country_id"),
        Index("ix_worldbank_countries_iso2_code", "iso2_code"),
        Index("ix_worldbank_countries_region_id", "region_id"),
        Index("ix_worldbank_countries_income_level_id", "income_level_id"),
    )
