from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
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
        # Duas formas de linha, porque há duas formas de requisição. Uma chamada
        # de metadados nomeia UM indicador e preenche `indicator_code`; a coleta
        # de séries busca VÁRIOS de uma vez e deixa a coluna nula, guardando a
        # lista em `query_params`. Exigir a coluna preenchida descartava a
        # segunda forma — que é a única que as coletas diárias produzem — e todo
        # par voltava como "nunca verificado", recoletado todas as noites.
        stmt = select(
            WorldBankRequest.country,
            WorldBankRequest.indicator_code,
            WorldBankRequest.query_params,
            WorldBankRequest.created_at,
        ).where(WorldBankRequest.country.is_not(None))
        if countries:
            stmt = stmt.where(WorldBankRequest.country.in_(countries))

        procurados = set(indicators or [])
        ultimos: dict[Pair, datetime] = {}
        for country, indicator_code, params, created_at in (await self._session.execute(stmt)).all():
            codigos = [indicator_code] if indicator_code else list((params or {}).get("indicator_codes") or [])
            for code in codigos:
                if procurados and code not in procurados:
                    continue
                chave = (country, code)
                if chave not in ultimos or created_at > ultimos[chave]:
                    ultimos[chave] = created_at
        return ultimos

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
