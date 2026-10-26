import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """A espera entre tentativas é real (app/utils/retry.py); nos testes ela
    seria só tempo perdido. A contagem de tentativas continua valendo."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "default_backoff", 0)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


@pytest.fixture
def sample_countries_raw() -> list[dict[str, Any]]:
    return [
        {
            "id": "ESP",
            "iso2Code": "ES",
            "name": "Spain",
            "region": {"id": "ECS", "iso2code": "Z7", "value": "Europe & Central Asia"},
            "incomeLevel": {"id": "HIC", "iso2code": "XD", "value": "High income"},
            "lendingType": {"id": "LNX", "iso2code": "XX", "value": "Not classified"},
            "capitalCity": "Madrid",
            "longitude": "-3.70256",
            "latitude": "40.4165",
        },
        {
            "id": "BRA",
            "iso2Code": "BR",
            "name": "Brazil",
            "region": {"id": "LCN", "iso2code": "ZJ", "value": "Latin America & Caribbean"},
            "incomeLevel": {"id": "UMC", "iso2code": "XT", "value": "Upper middle income"},
            "lendingType": {"id": "IBD", "iso2code": "XF", "value": "IBRD"},
            "capitalCity": "Brasilia",
            "longitude": "-47.9292",
            "latitude": "-15.7801",
        },
    ]


@pytest.fixture
def sample_countries_api_response(sample_countries_raw: list[dict[str, Any]]) -> list[Any]:
    return [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 2},
        sample_countries_raw,
    ]


@pytest.fixture
def sample_observations_raw() -> list[dict[str, Any]]:
    return [
        {
            "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita (current US$)"},
            "country": {"id": "ES", "value": "Spain"},
            "countryiso3code": "ESP",
            "date": "2024",
            "value": 35000.25,
            "unit": "",
            "obs_status": "",
            "decimal": 1,
        },
        {
            "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita (current US$)"},
            "country": {"id": "ES", "value": "Spain"},
            "countryiso3code": "ESP",
            "date": "2023",
            "value": 33500.10,
            "unit": "",
            "obs_status": "",
            "decimal": 1,
        },
        {
            "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita (current US$)"},
            "country": {"id": "ES", "value": "Spain"},
            "countryiso3code": "ESP",
            "date": "2022",
            "value": None,
            "unit": "",
            "obs_status": "",
            "decimal": 1,
        },
    ]


@pytest.fixture
def sample_observations_api_response(sample_observations_raw: list[dict[str, Any]]) -> list[Any]:
    return [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 3},
        sample_observations_raw,
    ]


@pytest.fixture
def sample_indicator_metadata_raw() -> list[dict[str, Any]]:
    return [
        {
            "id": "NY.GDP.PCAP.CD",
            "name": "GDP per capita (current US$)",
            "unit": "",
            "source": {"id": "2", "value": "World Development Indicators"},
            "sourceNote": "GDP per capita is gross domestic product divided by midyear population.",
            "sourceOrganization": "World Bank national accounts data, and OECD National Accounts data files.",
        }
    ]


@pytest.fixture
def sample_indicator_metadata_api_response(sample_indicator_metadata_raw: list[dict[str, Any]]) -> list[Any]:
    return [
        {"page": 1, "pages": 1, "per_page": 50, "total": 1},
        sample_indicator_metadata_raw,
    ]


@pytest.fixture
def sample_uuid() -> uuid.UUID:
    return uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def sample_datetime() -> datetime:
    return datetime(2026, 6, 29, 10, 0, 0)
