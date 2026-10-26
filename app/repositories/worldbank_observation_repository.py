import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worldbank_observation import WorldBankObservation
from app.utils.normalization import clean_numeric_value, make_json_safe
from app.utils.time import utc_now


class WorldBankObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_periods(
        self,
        worldbank_request_id: uuid.UUID,
        observations: list[dict[str, Any]],
    ) -> list[WorldBankObservation]:
        """Grava uma coleta, substituindo o que já havia para os mesmos anos.

        Até 26/10/2026 cada coleta só acrescentava, e um ano coletado duas vezes
        ficava guardado duas vezes: depois da segunda coleta, `limit=3` devolvia
        [2025, 2025, 2024] e a média de três anos do Core saía errada. A coleta
        nova vence -- é o número que a fonte publica hoje, revisões incluídas.
        Mesma regra nos três coletores de indicadores.
        """
        entities: list[WorldBankObservation] = []
        now = utc_now()
        for obs in observations:
            year = obs.get("year")
            if year is None:
                continue

            entity = WorldBankObservation(
                id=uuid.uuid4(),
                worldbank_request_id=worldbank_request_id,
                country=obs["country"],
                country_iso2=obs.get("country_iso2"),
                country_name=obs.get("country_name"),
                indicator_code=obs["indicator_code"],
                indicator_name=obs.get("indicator_name"),
                year=year,
                value=clean_numeric_value(obs.get("value")),
                decimal_places=obs.get("decimal_places"),
                unit=obs.get("unit"),
                obs_status=obs.get("obs_status"),
                normalized_value=None,
                raw_payload=make_json_safe(obs),
                created_at=now,
            )
            entities.append(entity)

        anos: dict[tuple[str | None, str], set[int]] = {}
        for entity in entities:
            anos.setdefault((entity.country_iso2, entity.indicator_code), set()).add(entity.year)
        for (country_iso2, indicator_code), years in anos.items():
            await self._session.execute(
                delete(WorldBankObservation)
                .where(WorldBankObservation.country_iso2 == country_iso2)
                .where(WorldBankObservation.indicator_code == indicator_code)
                .where(WorldBankObservation.year.in_(sorted(years)))
            )

        self._session.add_all(entities)
        await self._session.flush()
        return entities

    async def series(
        self, *, country_iso2: str, indicator_code: str, limit: int | None = None
    ) -> list[WorldBankObservation]:
        """The indicator's values for a country, one per year, newest year first, nulls dropped.

        Filtered by country_iso2 rather than the World Bank's own `country`
        column: ISO2 is the one code every caller can supply for every country
        without a lookup table of its own.

        Um valor por ano, e a regra de desempate é a mesma dos três coletores:
        vale a linha da coleta mais recente; dentro de uma mesma coleta, o maior
        valor. `replace_periods` já impede a cópia na escrita, mas o que foi
        gravado antes dela, ou por duas coletas simultâneas, não pode voltar
        duas vezes -- é o LIMIT que conta anos, não linhas.

        Rows are returned, not a computed figure. Whoever asks owns the
        arithmetic -- averaging the last three years, taking the latest, taking
        a logarithm -- and that arithmetic is versioned method, not something
        this service should be quietly deciding.
        """
        stmt = (
            select(WorldBankObservation)
            .where(WorldBankObservation.country_iso2 == country_iso2)
            .where(WorldBankObservation.indicator_code == indicator_code)
            .where(WorldBankObservation.value.is_not(None))
            .distinct(WorldBankObservation.year)
            .order_by(
                WorldBankObservation.year.desc(),
                WorldBankObservation.created_at.desc(),
                WorldBankObservation.value.desc(),
            )
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
