from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class RequestInfo(BaseModel):
    endpoint: str
    country: str | None = None
    indicator_code: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    per_page: int | None = None


class Metadata(BaseModel):
    provider: str = "World Bank"
    endpoint: str
    execution_time_ms: int
    records: int
    stored: bool = True
    ingestion_run_id: UUID
    worldbank_request_id: UUID
    status: str
    collected_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    app_name: str
    environment: str


class VersionResponse(BaseModel):
    app_name: str
    version: str
    environment: str


class CountryItem(BaseModel):
    country_id: str
    iso2_code: str | None = None
    name: str
    region_name: str | None = None
    income_level_name: str | None = None
    capital_city: str | None = None


class CountriesData(BaseModel):
    countries: list[CountryItem]


class CountriesResponse(BaseModel):
    request: RequestInfo
    metadata: Metadata
    data: CountriesData


class IndicatorMetadataItem(BaseModel):
    indicator_code: str
    indicator_name: str
    source_note: str | None = None
    source_organization: str | None = None


class IndicatorMetadataData(BaseModel):
    indicator: IndicatorMetadataItem


class IndicatorMetadataResponse(BaseModel):
    request: RequestInfo
    metadata: Metadata
    data: IndicatorMetadataData


class ObservationItem(BaseModel):
    country: str
    country_iso2: str | None = None
    country_name: str | None = None
    indicator_code: str
    indicator_name: str | None = None
    year: int
    value: Decimal | None = None


class ObservationsData(BaseModel):
    observations: list[ObservationItem]


class ObservationsResponse(BaseModel):
    request: RequestInfo
    metadata: Metadata
    data: ObservationsData


class CatalogIndicatorItem(BaseModel):
    id: UUID
    indicator_code: str
    indicator_name: str
    description: str | None = None
    source_note: str | None = None
    source_organization: str | None = None
    category: str
    expected_unit: str | None = None
    marketmind_dimension: str | None = None
    is_active: bool
    created_at: datetime


class CatalogData(BaseModel):
    indicators: list[CatalogIndicatorItem]


class CatalogResponse(BaseModel):
    data: CatalogData


class CatalogSeedResponse(BaseModel):
    request: RequestInfo
    metadata: Metadata
    data: CatalogData


class CatalogCreateResponse(BaseModel):
    request: RequestInfo
    metadata: Metadata
    data: CatalogData


class CollectData(BaseModel):
    indicators_collected: int
    total_observations: int
    observations: list[ObservationItem]


class CollectResponse(BaseModel):
    request: RequestInfo
    metadata: Metadata
    data: CollectData


class IngestionRunResponse(BaseModel):
    id: UUID
    source: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    execution_time_ms: int | None = None
    request_payload: dict
    error_message: str | None = None
    created_at: datetime


class WorldBankRequestResponse(BaseModel):
    id: UUID
    ingestion_run_id: UUID
    endpoint: str
    url: str
    country: str | None = None
    indicator_code: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    query_params: dict | None = None
    created_at: datetime


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error description")


class FreshnessItem(BaseModel):
    country: str
    indicator_code: str
    # When we last ASKED the World Bank, not how recent the data is. These are
    # different questions and only the first one says whether to fetch again:
    # GDP and population are published yearly, so a value from 2024 is current,
    # not stale, and a rule written against the data's own date would re-fetch
    # every indicator every day forever.
    last_checked_at: datetime | None = None
    last_observation_at: datetime | None = None
    latest_year: int | None = None
    observation_count: int = 0
    stale: bool


class FreshnessData(BaseModel):
    as_of: datetime
    stale_after_days: int
    items: list[FreshnessItem]


class FreshnessResponse(BaseModel):
    data: FreshnessData


class SeriesPoint(BaseModel):
    year: int
    value: Decimal
    unit: str | None = None
    obs_status: str | None = None


class SeriesData(BaseModel):
    country_iso2: str
    indicator_code: str
    points: list[SeriesPoint]


class SeriesResponse(BaseModel):
    data: SeriesData
