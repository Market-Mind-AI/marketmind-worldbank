from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worldbank_observation import WorldBankObservation
from app.db.models.worldbank_request import WorldBankRequest

Pair = tuple[str, str]


@dataclass(frozen=True)
class ObservationFacts:
    last_observation_at: datetime
    latest_year: int | None
    observation_count: int


class FreshnessRepository:
    """Answers "when did we last look at this?", per country and indicator.

    Two separate questions, deliberately not one join. A CHECK is a request we
    made (worldbank_requests), and it happened whether or not the World Bank had
    anything to give back. An OBSERVATION is data that landed. Reading freshness
    off observations alone would report a country the source genuinely has no
    data for as "never checked" forever, and it would be re-fetched every single
    day for as long as the service runs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def last_checks(
        self, *, countries: list[str] | None = None, indicators: list[str] | None = None
    ) -> dict[Pair, datetime]:
        stmt = (
            select(
                WorldBankRequest.country,
                WorldBankRequest.indicator_code,
                func.max(WorldBankRequest.created_at),
            )
            .where(WorldBankRequest.country.is_not(None))
            .where(WorldBankRequest.indicator_code.is_not(None))
            .group_by(WorldBankRequest.country, WorldBankRequest.indicator_code)
        )
        if countries:
            stmt = stmt.where(WorldBankRequest.country.in_(countries))
        if indicators:
            stmt = stmt.where(WorldBankRequest.indicator_code.in_(indicators))

        result = await self._session.execute(stmt)
        return {(row[0], row[1]): row[2] for row in result.all()}

    async def observation_facts(
        self, *, countries: list[str] | None = None, indicators: list[str] | None = None
    ) -> dict[Pair, ObservationFacts]:
        stmt = select(
            WorldBankObservation.country,
            WorldBankObservation.indicator_code,
            func.max(WorldBankObservation.created_at),
            func.max(WorldBankObservation.year),
            func.count(),
        ).group_by(WorldBankObservation.country, WorldBankObservation.indicator_code)
        if countries:
            stmt = stmt.where(WorldBankObservation.country.in_(countries))
        if indicators:
            stmt = stmt.where(WorldBankObservation.indicator_code.in_(indicators))

        result = await self._session.execute(stmt)
        return {
            (row[0], row[1]): ObservationFacts(
                last_observation_at=row[2], latest_year=row[3], observation_count=row[4]
            )
            for row in result.all()
        }
