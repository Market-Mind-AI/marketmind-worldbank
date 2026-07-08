import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.worldbank_client import WorldBankClient
from app.core.config import settings
from app.core.logging import logger
from app.domain.enums import IngestionStatus, WorldBankEndpoint
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
    IndicatorMetadataData,
    IndicatorMetadataItem,
    IndicatorMetadataResponse,
    Metadata,
    ObservationItem,
    ObservationsData,
    ObservationsResponse,
    RequestInfo,
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
        "indicator_code": "IT.NET.BBND.P2",
        "indicator_name": "Fixed broadband subscriptions (per 100 people)",
        "description": "Fixed broadband subscriptions per 100 people.",
        "category": "broadband_subscriptions",
        "expected_unit": "per_100_people",
        "marketmind_dimension": "digital_readiness",
    },
    # Macro Demand Structure (added 2026-07-08, marketmind-core GDP=C+I+G+NX
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
        "description": "Government spending share of GDP — context only in marketmind-core (no defensible "
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
                from app.core.exceptions import WorldBankEmptyResponseError

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

            entities = await self._observation_repo.bulk_create(
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

    async def collect_indicators(self, request: IndicatorCollectRequest) -> CollectResponse:
        endpoint = WorldBankEndpoint.INDICATORS_COLLECT
        start = utc_now()

        run = await self._ingestion_repo.create(source="worldbank", request_payload=request.model_dump())

        wb_request = await self._request_repo.create(
            ingestion_run_id=run.id,
            endpoint=endpoint,
            url=f"{settings.worldbank_base_url}/country/{request.country}/indicator/...",
            country=request.country,
            start_year=request.start_year,
            end_year=request.end_year,
        )

        try:
            if request.indicator_codes:
                indicators = await self._indicator_repo.get_by_codes(request.indicator_codes)
            else:
                indicators = await self._indicator_repo.get_active()

            if not indicators:
                from app.core.exceptions import WorldBankEmptyResponseError

                raise WorldBankEmptyResponseError(
                    "No active indicators found in catalog. Seed the catalog first with POST /indicators/catalog/seed"
                )

            all_observations: list[dict[str, Any]] = []
            indicators_collected = 0
            failed_indicators: list[str] = []

            for indicator in indicators:
                try:
                    data, raw_responses, final_url = await self._client.get_observations(
                        country=request.country,
                        indicator_code=indicator.indicator_code,
                        start_year=request.start_year,
                        end_year=request.end_year,
                    )

                    await self._raw_response_repo.bulk_create(
                        worldbank_request_id=wb_request.id,
                        endpoint=endpoint,
                        request_payload={
                            "country": request.country,
                            "indicator_code": indicator.indicator_code,
                            "start_year": request.start_year,
                            "end_year": request.end_year,
                        },
                        raw_responses=raw_responses,
                    )

                    normalized = normalize_country_observations(data)
                    all_observations.extend(normalized)
                    indicators_collected += 1

                    logger.info(
                        f"Collected indicator={indicator.indicator_code} | country={request.country} "
                        f"| records={len(normalized)}"
                    )

                except Exception as indicator_error:
                    failed_indicators.append(indicator.indicator_code)
                    logger.warning(
                        f"Failed to collect indicator={indicator.indicator_code} | "
                        f"country={request.country} | error={indicator_error}"
                    )

            entities = await self._observation_repo.bulk_create(
                worldbank_request_id=wb_request.id,
                observations=all_observations,
            )

            exec_time = elapsed_ms(start)
            run_failed = bool(failed_indicators) and indicators_collected == 0
            if run_failed:
                # Every requested indicator failed (transient network error,
                # genuinely absent data, etc.) — marking this "success" would
                # make callers' coverage tracking (e.g. marketmind-core's
                # coverage_index) believe the gap is durably filled with zero
                # actual data, and never retry it. Found 2026-07-03 during a
                # real bulk-collection run: a transient failure for one
                # country/indicator silently looked identical to success.
                await self._ingestion_repo.mark_failed(
                    run, exec_time, f"All indicators failed: {', '.join(failed_indicators)}"
                )
            else:
                await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(endpoint, run.id, wb_request.id, exec_time, len(entities), country=request.country)

            return CollectResponse(
                request=self._request_info(
                    endpoint=endpoint,
                    country=request.country,
                    start_year=request.start_year,
                    end_year=request.end_year,
                ),
                metadata=self._metadata(
                    endpoint,
                    exec_time,
                    len(entities),
                    run.id,
                    wb_request.id,
                    status="failed" if run_failed else "success",
                ),  # fmt: skip
                data=CollectData(
                    indicators_collected=indicators_collected,
                    total_observations=len(entities),
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
                        for obs in all_observations
                        if obs.get("year") is not None
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
