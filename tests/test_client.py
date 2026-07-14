from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.clients.worldbank_client import WorldBankClient
from app.core.exceptions import (
    WorldBankEmptyResponseError,
    WorldBankParsingError,
    WorldBankTimeoutError,
    WorldBankTransientError,
)


def _make_mock_response(json_data: Any, url: str = "https://api.worldbank.org/v2") -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_data
    mock_response.url = url
    mock_response.raise_for_status = MagicMock()
    return mock_response


def _make_mock_client(mock_response: MagicMock) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestWorldBankClient:
    @pytest.fixture
    def client(self) -> WorldBankClient:
        return WorldBankClient()

    @pytest.mark.asyncio
    async def test_get_countries_success(
        self, client: WorldBankClient, sample_countries_api_response: list[Any]
    ) -> None:
        mock_response = _make_mock_response(
            sample_countries_api_response, "https://api.worldbank.org/v2/country?format=json"
        )

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            data, raw_responses, url = await client.get_countries()
            assert len(data) == 2
            assert data[0]["id"] == "ESP"
            assert len(raw_responses) == 1

    @pytest.mark.asyncio
    async def test_get_countries_empty(self, client: WorldBankClient) -> None:
        mock_response = _make_mock_response(
            [{"page": 1, "pages": 1, "per_page": 1000, "total": 0}, []], "https://api.worldbank.org/v2/country"
        )

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            with pytest.raises(WorldBankEmptyResponseError):
                await client.get_countries()

    @pytest.mark.asyncio
    async def test_get_observations_success(
        self, client: WorldBankClient, sample_observations_api_response: list[Any]
    ) -> None:
        mock_response = _make_mock_response(
            sample_observations_api_response,
            "https://api.worldbank.org/v2/country/ES/indicator/NY.GDP.PCAP.CD",
        )

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            data, raw_responses, url = await client.get_observations("ES", "NY.GDP.PCAP.CD", 2020, 2024)
            assert len(data) == 3
            assert data[0]["indicator"]["id"] == "NY.GDP.PCAP.CD"

    @pytest.mark.asyncio
    async def test_get_indicator_metadata_success(
        self, client: WorldBankClient, sample_indicator_metadata_api_response: list[Any]
    ) -> None:
        mock_response = _make_mock_response(
            sample_indicator_metadata_api_response,
            "https://api.worldbank.org/v2/indicator/NY.GDP.PCAP.CD",
        )

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            data, raw_responses, url = await client.get_indicator_metadata("NY.GDP.PCAP.CD")
            assert len(data) == 1
            assert data[0]["id"] == "NY.GDP.PCAP.CD"

    @pytest.mark.asyncio
    async def test_get_indicator_metadata_empty(self, client: WorldBankClient) -> None:
        mock_response = _make_mock_response(
            [{"page": 1, "pages": 1, "per_page": 50, "total": 0}, []],
            "https://api.worldbank.org/v2/indicator/INVALID",
        )

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            with pytest.raises(WorldBankEmptyResponseError):
                await client.get_indicator_metadata("INVALID")

    @pytest.mark.asyncio
    async def test_timeout_error(self, client: WorldBankClient) -> None:
        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(WorldBankTimeoutError):
                await client.get_raw("https://api.worldbank.org/v2/country", {})

    @pytest.mark.asyncio
    async def test_transient_5xx_raises_retryable_error(self, client: WorldBankClient) -> None:
        # The World Bank public API returns intermittent 502/503/504; those must
        # map to WorldBankTransientError so the RETRY_DECORATOR retries them
        # (a single blip must not permanently drop an indicator).
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.url = "https://api.worldbank.org/v2/country"

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            with pytest.raises(WorldBankTransientError):
                await client.get_raw("https://api.worldbank.org/v2/country", {})

    @pytest.mark.asyncio
    async def test_json_parse_error(self, client: WorldBankClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("bad json")
        mock_response.url = "https://api.worldbank.org/v2/country"
        mock_response.raise_for_status = MagicMock()

        with patch("app.clients.worldbank_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = _make_mock_client(mock_response)

            with pytest.raises(WorldBankParsingError):
                await client.get_raw("https://api.worldbank.org/v2/country", {})
