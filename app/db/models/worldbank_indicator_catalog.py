import uuid
from datetime import datetime

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorldBankIndicatorCatalog(Base):
    __tablename__ = "worldbank_indicators_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator_code: Mapped[str] = mapped_column(String, nullable=False)
    indicator_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_organization: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    expected_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    marketmind_dimension: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_worldbank_indicators_catalog_indicator_code", "indicator_code"),
        Index("ix_worldbank_indicators_catalog_category", "category"),
        Index("ix_worldbank_indicators_catalog_marketmind_dimension", "marketmind_dimension"),
        Index("ix_worldbank_indicators_catalog_is_active", "is_active"),
    )
