import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorldBankRequest(Base):
    __tablename__ = "worldbank_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    indicator_code: Mapped[str | None] = mapped_column(String, nullable=True)
    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    query_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_worldbank_requests_ingestion_run_id", "ingestion_run_id"),
        Index("ix_worldbank_requests_endpoint", "endpoint"),
        Index("ix_worldbank_requests_country", "country"),
        Index("ix_worldbank_requests_indicator_code", "indicator_code"),
        Index("ix_worldbank_requests_start_year", "start_year"),
        Index("ix_worldbank_requests_end_year", "end_year"),
    )
