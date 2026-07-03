import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worldbank_country import WorldBankCountry
from app.utils.normalization import clean_numeric_value, make_json_safe
from app.utils.time import utc_now


class WorldBankCountryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(
        self,
        worldbank_request_id: uuid.UUID,
        countries: list[dict[str, Any]],
    ) -> list[WorldBankCountry]:
        entities: list[WorldBankCountry] = []
        now = utc_now()
        for c in countries:
            entity = WorldBankCountry(
                id=uuid.uuid4(),
                worldbank_request_id=worldbank_request_id,
                country_id=c["country_id"],
                iso2_code=c.get("iso2_code"),
                name=c["name"],
                region_id=c.get("region_id"),
                region_name=c.get("region_name"),
                income_level_id=c.get("income_level_id"),
                income_level_name=c.get("income_level_name"),
                lending_type_id=c.get("lending_type_id"),
                lending_type_name=c.get("lending_type_name"),
                capital_city=c.get("capital_city"),
                longitude=clean_numeric_value(c.get("longitude")),
                latitude=clean_numeric_value(c.get("latitude")),
                raw_payload=make_json_safe(c),
                created_at=now,
            )
            entities.append(entity)
        self._session.add_all(entities)
        await self._session.flush()
        return entities
