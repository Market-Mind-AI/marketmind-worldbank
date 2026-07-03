import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_worldbank_service
from app.core.exceptions import (
    WorldBankBaseException,
    WorldBankClientError,
    WorldBankEmptyResponseError,
    WorldBankRateLimitError,
    WorldBankTimeoutError,
)
from app.schemas.requests import (
    CountriesRequest,
    IndicatorCatalogRequest,
    IndicatorCollectRequest,
    IndicatorMetadataRequest,
    ObservationsRequest,
)
from app.schemas.responses import (
    CatalogCreateResponse,
    CatalogResponse,
    CatalogSeedResponse,
    CollectResponse,
    CountriesResponse,
    IndicatorMetadataResponse,
    IngestionRunResponse,
    ObservationsResponse,
    WorldBankRequestResponse,
)
from app.services.worldbank_service import WorldBankService

router = APIRouter()


def _handle_exception(e: Exception) -> HTTPException:
    if isinstance(e, WorldBankEmptyResponseError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, WorldBankRateLimitError):
        return HTTPException(status_code=429, detail=str(e))
    if isinstance(e, WorldBankTimeoutError):
        return HTTPException(status_code=504, detail=str(e))
    if isinstance(e, WorldBankClientError):
        return HTTPException(status_code=502, detail=str(e))
    if isinstance(e, WorldBankBaseException):
        return HTTPException(status_code=e.status_code, detail=e.message)
    return HTTPException(status_code=500, detail=str(e))


@router.post(
    "/countries",
    response_model=CountriesResponse,
    summary="Collect countries",
    description="Fetches the list of available countries from World Bank API, normalizes and persists the data.",
)
async def collect_countries(
    request: CountriesRequest,
    service: WorldBankService = Depends(get_worldbank_service),
) -> CountriesResponse:
    try:
        return await service.collect_countries(request)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.post(
    "/indicators/metadata",
    response_model=IndicatorMetadataResponse,
    summary="Collect indicator metadata",
    description="Fetches metadata for a specific World Bank indicator, normalizes and persists the data.",
)
async def collect_indicator_metadata(
    request: IndicatorMetadataRequest,
    service: WorldBankService = Depends(get_worldbank_service),
) -> IndicatorMetadataResponse:
    try:
        return await service.collect_indicator_metadata(request)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.post(
    "/observations",
    response_model=ObservationsResponse,
    summary="Collect observations",
    description="Fetches observations for a specific indicator/country/period from World Bank API.",
)
async def collect_observations(
    request: ObservationsRequest,
    service: WorldBankService = Depends(get_worldbank_service),
) -> ObservationsResponse:
    try:
        return await service.collect_observations(request)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.post(
    "/indicators/catalog/seed",
    response_model=CatalogSeedResponse,
    summary="Seed indicator catalog",
    description="Seeds the internal indicator catalog with the default MarketMind indicators.",
)
async def seed_catalog(
    service: WorldBankService = Depends(get_worldbank_service),
) -> CatalogSeedResponse:
    try:
        return await service.seed_catalog()
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.post(
    "/indicators/catalog",
    response_model=CatalogCreateResponse,
    summary="Create indicator catalog entries",
    description="Creates or updates indicator catalog entries for MarketMind-relevant World Bank indicators.",
)
async def create_catalog(
    request: IndicatorCatalogRequest,
    service: WorldBankService = Depends(get_worldbank_service),
) -> CatalogCreateResponse:
    try:
        return await service.create_catalog(request)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.get(
    "/indicators/catalog",
    response_model=CatalogResponse,
    summary="List indicator catalog",
    description="Lists all indicators registered in the internal catalog.",
)
async def list_catalog(
    service: WorldBankService = Depends(get_worldbank_service),
) -> CatalogResponse:
    try:
        return await service.get_catalog()
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.post(
    "/indicators/collect",
    response_model=CollectResponse,
    summary="Collect catalog indicators",
    description="Collects observations for indicators from the catalog for a specific country/period.",
)
async def collect_indicators(
    request: IndicatorCollectRequest,
    service: WorldBankService = Depends(get_worldbank_service),
) -> CollectResponse:
    try:
        return await service.collect_indicators(request)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.get(
    "/requests/{worldbank_request_id}",
    response_model=WorldBankRequestResponse,
    summary="Get request details",
    description="Returns details of a specific World Bank API request by its ID.",
)
async def get_request(
    worldbank_request_id: uuid.UUID,
    service: WorldBankService = Depends(get_worldbank_service),
) -> WorldBankRequestResponse:
    try:
        wb_request = await service.get_request(worldbank_request_id)
        if not wb_request:
            raise HTTPException(status_code=404, detail=f"Request {worldbank_request_id} not found")
        return WorldBankRequestResponse(
            id=wb_request.id,
            ingestion_run_id=wb_request.ingestion_run_id,
            endpoint=wb_request.endpoint,
            url=wb_request.url,
            country=wb_request.country,
            indicator_code=wb_request.indicator_code,
            start_year=wb_request.start_year,
            end_year=wb_request.end_year,
            query_params=wb_request.query_params,
            created_at=wb_request.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.get(
    "/runs/{ingestion_run_id}",
    response_model=IngestionRunResponse,
    summary="Get ingestion run details",
    description="Returns status and metadata of a specific ingestion run.",
)
async def get_run(
    ingestion_run_id: uuid.UUID,
    service: WorldBankService = Depends(get_worldbank_service),
) -> IngestionRunResponse:
    try:
        run = await service.get_run(ingestion_run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Ingestion run {ingestion_run_id} not found")
        return IngestionRunResponse(
            id=run.id,
            source=run.source,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            execution_time_ms=run.execution_time_ms,
            request_payload=run.request_payload,
            error_message=run.error_message,
            created_at=run.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e
