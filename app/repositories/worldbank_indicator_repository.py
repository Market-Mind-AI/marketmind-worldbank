import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worldbank_indicator_catalog import WorldBankIndicatorCatalog
from app.utils.time import utc_now


class WorldBankIndicatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        indicator_code: str,
        indicator_name: str,
        description: str | None = None,
        source_note: str | None = None,
        source_organization: str | None = None,
        category: str = "",
        expected_unit: str | None = None,
        marketmind_dimension: str | None = None,
        is_active: bool = True,
    ) -> WorldBankIndicatorCatalog:
        entity = WorldBankIndicatorCatalog(
            id=uuid.uuid4(),
            indicator_code=indicator_code,
            indicator_name=indicator_name,
            description=description,
            source_note=source_note,
            source_organization=source_organization,
            category=category,
            expected_unit=expected_unit,
            marketmind_dimension=marketmind_dimension,
            is_active=is_active,
            created_at=utc_now(),
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def bulk_create(
        self,
        indicators: list[dict],
    ) -> list[WorldBankIndicatorCatalog]:
        entities: list[WorldBankIndicatorCatalog] = []
        now = utc_now()
        for ind in indicators:
            entity = WorldBankIndicatorCatalog(
                id=uuid.uuid4(),
                indicator_code=ind["indicator_code"],
                indicator_name=ind["indicator_name"],
                description=ind.get("description"),
                source_note=ind.get("source_note"),
                source_organization=ind.get("source_organization"),
                category=ind["category"],
                expected_unit=ind.get("expected_unit"),
                marketmind_dimension=ind.get("marketmind_dimension"),
                is_active=ind.get("is_active", True),
                created_at=now,
            )
            entities.append(entity)
        self._session.add_all(entities)
        await self._session.flush()
        return entities

    async def get_all(self) -> list[WorldBankIndicatorCatalog]:
        result = await self._session.execute(
            select(WorldBankIndicatorCatalog).order_by(WorldBankIndicatorCatalog.indicator_code)
        )
        return list(result.scalars().all())

    async def get_active(self) -> list[WorldBankIndicatorCatalog]:
        result = await self._session.execute(
            select(WorldBankIndicatorCatalog)
            .where(WorldBankIndicatorCatalog.is_active.is_(True))
            .order_by(WorldBankIndicatorCatalog.indicator_code)
        )
        return list(result.scalars().all())

    async def get_by_code(self, indicator_code: str) -> WorldBankIndicatorCatalog | None:
        result = await self._session.execute(
            select(WorldBankIndicatorCatalog).where(WorldBankIndicatorCatalog.indicator_code == indicator_code)
        )
        return result.scalar_one_or_none()

    async def get_by_codes(self, codes: list[str]) -> list[WorldBankIndicatorCatalog]:
        result = await self._session.execute(
            select(WorldBankIndicatorCatalog)
            .where(WorldBankIndicatorCatalog.indicator_code.in_(codes))
            .where(WorldBankIndicatorCatalog.is_active.is_(True))
        )
        return list(result.scalars().all())
