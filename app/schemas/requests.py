from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings


class CountriesRequest(BaseModel):
    per_page: int = Field(
        default=settings.default_per_page,
        ge=1,
        le=20000,
        description="Number of results per page",
        examples=[1000],
    )

    model_config = {"json_schema_extra": {"examples": [{"per_page": 1000}]}}


class IndicatorMetadataRequest(BaseModel):
    indicator_code: str = Field(
        ...,
        min_length=1,
        description="World Bank indicator code",
        examples=["NY.GDP.PCAP.CD"],
    )

    model_config = {"json_schema_extra": {"examples": [{"indicator_code": "NY.GDP.PCAP.CD"}]}}


class ObservationsRequest(BaseModel):
    country: str = Field(
        ...,
        min_length=2,
        max_length=3,
        description="ISO-2 or ISO-3 country code",
        examples=["ES"],
    )
    indicator_code: str = Field(
        ...,
        min_length=1,
        description="World Bank indicator code",
        examples=["NY.GDP.PCAP.CD"],
    )
    start_year: int = Field(
        ...,
        ge=1960,
        description="Start year for data collection",
        examples=[2018],
    )
    end_year: int = Field(
        ...,
        description="End year for data collection",
        examples=[2026],
    )
    per_page: int = Field(
        default=settings.default_per_page,
        ge=1,
        le=20000,
        description="Number of results per page",
        examples=[1000],
    )

    @model_validator(mode="after")
    def validate_years(self) -> "ObservationsRequest":
        current_year = datetime.now().year
        if self.end_year > current_year + 1:
            raise ValueError(f"end_year must be <= {current_year + 1}")
        if self.start_year > self.end_year:
            raise ValueError("start_year must be <= end_year")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "country": "ES",
                    "indicator_code": "NY.GDP.PCAP.CD",
                    "start_year": 2018,
                    "end_year": 2026,
                    "per_page": 1000,
                }
            ]
        }
    }


class IndicatorCatalogItem(BaseModel):
    indicator_code: str = Field(..., min_length=1, description="World Bank indicator code", examples=["NY.GDP.PCAP.CD"])
    indicator_name: str = Field(
        ..., min_length=1, description="Human-readable name", examples=["GDP per capita (current US$)"]
    )
    description: str | None = Field(
        None, description="Extended description", examples=["GDP per capita in current USD"]
    )
    category: str = Field(..., description="Indicator category", examples=["gdp_per_capita"])
    expected_unit: str | None = Field(None, description="Expected unit of measure", examples=["current_usd"])
    marketmind_dimension: str | None = Field(
        None, description="MarketMind dimension mapping", examples=["macroeconomic_stability"]
    )
    is_active: bool = Field(True, description="Whether indicator is active")


class IndicatorCatalogRequest(BaseModel):
    indicators: list[IndicatorCatalogItem] = Field(..., min_length=1, description="List of indicators to register")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "indicators": [
                        {
                            "indicator_code": "NY.GDP.PCAP.CD",
                            "indicator_name": "GDP per capita (current US$)",
                            "description": "GDP per capita in current US dollars.",
                            "category": "gdp_per_capita",
                            "expected_unit": "current_usd",
                            "marketmind_dimension": "macroeconomic_stability",
                            "is_active": True,
                        }
                    ]
                }
            ]
        }
    }


class IndicatorCollectRequest(BaseModel):
    country: str = Field(
        ...,
        min_length=2,
        max_length=3,
        description="ISO-2 or ISO-3 country code",
        examples=["ES"],
    )
    start_year: int = Field(
        ...,
        ge=1960,
        description="Start year for data collection",
        examples=[2018],
    )
    end_year: int = Field(
        ...,
        description="End year for data collection",
        examples=[2026],
    )
    indicator_codes: list[str] | None = Field(
        None,
        description="List of indicator codes to collect. If empty or null, all active indicators are collected.",
        examples=[["NY.GDP.PCAP.CD", "IT.NET.USER.ZS"]],
    )

    @model_validator(mode="after")
    def validate_years(self) -> "IndicatorCollectRequest":
        current_year = datetime.now().year
        if self.end_year > current_year + 1:
            raise ValueError(f"end_year must be <= {current_year + 1}")
        if self.start_year > self.end_year:
            raise ValueError("start_year must be <= end_year")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "country": "ES",
                    "start_year": 2018,
                    "end_year": 2026,
                    "indicator_codes": ["NY.GDP.PCAP.CD", "IT.NET.USER.ZS"],
                }
            ]
        }
    }


class RefreshStaleRequest(BaseModel):
    """Body of the daily maintenance pass. Every field has a default so the
    scheduled call can send `{}`."""

    stale_after_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        description="A country whose last check is older than this gets collected again.",
    )
    # Sem teto por padrão: None quer dizer "todo país vencido nesta passagem".
    # Um teto de 10 contra 24 países não conseguia sequer limpar o atraso de uma
    # noite — sobravam 14, que na noite seguinte disputavam as mesmas 10 vagas
    # com os que tinham acabado de vencer. O teto continua disponível para quem
    # quiser limitar uma partida a frio; ele só deixou de ser o padrão.
    limit: int | None = Field(default=None, ge=1, le=200, description="Most countries to refresh in one pass.")
    # Quando ligado, uma passagem que deixou país para trás responde 503 em vez
    # de 200. É o que transforma o CronJob em rede de segurança: `curl --fail`
    # sai diferente de zero, o Kubernetes retenta, e o que não se resolve fica
    # como Job `Failed` em vez de um sucesso que não coletou nada.
    fail_if_incomplete: bool = Field(
        default=False,
        description="Answer 503 when any country failed, so a caller that retries on error can retry.",
    )
    years_back: int = Field(
        default=5,
        ge=1,
        le=70,
        description="How far back the replayed window reaches, counting from this year.",
    )
