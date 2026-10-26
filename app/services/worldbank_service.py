import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.worldbank_client import WorldBankClient
from app.core.config import settings
from app.core.exceptions import (
    IndicatorNotConfiguredError,
    WorldBankBaseException,
    WorldBankClientError,
    WorldBankEmptyResponseError,
    WorldBankTransientError,
)
from app.core.logging import logger
from app.domain.enums import WorldBankEndpoint
from app.repositories.freshness_repository import FreshnessRepository
from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.raw_api_response_repository import RawApiResponseRepository
from app.repositories.worldbank_country_repository import WorldBankCountryRepository
from app.repositories.worldbank_indicator_repository import WorldBankIndicatorRepository
from app.repositories.worldbank_observation_repository import WorldBankObservationRepository
from app.repositories.worldbank_request_repository import WorldBankRequestRepository
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
    CatalogData,
    CatalogIndicatorItem,
    CatalogResponse,
    CatalogSeedResponse,
    CollectData,
    CollectResponse,
    CountriesData,
    CountriesResponse,
    CountryItem,
    FreshnessData,
    FreshnessItem,
    FreshnessResponse,
    IndicatorMetadataData,
    IndicatorMetadataItem,
    IndicatorMetadataResponse,
    Metadata,
    ObservationItem,
    ObservationsData,
    ObservationsResponse,
    RefreshedCountry,
    RefreshStaleData,
    RefreshStaleResponse,
    RequestInfo,
    SeriesData,
    SeriesPoint,
    SeriesResponse,
)
from app.utils.normalization import normalize_countries, normalize_country_observations, normalize_indicator_metadata
from app.utils.time import elapsed_ms, utc_now

SEED_INDICATORS = [
    {
        "indicator_code": "NY.GDP.PCAP.CD",
        "indicator_name": "GDP per capita (current US$)",
        "description": "GDP per capita is gross domestic product divided by midyear population.",
        "category": "gdp_per_capita",
        "expected_unit": "current_usd",
        "marketmind_dimension": "macroeconomic_stability",
    },
    {
        "indicator_code": "NY.GDP.MKTP.KD.ZG",
        "indicator_name": "GDP growth (annual %)",
        "description": "Annual percentage growth rate of GDP at market prices based on constant local currency.",
        "category": "gdp_growth",
        "expected_unit": "percentage",
        "marketmind_dimension": "macroeconomic_stability",
    },
    {
        "indicator_code": "IT.NET.USER.ZS",
        "indicator_name": "Individuals using the Internet (% of population)",
        "description": "Internet users are individuals who have used the Internet in the last 3 months.",
        "category": "internet_users",
        "expected_unit": "percentage",
        "marketmind_dimension": "digital_readiness",
    },
    {
        "indicator_code": "SP.POP.TOTL",
        "indicator_name": "Population, total",
        "description": "Total population based on the de facto definition of population.",
        "category": "population_total",
        "expected_unit": "persons",
        "marketmind_dimension": "market_population_potential",
    },
    {
        "indicator_code": "SP.URB.TOTL.IN.ZS",
        "indicator_name": "Urban population (% of total population)",
        "description": "Urban population refers to people living in urban areas.",
        "category": "urban_population",
        "expected_unit": "percentage",
        "marketmind_dimension": "urban_consumption_potential",
    },
    {
        "indicator_code": "IT.CEL.SETS.P2",
        "indicator_name": "Mobile cellular subscriptions (per 100 people)",
        "description": "Mobile cellular telephone subscriptions per 100 people.",
        "category": "mobile_subscriptions",
        "expected_unit": "per_100_people",
        "marketmind_dimension": "digital_readiness",
    },
    {
        "indicator_code": "FP.CPI.TOTL.ZG",
        "indicator_name": "Inflation, consumer prices (annual %)",
        "description": "Inflation as measured by the consumer price index.",
        "category": "inflation",
        "expected_unit": "percentage",
        "marketmind_dimension": "macroeconomic_stability",
    },
    {
        "indicator_code": "IT.NET.BBND.P2",
        "indicator_name": "Fixed broadband subscriptions (per 100 people)",
        "description": "Fixed broadband subscriptions per 100 people.",
        "category": "broadband_subscriptions",
        "expected_unit": "per_100_people",
        "marketmind_dimension": "digital_readiness",
    },
    # Macro Demand Structure (added 2026-07-08, marketmind-scoring GDP=C+I+G+NX
    # identity — see that repo's memory marketmind_mos_engine). All 4
    # confirmed live against the real World Bank API before being added.
    {
        "indicator_code": "NE.CON.PRVT.ZS",
        "indicator_name": "Households and NPISHs final consumption expenditure (% of GDP)",
        "description": "Private consumption share of GDP — a market's household spending intensity.",
        "category": "consumer_spending",
        "expected_unit": "percentage",
        "marketmind_dimension": "macro_demand_structure",
    },
    {
        "indicator_code": "NE.CON.GOVT.ZS",
        "indicator_name": "General government final consumption expenditure (% of GDP)",
        "description": "Government spending share of GDP — context only in marketmind-scoring (no defensible "
        "mayor/menor direction for market opportunity, confirmed against live data).",
        "category": "government_expenditure",
        "expected_unit": "percentage",
        "marketmind_dimension": "macro_demand_structure",
    },
    {
        "indicator_code": "NE.GDI.FTOT.ZS",
        "indicator_name": "Gross fixed capital formation (% of GDP)",
        "description": "Investment share of GDP — proxy for infrastructure/productive investment.",
        "category": "investment",
        "expected_unit": "percentage",
        "marketmind_dimension": "macro_demand_structure",
    },
    {
        "indicator_code": "NE.RSB.GNFS.ZS",
        "indicator_name": "External balance on goods and services (% of GDP)",
        "description": "Net exports share of GDP (can be negative — a trade deficit).",
        "category": "net_exports",
        "expected_unit": "percentage",
        "marketmind_dimension": "macro_demand_structure",
    },
    {
        "indicator_code": "NE.TRD.GNFS.ZS",
        "indicator_name": "Trade (% of GDP)",
        "description": "Exports plus imports of goods and services as a share of GDP — trade openness/"
        "global integration, complementary to net exports (not a zero-sum share with C/I/G).",
        "category": "trade_openness",
        "expected_unit": "percentage",
        "marketmind_dimension": "macro_demand_structure",
    },
]


