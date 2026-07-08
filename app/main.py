from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.worldbank import router as worldbank_router
from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory, engine
from app.services.worldbank_service import WorldBankService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Starting {settings.app_name} v{settings.app_version} in {settings.app_env} mode")
    # Idempotent (upserts by indicator_code) — safe to run on every startup,
    # not just after a fresh volume. Never blocks startup: a transient
    # failure here just means POST /indicators/catalog/seed still works
    # manually, same as before this existed.
    try:
        async with async_session_factory() as session:
            await WorldBankService(session).seed_catalog()
        logger.info("Indicator catalog seeded on startup")
    except Exception as e:
        logger.error(f"Startup catalog seed failed (non-fatal): {e}")
    yield
    await engine.dispose()
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title="MarketMind World Bank API",
    description=(
        "Microservice for consuming, normalizing and persisting World Bank Open Data "
        "via the World Bank Indicators API. This service collects countries, indicators metadata, "
        "and time-series observations, storing raw and normalized data in PostgreSQL "
        "for scientific traceability and downstream consumption by MarketMind Core."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health_router, tags=["Health"])
app.include_router(worldbank_router, tags=["World Bank"])
