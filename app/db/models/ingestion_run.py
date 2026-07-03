import uuid
from datetime import datetime

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String, nullable=False, default="worldbank")
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[assignment]
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_ingestion_runs_source", "source"),
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_started_at", "started_at"),
    )