class WorldBankService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._client = WorldBankClient()
        self._ingestion_repo = IngestionRunRepository(session)
        self._request_repo = WorldBankRequestRepository(session)
        self._raw_response_repo = RawApiResponseRepository(session)
        self._country_repo = WorldBankCountryRepository(session)
        self._indicator_repo = WorldBankIndicatorRepository(session)
        self._observation_repo = WorldBankObservationRepository(session)
        self._freshness_repo = FreshnessRepository(session)

    def _request_info(
        self,
        endpoint: str,
        country: str | None = None,
        indicator_code: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        per_page: int | None = None,
    ) -> RequestInfo:
        return RequestInfo(
            endpoint=endpoint,
            country=country,
            indicator_code=indicator_code,
            start_year=start_year,
            end_year=end_year,
            per_page=per_page,
        )

    def _metadata(
        self,
        endpoint: str,
        execution_time_ms: int,
        records: int,
        ingestion_run_id: uuid.UUID,
        worldbank_request_id: uuid.UUID,
        status: str = "success",
    ) -> Metadata:
        return Metadata(
            provider="World Bank",
            endpoint=endpoint,
            execution_time_ms=execution_time_ms,
            records=records,
            stored=True,
            ingestion_run_id=ingestion_run_id,
            worldbank_request_id=worldbank_request_id,
            status=status,
            collected_at=utc_now(),
        )

    def _log_success(
        self,
        endpoint: str,
        run_id: uuid.UUID,
        request_id: uuid.UUID,
        execution_time_ms: int,
        records: int,
        country: str | None = None,
        indicator_code: str | None = None,
    ) -> None:
        logger.info(
            f"endpoint={endpoint} | country={country} | indicator_code={indicator_code} "
            f"| ingestion_run_id={run_id} | worldbank_request_id={request_id} "
            f"| execution_time_ms={execution_time_ms} | records={records} | status=success"
        )

    async def _fail(
        self,
        run: Any,
        endpoint: str,
        start: Any,
        error: Exception,
        country: str | None = None,
        indicator_code: str | None = None,
    ) -> None:
        exec_time = elapsed_ms(start)
        await self._ingestion_repo.mark_failed(run, exec_time, str(error))
        await self._session.commit()
        logger.error(
            f"endpoint={endpoint} | country={country} | indicator_code={indicator_code} "
            f"| ingestion_run_id={run.id} | execution_time_ms={exec_time} | status=failed | error={error}"
        )

    async def collect_countries(self, request: CountriesRequest) -> CountriesResponse:
        endpoint = WorldBankEndpoint.COUNTRIES
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload=request.model_dump())

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url=f"{settings.worldbank_base_url}/country",
            query_params={"per_page": request.per_page},
        )

        try:
            data, raw_responses, final_url = await self._client.get_countries(per_page=request.per_page)

            await self._raw_response_repo.bulk_create(
                worldbank_request_id=wb_request.id,
                endpoint=endpoint,
                request_payload={"per_page": request.per_page},
                raw_responses=raw_responses,
            )

            normalized = normalize_countries(data)

            await self._country_repo.bulk_create(
                worldbank_request_id=wb_request.id,
                countries=normalized,
            )

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(endpoint, run.id, wb_request.id, exec_time, len(normalized))

            return CountriesResponse(
                request=self._request_info(endpoint=endpoint, per_page=request.per_page),
                metadata=self._metadata(endpoint, exec_time, len(normalized), run.id, wb_request.id),
                data=CountriesData(
                    countries=[
                        CountryItem(
                            country_id=c["country_id"],
                            iso2_code=c.get("iso2_code"),
                            name=c["name"],
                            region_name=c.get("region_name"),
                            income_level_name=c.get("income_level_name"),
                            capital_city=c.get("capital_city"),
                        )
                        for c in normalized
                    ]
                ),
            )

        except Exception as e:
            await self._fail(run, endpoint, start, e)
            raise

    async def collect_indicator_metadata(self, request: IndicatorMetadataRequest) -> IndicatorMetadataResponse:
        endpoint = WorldBankEndpoint.INDICATOR_METADATA
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload=request.model_dump())

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url=f"{settings.worldbank_base_url}/indicator/{request.indicator_code}",
            indicator_code=request.indicator_code,
        )

        try:
            data, raw_responses, final_url = await self._client.get_indicator_metadata(request.indicator_code)

            await self._raw_response_repo.bulk_create(
                worldbank_request_id=wb_request.id,
                endpoint=endpoint,
                request_payload={"indicator_code": request.indicator_code},
                raw_responses=raw_responses,
            )

            normalized = normalize_indicator_metadata(data)

            if not normalized:
                raise WorldBankEmptyResponseError(f"No metadata found for indicator: {request.indicator_code}")

            indicator = normalized[0]

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(endpoint, run.id, wb_request.id, exec_time, 1, indicator_code=request.indicator_code)

            return IndicatorMetadataResponse(
                request=self._request_info(endpoint=endpoint, indicator_code=request.indicator_code),
                metadata=self._metadata(endpoint, exec_time, 1, run.id, wb_request.id),
                data=IndicatorMetadataData(
                    indicator=IndicatorMetadataItem(
                        indicator_code=indicator["indicator_code"],
                        indicator_name=indicator["indicator_name"],
                        source_note=indicator.get("source_note"),
                        source_organization=indicator.get("source_organization"),
                    )
                ),
            )

        except Exception as e:
            await self._fail(run, endpoint, start, e, indicator_code=request.indicator_code)
            raise

    async def collect_observations(self, request: ObservationsRequest) -> ObservationsResponse:
        endpoint = WorldBankEndpoint.OBSERVATIONS
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload=request.model_dump())

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url=f"{settings.worldbank_base_url}/country/{request.country}/indicator/{request.indicator_code}",
            country=request.country,
            indicator_code=request.indicator_code,
            start_year=request.start_year,
            end_year=request.end_year,
            query_params={"per_page": request.per_page, "date": f"{request.start_year}:{request.end_year}"},
        )

        try:
            data, raw_responses, final_url = await self._client.get_observations(
                country=request.country,
                indicator_code=request.indicator_code,
                start_year=request.start_year,
                end_year=request.end_year,
                per_page=request.per_page,
            )

            await self._raw_response_repo.bulk_create(
                worldbank_request_id=wb_request.id,
                endpoint=endpoint,
                request_payload=request.model_dump(),
                raw_responses=raw_responses,
            )

            normalized = normalize_country_observations(data)

            entities = await self._observation_repo.replace_periods(
                worldbank_request_id=wb_request.id,
                observations=normalized,
            )

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(
                endpoint,
                run.id,
                wb_request.id,
                exec_time,
                len(entities),
                country=request.country,
                indicator_code=request.indicator_code,
            )

            return ObservationsResponse(
                request=self._request_info(
                    endpoint=endpoint,
                    country=request.country,
                    indicator_code=request.indicator_code,
                    start_year=request.start_year,
                    end_year=request.end_year,
                    per_page=request.per_page,
                ),
                metadata=self._metadata(endpoint, exec_time, len(entities), run.id, wb_request.id),
                data=ObservationsData(
                    observations=[
                        ObservationItem(
                            country=obs["country"],
                            country_iso2=obs.get("country_iso2"),
                            country_name=obs.get("country_name"),
                            indicator_code=obs["indicator_code"],
                            indicator_name=obs.get("indicator_name"),
                            year=obs["year"],
                            value=obs.get("value"),
                        )
                        for obs in normalized
                        if obs.get("year") is not None
                    ]
                ),
            )

        except Exception as e:
            await self._fail(run, endpoint, start, e, country=request.country, indicator_code=request.indicator_code)
            raise

    async def seed_catalog(self) -> CatalogSeedResponse:
        endpoint = WorldBankEndpoint.INDICATORS_CATALOG_SEED
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload={"action": "seed_catalog"})

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url="internal://indicators/catalog/seed",
        )

        try:
            created: list = []
            for seed in SEED_INDICATORS:
                existing = await self._indicator_repo.get_by_code(seed["indicator_code"])
                if existing is None:
                    entity = await self._indicator_repo.create(**seed)
                    created.append(entity)
                else:
                    created.append(existing)

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(endpoint, run.id, wb_request.id, exec_time, len(created))

            return CatalogSeedResponse(
                request=self._request_info(endpoint=endpoint),
                metadata=self._metadata(endpoint, exec_time, len(created), run.id, wb_request.id),
                data=CatalogData(
                    indicators=[
                        CatalogIndicatorItem(
                            id=e.id,
                            indicator_code=e.indicator_code,
                            indicator_name=e.indicator_name,
                            description=e.description,
                            source_note=e.source_note,
                            source_organization=e.source_organization,
                            category=e.category,
                            expected_unit=e.expected_unit,
                            marketmind_dimension=e.marketmind_dimension,
                            is_active=e.is_active,
                            created_at=e.created_at,
                        )
                        for e in created
                    ]
                ),
            )

        except Exception as e:
            await self._fail(run, endpoint, start, e)
            raise

    async def create_catalog(self, request: IndicatorCatalogRequest) -> CatalogCreateResponse:
        endpoint = WorldBankEndpoint.INDICATORS_CATALOG
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload=request.model_dump())

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url="internal://indicators/catalog",
        )

        try:
            indicators_data = [item.model_dump() for item in request.indicators]
            entities = await self._indicator_repo.bulk_create(indicators_data)

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(endpoint, run.id, wb_request.id, exec_time, len(entities))

            return CatalogCreateResponse(
                request=self._request_info(endpoint=endpoint),
                metadata=self._metadata(endpoint, exec_time, len(entities), run.id, wb_request.id),
                data=CatalogData(
                    indicators=[
                        CatalogIndicatorItem(
                            id=e.id,
                            indicator_code=e.indicator_code,
                            indicator_name=e.indicator_name,
                            description=e.description,
                            source_note=e.source_note,
                            source_organization=e.source_organization,
                            category=e.category,
                            expected_unit=e.expected_unit,
                            marketmind_dimension=e.marketmind_dimension,
                            is_active=e.is_active,
                            created_at=e.created_at,
                        )
                        for e in entities
                    ]
                ),
            )

        except Exception as e:
            await self._fail(run, endpoint, start, e)
            raise

    async def get_freshness(
        self,
        *,
        countries: list[str] | None = None,
        indicators: list[str] | None = None,
        stale_after_days: int = 90,
        only_stale: bool = False,
    ) -> FreshnessResponse:
        """What this service holds and when it last looked, per country and indicator.

        This is what lets a caller decide whether to ask for a collection,
        without the caller having to keep its own record of what was fetched
        when -- which is the bookkeeping that used to live outside this service
        and drift away from what the tables actually held.

        Naming BOTH a country and an indicator asks a closed question, so it
        gets a closed answer: every requested pair comes back, including pairs
        never fetched, marked stale with last_checked_at null. An empty list
        would be indistinguishable from "everything is fresh".
        """
        countries = [c.strip().upper() for c in countries if c.strip()] if countries else None
        indicators = [i.strip() for i in indicators if i.strip()] if indicators else None

        checks = await self._freshness_repo.last_checks(countries=countries, indicators=indicators)
        observed = await self._freshness_repo.observation_facts(countries=countries, indicators=indicators)

        if countries and indicators:
            pairs = [(country, indicator) for country in countries for indicator in indicators]
        else:
            pairs = sorted(set(checks) | set(observed))

        now = utc_now()
        cutoff = now - timedelta(days=stale_after_days)

        items: list[FreshnessItem] = []
        for country, indicator in pairs:
            last_checked_at = checks.get((country, indicator))
            facts = observed.get((country, indicator))
            stale = last_checked_at is None or last_checked_at < cutoff
            if only_stale and not stale:
                continue
            items.append(
                FreshnessItem(
                    country=country,
                    indicator_code=indicator,
                    last_checked_at=last_checked_at,
                    last_observation_at=facts.last_observation_at if facts else None,
                    latest_year=facts.latest_year if facts else None,
                    observation_count=facts.observation_count if facts else 0,
                    stale=stale,
                )
            )

        return FreshnessResponse(data=FreshnessData(as_of=now, stale_after_days=stale_after_days, items=items))

    async def get_catalog(self) -> CatalogResponse:
        indicators = await self._indicator_repo.get_all()
        return CatalogResponse(
            data=CatalogData(
                indicators=[
                    CatalogIndicatorItem(
                        id=e.id,
                        indicator_code=e.indicator_code,
                        indicator_name=e.indicator_name,
                        description=e.description,
                        source_note=e.source_note,
                        source_organization=e.source_organization,
                        category=e.category,
                        expected_unit=e.expected_unit,
                        marketmind_dimension=e.marketmind_dimension,
                        is_active=e.is_active,
                        created_at=e.created_at,
                    )
                    for e in indicators
                ]
            )
        )

    async def _configured_indicators(self, codes: list[str] | None) -> list[Any]:
        """Os indicadores do catálogo que este pedido nomeia -- ou recusa o pedido.

        Um código que o catálogo não conhece é erro de quem pediu, e recusar
        o pedido inteiro com 422 é a mesma regra nos três coletores de
        indicadores. Até 26/10/2026 o World Bank descartava o código em silêncio
        e coletava o resto, e um catálogo vazio era um 404 -- o mesmo caso
        respondido com 400 pela OCDE e com 422 pelo UN Data.
        """
        if codes:
            indicators = await self._indicator_repo.get_by_codes(codes)
            known = {indicator.indicator_code for indicator in indicators}
            missing = [code for code in codes if code not in known]
            if missing:
                raise IndicatorNotConfiguredError(
                    f"Indicators not configured in catalog: {', '.join(missing)}. "
                    "Register them with POST /indicators/catalog first."
                )
            return indicators
        indicators = await self._indicator_repo.get_active()
        if not indicators:
            raise IndicatorNotConfiguredError(
                "No active indicators found in catalog. Seed the catalog first with POST /indicators/catalog/seed"
            )
        return indicators

    @staticmethod
    def _collect_failure(failures: dict[str, Exception]) -> WorldBankBaseException:
        """O erro de uma coleta em que NENHUM indicador teve resposta da fonte.

        Uma coleta que não trouxe nada levanta erro -- nunca um 200 com a
        execução marcada como falha por dentro. Era assim até 26/10/2026, e a
        manutenção diária contava uma queda da fonte como país renovado, com o
        CronJob verde. A regra é a mesma nos três coletores de indicadores:

        - toda falha foi passageira (5xx, 429, timeout, rede): a fonte está
          fora, e o erro é 503 -- "tente de novo", que é o que vale fazer;
        - alguma falha foi uma resposta definitiva que não serve: 502.

        4xx fica só para erro de quem pediu, que é recusado antes de coletar
        (`_configured_indicators`).
        """
        detail = "; ".join(f"{code}: {error}" for code, error in failures.items())
        if all(isinstance(error, WorldBankTransientError) for error in failures.values()):
            return WorldBankTransientError(f"World Bank unavailable: {detail}")
        return WorldBankClientError(f"No indicator could be collected: {detail}")

    async def collect_indicators(self, request: IndicatorCollectRequest) -> CollectResponse:
        endpoint = WorldBankEndpoint.INDICATORS_COLLECT
        indicators = await self._configured_indicators(request.indicator_codes)
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload=request.model_dump())

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url=f"{settings.worldbank_base_url}/country/{request.country}/indicator/...",
            country=request.country,
            start_year=request.start_year,
            end_year=request.end_year,
            query_params={"indicator_codes": list(request.indicator_codes or [])},
        )

        try:
            all_observations: list[dict[str, Any]] = []
            answered: list[str] = []
            failures: dict[str, Exception] = {}

            for indicator in indicators:
                code = indicator.indicator_code
                url = f"{settings.worldbank_base_url}/country/{request.country}/indicator/{code}"
                try:
                    data, raw_responses, url = await self._client.get_observations(
                        country=request.country,
                        indicator_code=code,
                        start_year=request.start_year,
                        end_year=request.end_year,
                    )
                except WorldBankEmptyResponseError:
                    # A fonte respondeu que não tem: é resposta, conta como
                    # verificação, e não é falha.
                    data, raw_responses = [], []
                except Exception as indicator_error:
                    failures[code] = indicator_error
                    logger.warning(
                        f"Failed to collect indicator={code} | country={request.country} | error={indicator_error}"
                    )
                    continue

                # A verificação: uma linha por indicador que a fonte respondeu.
                # Um código que falhou não ganha linha, e por isso não conta
                # como verificado (ver FreshnessRepository.last_checks).
                check = await self._request_repo.create(
                    ingestion_run_id=run.id,
                    endpoint=endpoint,
                    url=url,
                    country=request.country,
                    indicator_code=code,
                    start_year=request.start_year,
                    end_year=request.end_year,
                )
                await self._raw_response_repo.bulk_create(
                    worldbank_request_id=check.id,
                    endpoint=endpoint,
                    request_payload={
                        "country": request.country,
                        "indicator_code": code,
                        "start_year": request.start_year,
                        "end_year": request.end_year,
                    },
                    raw_responses=raw_responses,
                )
                normalized = normalize_country_observations(data)
                await self._observation_repo.replace_periods(worldbank_request_id=check.id, observations=normalized)
                all_observations.extend(normalized)
                answered.append(code)

                logger.info(f"Collected indicator={code} | country={request.country} | records={len(normalized)}")

            if not answered:
                raise self._collect_failure(failures)

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            stored = [obs for obs in all_observations if obs.get("year") is not None]
            self._log_success(endpoint, run.id, wb_request.id, exec_time, len(stored), country=request.country)

            return CollectResponse(
                request=self._request_info(
                    endpoint=endpoint,
                    country=request.country,
                    start_year=request.start_year,
                    end_year=request.end_year,
                ),
                metadata=self._metadata(endpoint, exec_time, len(stored), run.id, wb_request.id),
                data=CollectData(
                    indicators_collected=len(answered),
                    indicators_failed=list(failures),
                    total_observations=len(stored),
                    observations=[
                        ObservationItem(
                            country=obs["country"],
                            country_iso2=obs.get("country_iso2"),
                            country_name=obs.get("country_name"),
                            indicator_code=obs["indicator_code"],
                            indicator_name=obs.get("indicator_name"),
                            year=obs["year"],
                            value=obs.get("value"),
                        )
                        for obs in stored
                    ],
                ),
            )

        except Exception as e:
            await self._fail(run, endpoint, start, e, country=request.country)
            raise

    async def get_run(self, run_id: uuid.UUID) -> Any:
        return await self._ingestion_repo.get_by_id(run_id)

    async def get_request(self, request_id: uuid.UUID) -> Any:
        return await self._request_repo.get_by_id(request_id)

    async def get_series(self, *, country_iso2: str, indicator_code: str, limit: int | None = None) -> SeriesResponse:
        """One indicator's stored values for one country, newest year first.

        This is how a caller reads what was collected without opening this
        service's database. Reading another service's tables directly couples
        the reader to a schema it does not own: a column rename here breaks a
        calculation there, silently and at the worst moment.

        Values come back as rows, never as an average or a latest-value. The
        arithmetic on top (mean of the last three years, natural log of the
        latest, truncation to a range) is method, it is versioned, and it
        belongs to whoever owns the method -- not here.
        """
        rows = await self._observation_repo.series(
            country_iso2=country_iso2.strip().upper(),
            indicator_code=indicator_code.strip(),
            limit=limit,
        )
        return SeriesResponse(
            data=SeriesData(
                country_iso2=country_iso2.strip().upper(),
                indicator_code=indicator_code.strip(),
                points=[SeriesPoint(year=r.year, value=r.value, unit=r.unit, obs_status=r.obs_status) for r in rows],
            )
        )

    async def refresh_stale(self, request: RefreshStaleRequest) -> RefreshStaleResponse:
        """Collect again whatever has not been looked at in a while.

        This is the half of freshness that nobody has to ask for. The other half
        is the on-demand collection: something decides a country is needed now
        and asks. Between the two, data this service already holds stays current
        without anyone tracking it from outside, which is the whole point --
        a second record of what was collected, kept elsewhere, drifts from the
        tables, and the tables are the ones that can be wrong in silence.

        Bounded on purpose. A first run against a long-idle database would
        otherwise find every country stale at once and try to collect all of
        them in one pass, against an upstream API with its own patience.

        Each country is REPLAYED from what its successful collections asked
        for -- every indicator, gathered across runs -- with the window moved to
        now. Composing a fresh request instead would mean knowing things this
        service has no business keeping -- which upstream identifier a country
        has, which indicators it was set up with.

        Um país só conta como renovado quando TODOS os seus indicadores tiveram
        resposta. Se algum falhou, o país conta como falha, com os códigos no
        detalhe -- é o que faz `fail_if_incomplete` acusar uma queda parcial da
        fonte em vez de deixá-la passar como noite boa. Mesma regra nos três.
        """
        freshness = await self.get_freshness(stale_after_days=request.stale_after_days, only_stale=True)

        stale_countries: list[str] = []
        for item in freshness.data.items:
            if item.country not in stale_countries:
                stale_countries.append(item.country)

        setups = await self._ingestion_repo.last_collect_setup_by_country()
        end_year = utc_now().year
        # A mesma janela que o Core pede: de `years_back` anos atrás até este
        # ano, inclusive (macro_coverage, `_ANNUAL_LOOKBACK_YEARS`).
        start_year = end_year - request.years_back

        outcomes: list[RefreshedCountry] = []
        refreshed = failed = skipped = 0

        for country in stale_countries[: request.limit]:
            setup = setups.get(country)
            if setup is None:
                skipped += 1
                outcomes.append(
                    RefreshedCountry(
                        country=country,
                        outcome="skipped",
                        detail="no successful collection to replay; collect it once on demand first",
                    )
                )
                continue

            try:
                response = await self.collect_indicators(
                    IndicatorCollectRequest(
                        country=setup.get("country", country),
                        start_year=start_year,
                        end_year=end_year,
                        indicator_codes=setup["indicator_codes"] or None,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - one country failing must not end the pass
                failed += 1
                logger.warning(f"Scheduled refresh failed for country={country}: {exc}")
                outcomes.append(RefreshedCountry(country=country, outcome="failed", detail=str(exc)))
                continue

            not_collected = response.data.indicators_failed
            if not_collected:
                failed += 1
                logger.warning(f"Scheduled refresh incomplete for country={country}: {not_collected}")
                outcomes.append(
                    RefreshedCountry(
                        country=country,
                        outcome="failed",
                        detail=f"indicators not collected: {', '.join(not_collected)}",
                    )
                )
            else:
                refreshed += 1
                outcomes.append(RefreshedCountry(country=country, outcome="refreshed"))

        return RefreshStaleResponse(
            data=RefreshStaleData(
                stale_after_days=request.stale_after_days,
                stale_countries=len(stale_countries),
                attempted=len(outcomes),
                refreshed=refreshed,
                failed=failed,
                skipped=skipped,
                countries=outcomes,
            )
        )
