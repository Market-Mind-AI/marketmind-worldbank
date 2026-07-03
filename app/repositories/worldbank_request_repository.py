import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worldbank_request import WorldBankRequest
from app.utils.time import utc_now


class WorldBankRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        ingestion_run_id: uuid.UUID,
        endpoint: str,
        url: str,
        country: str | None = None,
        indicator_code: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> WorldBankRequest:
        request = WorldBankRequest(
            id=uuid.uuid4(),
            ingestion_run_id=ingestion_run_id,
            endpoint=endpoint,
            url=url,
            country=country,
            indicator_code=indicator_code,
            start_year=start_year,
            end_year=end_year,
            query_params=query_params,
            created_at=utc_now(),
        )
        self._session.add(request)
        await self._session.flush()
        return request

    async def get_by_id(self, request_id: uuid.UUID) -> WorldBankRequest | None:
        result = await self._session.execute(select(WorldBankRequest).where(WorldBankRequest.id == request_id))
        return result.scalar_one_or_none()
