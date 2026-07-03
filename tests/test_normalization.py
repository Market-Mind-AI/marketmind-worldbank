from decimal import Decimal
from typing import Any

from app.utils.normalization import (
    clean_integer_value,
    clean_numeric_value,
    clean_string_value,
    normalize_countries,
    normalize_country_observations,
    normalize_indicator_metadata,
)


class TestCleanNumericValue:
    def test_none(self) -> None:
        assert clean_numeric_value(None) is None

    def test_integer(self) -> None:
        assert clean_numeric_value(42) == Decimal("42")

    def test_float(self) -> None:
        assert clean_numeric_value(3.14) == Decimal("3.14")

    def test_string_number(self) -> None:
        assert clean_numeric_value("123.45") == Decimal("123.45")

    def test_empty_string(self) -> None:
        assert clean_numeric_value("") is None

    def test_nan(self) -> None:
        assert clean_numeric_value(float("nan")) is None

    def test_inf(self) -> None:
        assert clean_numeric_value(float("inf")) is None

    def test_non_numeric_string(self) -> None:
        assert clean_numeric_value("abc") is None

    def test_decimal_passthrough(self) -> None:
        d = Decimal("99.99")
        assert clean_numeric_value(d) == d


class TestCleanStringValue:
    def test_none(self) -> None:
        assert clean_string_value(None) is None

    def test_normal_string(self) -> None:
        assert clean_string_value("hello") == "hello"

    def test_empty_string(self) -> None:
        assert clean_string_value("") is None

    def test_whitespace_string(self) -> None:
        assert clean_string_value("   ") is None

    def test_strips_whitespace(self) -> None:
        assert clean_string_value("  hello  ") == "hello"


class TestCleanIntegerValue:
    def test_none(self) -> None:
        assert clean_integer_value(None) is None

    def test_integer(self) -> None:
        assert clean_integer_value(42) == 42

    def test_float(self) -> None:
        assert clean_integer_value(3.7) == 3

    def test_string_integer(self) -> None:
        assert clean_integer_value("2024") == 2024

    def test_nan(self) -> None:
        assert clean_integer_value(float("nan")) is None

    def test_empty_string(self) -> None:
        assert clean_integer_value("") is None


class TestNormalizeCountries:
    def test_normalize(self, sample_countries_raw: list[dict[str, Any]]) -> None:
        result = normalize_countries(sample_countries_raw)
        assert len(result) == 2
        assert result[0]["country_id"] == "ESP"
        assert result[0]["iso2_code"] == "ES"
        assert result[0]["name"] == "Spain"
        assert result[0]["region_name"] == "Europe & Central Asia"
        assert result[0]["income_level_name"] == "High income"
        assert result[0]["capital_city"] == "Madrid"

    def test_empty_list(self) -> None:
        assert normalize_countries([]) == []


class TestNormalizeCountryObservations:
    def test_normalize(self, sample_observations_raw: list[dict[str, Any]]) -> None:
        result = normalize_country_observations(sample_observations_raw)
        assert len(result) == 3
        assert result[0]["country"] == "ESP"
        assert result[0]["country_iso2"] == "ES"
        assert result[0]["indicator_code"] == "NY.GDP.PCAP.CD"
        assert result[0]["year"] == 2024
        assert result[0]["value"] == Decimal("35000.25")

    def test_null_value_preserved(self, sample_observations_raw: list[dict[str, Any]]) -> None:
        result = normalize_country_observations(sample_observations_raw)
        assert result[2]["value"] is None

    def test_empty_list(self) -> None:
        assert normalize_country_observations([]) == []


class TestNormalizeIndicatorMetadata:
    def test_normalize(self, sample_indicator_metadata_raw: list[dict[str, Any]]) -> None:
        result = normalize_indicator_metadata(sample_indicator_metadata_raw)
        assert len(result) == 1
        assert result[0]["indicator_code"] == "NY.GDP.PCAP.CD"
        assert result[0]["indicator_name"] == "GDP per capita (current US$)"
        assert "GDP per capita" in (result[0]["source_note"] or "")
        assert result[0]["source_organization"] is not None

    def test_empty_list(self) -> None:
        assert normalize_indicator_metadata([]) == []
