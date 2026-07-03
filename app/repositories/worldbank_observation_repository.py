import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worldbank_observation import WorldBankObservation
from app.utils.normalization import clean_numeric_value, make_json_safe
from app.utils.time import utc_now


class WorldBankObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(
        self,
        worldbank_request_id: uuid.UUID,
        observations: list[dict[str, Any]],
    ) -> list[WorldBankObservation]:
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
        self._session.add_all(entities)
        await self._session.flush()
        return entities
