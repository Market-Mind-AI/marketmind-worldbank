import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

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
    RefreshStaleRequest,
)
from app.schemas.responses import (
    CatalogCreateResponse,
    CatalogResponse,
    CatalogSeedResponse,
    CollectResponse,
    CountriesResponse,
    FreshnessResponse,
    IndicatorMetadataResponse,
    IngestionRunResponse,
    ObservationsResponse,
    RefreshStaleResponse,
    SeriesResponse,
    WorldBankRequestResponse,
)
from app.services.worldbank_service import WorldBankService

router = APIRouter()


def _refuse_if_incomplete(resposta, pedido) -> None:
    """Uma passagem que deixou país para trás responde 503, quando pedido.

    O CronJob chama isto com `curl --fail`, então um 503 sai diferente de zero:
    o Kubernetes retenta dentro do backoffLimit e, se não resolver, o Job fica
    `Failed` em vez de marcar sucesso. Sem isso, `failed` era apenas um campo
    dentro de uma resposta 200 — uma noite em que TODOS os países falharam
    terminava com o CronJob anotando lastSuccessfulTime.

    Só quando pedido: uma chamada manual quer o relatório parcial, não um erro.
    """
    if not getattr(pedido, "fail_if_incomplete", False):
        return
    dados = getattr(resposta, "data", resposta)
    falharam = getattr(dados, "failed", 0) or 0
    if falharam:
        raise HTTPException(
            status_code=503,
            detail=f"{falharam} country(ies) could not be refreshed; the pass is incomplete.",
        )


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


@router.post(
    "/maintenance/refresh-stale",
    response_model=RefreshStaleResponse,
    summary="Collect again whatever has not been looked at in a while",
    description=(
        "The scheduled half of keeping data current. The other half is the "
        "on-demand collection: something decides a country is needed now and "
        "asks for it. Between the two, what this service holds stays fresh "
        "without anyone tracking it from outside.\n\n"
        "Each stale country is replayed from its last SUCCESSFUL collection "
        "request, with the year window moved to now. Replaying rather than "
        "composing a new request means this service needs no knowledge it does "
        "not already have -- whatever a caller once set up keeps working.\n\n"
        "A country never collected is skipped, not invented: it has no request "
        "to replay, and it arrives through the on-demand path the first time.\n\n"
        "Bounded by `limit`, because a first run against a long-idle database "
        "finds everything stale at once and would collect all of it in one "
        "pass. One country failing does not end the pass."
    ),
)
async def refresh_stale(
    request: RefreshStaleRequest | None = None,
    service: WorldBankService = Depends(get_worldbank_service),
) -> RefreshStaleResponse:
    try:
        pedido = request or RefreshStaleRequest()
        resposta = await service.refresh_stale(pedido)
        _refuse_if_incomplete(resposta, pedido)
        return resposta
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.get(
    "/observations/series",
    response_model=SeriesResponse,
    summary="Read one indicator's stored values for one country",
    description=(
        "Returns the values this service has collected, newest year first, with "
        "nulls dropped. Filtered by ISO2 country code, which is the one code a "
        "caller can supply for every country without keeping a mapping table of "
        "its own.\n\n"
        "Rows come back, never a computed figure: an average, a latest value or "
        "a logarithm is method, it is versioned, and it belongs to whoever owns "
        "the method rather than to this service.\n\n"
        "Use `limit` to read only the most recent N years."
    ),
)
async def get_series(
    country_iso2: str = Query(..., min_length=2, max_length=2, description="ISO2 country code, e.g. ES"),
    indicator_code: str = Query(..., description="World Bank indicator code, e.g. NY.GDP.PCAP.CD"),
    limit: int | None = Query(None, ge=1, le=1000, description="Most recent N years only. Omit for the full series."),
    service: WorldBankService = Depends(get_worldbank_service),
) -> SeriesResponse:
    try:
        return await service.get_series(country_iso2=country_iso2, indicator_code=indicator_code, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_exception(e) from e


@router.get(
    "/freshness",
    response_model=FreshnessResponse,
    summary="What this service holds, and when it last looked",
    description=(
        "Reports, per country and indicator, when this service last ASKED the "
        "World Bank -- not how recent the returned data is. The two are "
        "different: GDP and population are published yearly, so a 2024 value is "
        "current rather than stale, and a staleness rule written against the "
        "data's own date would re-fetch every indicator every day forever.\n\n"
        "A pair that was checked and came back empty still reports a "
        "last_checked_at, so a country the source genuinely has no data for is "
        "not mistaken for one that was never tried.\n\n"
        "Naming both country and indicator asks a closed question and gets a "
        "closed answer: every requested pair is returned, including pairs never "
        "fetched (last_checked_at null, stale true). Without both filters, only "
        "pairs this service knows about are listed."
    ),
)
async def get_freshness(
    country: list[str] | None = Query(
        None, description="ISO3 country codes. Repeat the parameter for several."
    ),
    indicator: list[str] | None = Query(
        None, description="World Bank indicator codes, e.g. NY.GDP.MKTP.CD. Repeat for several."
    ),
    stale_after_days: int = Query(30, ge=1, le=3650, description="A check older than this counts as stale."),
    only_stale: bool = Query(False, description="Return only the pairs that need collecting."),
    service: WorldBankService = Depends(get_worldbank_service),
) -> FreshnessResponse:
    try:
        return await service.get_freshness(
            countries=country,
            indicators=indicator,
            stale_after_days=stale_after_days,
            only_stale=only_stale,
        )
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
