import pytest
from pydantic import ValidationError

from app.schemas.requests import (
    CountriesRequest,
    IndicatorCatalogItem,
    IndicatorCatalogRequest,
    IndicatorCollectRequest,
    IndicatorMetadataRequest,
    ObservationsRequest,
)


class TestCountriesRequest:
    def test_default_per_page(self) -> None:
        req = CountriesRequest()
        assert req.per_page == 1000

    def test_custom_per_page(self) -> None:
        req = CountriesRequest(per_page=500)
        assert req.per_page == 500

    def test_invalid_per_page_zero(self) -> None:
        with pytest.raises(ValidationError):
            CountriesRequest(per_page=0)

    def test_invalid_per_page_too_large(self) -> None:
        with pytest.raises(ValidationError):
            CountriesRequest(per_page=30000)


class TestIndicatorMetadataRequest:
    def test_valid_indicator(self) -> None:
        req = IndicatorMetadataRequest(indicator_code="NY.GDP.PCAP.CD")
        assert req.indicator_code == "NY.GDP.PCAP.CD"

    def test_empty_indicator(self) -> None:
        with pytest.raises(ValidationError):
            IndicatorMetadataRequest(indicator_code="")


class TestObservationsRequest:
    def test_valid_request(self) -> None:
        req = ObservationsRequest(
            country="ES",
            indicator_code="NY.GDP.PCAP.CD",
            start_year=2018,
            end_year=2024,
        )
        assert req.country == "ES"
        assert req.start_year == 2018
        assert req.end_year == 2024

    def test_start_year_after_end_year(self) -> None:
        with pytest.raises(ValidationError, match="start_year must be <= end_year"):
            ObservationsRequest(
                country="ES",
                indicator_code="NY.GDP.PCAP.CD",
                start_year=2025,
                end_year=2020,
            )

    def test_start_year_too_old(self) -> None:
        with pytest.raises(ValidationError):
            ObservationsRequest(
                country="ES",
                indicator_code="NY.GDP.PCAP.CD",
                start_year=1900,
                end_year=2024,
            )

    def test_country_too_short(self) -> None:
        with pytest.raises(ValidationError):
            ObservationsRequest(
                country="E",
                indicator_code="NY.GDP.PCAP.CD",
                start_year=2018,
                end_year=2024,
            )

    def test_country_too_long(self) -> None:
        with pytest.raises(ValidationError):
            ObservationsRequest(
                country="ESPA",
                indicator_code="NY.GDP.PCAP.CD",
                start_year=2018,
                end_year=2024,
            )

    def test_iso3_country(self) -> None:
        req = ObservationsRequest(
            country="ESP",
            indicator_code="NY.GDP.PCAP.CD",
            start_year=2018,
            end_year=2024,
        )
        assert req.country == "ESP"


class TestIndicatorCatalogRequest:
    def test_valid_catalog(self) -> None:
        req = IndicatorCatalogRequest(
            indicators=[
                IndicatorCatalogItem(
                    indicator_code="NY.GDP.PCAP.CD",
                    indicator_name="GDP per capita",
                    category="gdp_per_capita",
                )
            ]
        )
        assert len(req.indicators) == 1

    def test_empty_indicators(self) -> None:
        with pytest.raises(ValidationError):
            IndicatorCatalogRequest(indicators=[])


class TestIndicatorCollectRequest:
    def test_valid_collect(self) -> None:
        req = IndicatorCollectRequest(
            country="ES",
            start_year=2018,
            end_year=2024,
            indicator_codes=["NY.GDP.PCAP.CD"],
        )
        assert req.country == "ES"
        assert req.indicator_codes == ["NY.GDP.PCAP.CD"]

    def test_null_indicator_codes(self) -> None:
        req = IndicatorCollectRequest(
            country="ES",
            start_year=2018,
            end_year=2024,
            indicator_codes=None,
        )
        assert req.indicator_codes is None

    def test_invalid_years(self) -> None:
        with pytest.raises(ValidationError, match="start_year must be <= end_year"):
            IndicatorCollectRequest(
                country="ES",
                start_year=2025,
                end_year=2020,
            )
