import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.raw_api_response import RawApiResponse
from app.utils.time import utc_now


class RawApiResponseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        worldbank_request_id: uuid.UUID,
        endpoint: str,
        request_payload: dict[str, Any],
        response_payload: Any,
    ) -> RawApiResponse:
        raw = RawApiResponse(
            id=uuid.uuid4(),
            worldbank_request_id=worldbank_request_id,
            endpoint=endpoint,
            request_payload=request_payload,
            response_payload=response_payload if isinstance(response_payload, dict) else {"data": response_payload},
            created_at=utc_now(),
        )
        self._session.add(raw)
        await self._session.flush()
        return raw

    async def bulk_create(
        self,
        worldbank_request_id: uuid.UUID,
        endpoint: str,
        request_payload: dict[str, Any],
        raw_responses: list[Any],
    ) -> list[RawApiResponse]:
        entities: list[RawApiResponse] = []
        now = utc_now()
        for i, response in enumerate(raw_responses):
            raw = RawApiResponse(
                id=uuid.uuid4(),
                worldbank_request_id=worldbank_request_id,
                endpoint=endpoint,
                request_payload={**request_payload, "page": i + 1},
                response_payload=response if isinstance(response, dict) else {"data": response},
                created_at=now,
            )
            entities.append(raw)
        self._session.add_all(entities)
        await self._session.flush()
        return entities
