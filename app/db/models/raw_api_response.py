import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RawApiResponse(Base):
    __tablename__ = "raw_api_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worldbank_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worldbank_requests.id"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[assignment]
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_raw_api_responses_worldbank_request_id", "worldbank_request_id"),
        Index("ix_raw_api_responses_endpoint", "endpoint"),
    )
