import math
from decimal import Decimal, InvalidOperation
from typing import Any


def make_json_safe(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    return obj


def clean_numeric_value(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, int | float):
        try:
            return Decimal(str(val))
        except InvalidOperation:
            return None
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return None
        try:
            d = Decimal(stripped)
            if d.is_nan() or d.is_infinite():
                return None
            return d
        except InvalidOperation:
            return None
    return None


def clean_string_value(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def clean_integer_value(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return int(val)
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            try:
                return int(float(stripped))
            except (ValueError, OverflowError):
                return None
    return None


def normalize_country_observations(raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in raw_data:
        country_info = item.get("country", {})
        indicator_info = item.get("indicator", {})

        normalized.append(
            {
                "country": item.get("countryiso3code") or country_info.get("id", ""),
                "country_iso2": country_info.get("id", ""),
                "country_name": country_info.get("value"),
                "indicator_code": indicator_info.get("id", ""),
                "indicator_name": indicator_info.get("value"),
                "year": clean_integer_value(item.get("date")),
                "value": clean_numeric_value(item.get("value")),
                "decimal_places": clean_integer_value(item.get("decimal")),
                "unit": clean_string_value(item.get("unit")),
                "obs_status": clean_string_value(item.get("obs_status")),
            }
        )
    return normalized


def normalize_countries(raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in raw_data:
        region = item.get("region", {})
        income_level = item.get("incomeLevel", {})
        lending_type = item.get("lendingType", {})

        normalized.append(
            {
                "country_id": item.get("id", ""),
                "iso2_code": item.get("iso2Code"),
                "name": item.get("name", ""),
                "region_id": region.get("id") if region else None,
                "region_name": region.get("value") if region else None,
                "income_level_id": income_level.get("id") if income_level else None,
                "income_level_name": income_level.get("value") if income_level else None,
                "lending_type_id": lending_type.get("id") if lending_type else None,
                "lending_type_name": lending_type.get("value") if lending_type else None,
                "capital_city": clean_string_value(item.get("capitalCity")),
                "longitude": clean_numeric_value(item.get("longitude")),
                "latitude": clean_numeric_value(item.get("latitude")),
            }
        )
    return normalized


def normalize_indicator_metadata(raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in raw_data:
        source = item.get("source", {})
        normalized.append(
            {
                "indicator_code": item.get("id", ""),
                "indicator_name": item.get("name", ""),
                "source_note": clean_string_value(item.get("sourceNote")),
                "source_organization": clean_string_value(item.get("sourceOrganization")),
                "source_id": source.get("id") if source else None,
                "source_name": source.get("value") if source else None,
            }
        )
    return normalized
