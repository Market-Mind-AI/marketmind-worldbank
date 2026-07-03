from typing import Any


def parse_worldbank_response(raw_response: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(raw_response, list) or len(raw_response) < 2:
        return {}, []

    metadata = raw_response[0] if isinstance(raw_response[0], dict) else {}
    data = raw_response[1] if isinstance(raw_response[1], list) else []

    return metadata, data


def get_total_pages(metadata: dict[str, Any]) -> int:
    return int(metadata.get("pages", 1))


def get_total_records(metadata: dict[str, Any]) -> int:
    return int(metadata.get("total", 0))
