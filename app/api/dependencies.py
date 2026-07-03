from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.worldbank_service import WorldBankService


async def get_worldbank_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[WorldBankService, None]:
    yield WorldBankService(session)
