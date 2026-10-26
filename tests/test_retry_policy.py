"""A política de repetição é a mesma nos quatro coletores (app/utils/retry.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.clients.worldbank_client import WorldBankClient
from app.core.config import settings
from app.core.exceptions import (
    WorldBankClientError,
    WorldBankEmptyResponseError,
    WorldBankTransientError,
)
from app.utils.retry import MAX_BACKOFF_SECONDS, backoff_seconds, is_retryable_status


def _response(status: int, json_data: object = None, headers: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = json_data
    response.headers = headers or {}
    response.url = "https://api.worldbank.org/v2/x"
    return response


def _client_returning(*effects: object) -> MagicMock:
    http = AsyncMock()
    http.get.side_effect = list(effects)
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=http)


def test_what_is_retried() -> None:
    assert all(is_retryable_status(s) for s in (408, 429, 500, 502, 503, 504))
    assert not any(is_retryable_status(s) for s in (200, 400, 401, 403, 404, 422))


def test_the_wait_doubles_with_jitter_and_has_a_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "default_backoff", 2)

    assert 2 <= backoff_seconds(1) <= 2.5
    assert 8 <= backoff_seconds(3) <= 10
    assert backoff_seconds(20) == MAX_BACKOFF_SECONDS


def test_retry_after_is_honoured_up_to_the_ceiling() -> None:
    assert backoff_seconds(1, "7") == 7
    assert backoff_seconds(1, "3600") == MAX_BACKOFF_SECONDS


async def test_a_429_is_retried_and_then_succeeds() -> None:
    factory = _client_returning(_response(429, headers={"Retry-After": "0"}), _response(200, [{"page": 1}, []]))

    with patch("app.clients.worldbank_client.httpx.AsyncClient", factory):
        data, _ = await WorldBankClient().get_raw("https://api.worldbank.org/v2/x")

    assert data == [{"page": 1}, []]


async def test_a_network_error_is_retried() -> None:
    factory = _client_returning(httpx.ConnectError("dns"), _response(200, [{"page": 1}, []]))

    with patch("app.clients.worldbank_client.httpx.AsyncClient", factory):
        data, _ = await WorldBankClient().get_raw("https://api.worldbank.org/v2/x")

    assert data == [{"page": 1}, []]


async def test_a_source_that_stays_down_is_a_503_after_every_attempt() -> None:
    factory = _client_returning(*[_response(502) for _ in range(settings.default_retries)])

    with patch("app.clients.worldbank_client.httpx.AsyncClient", factory):
        with pytest.raises(WorldBankTransientError) as raised:
            await WorldBankClient().get_raw("https://api.worldbank.org/v2/x")

    assert raised.value.status_code == 503
    assert factory.return_value.get.await_count == settings.default_retries


async def test_another_4xx_is_never_retried() -> None:
    factory = _client_returning(_response(400))

    with patch("app.clients.worldbank_client.httpx.AsyncClient", factory):
        with pytest.raises(WorldBankClientError):
            await WorldBankClient().get_raw("https://api.worldbank.org/v2/x")

    assert factory.return_value.get.await_count == 1


async def test_a_404_is_the_source_saying_it_has_no_data() -> None:
    factory = _client_returning(_response(404))

    with patch("app.clients.worldbank_client.httpx.AsyncClient", factory):
        with pytest.raises(WorldBankEmptyResponseError):
            await WorldBankClient().get_raw("https://api.worldbank.org/v2/x")


async def test_a_rejected_request_is_not_mistaken_for_no_data() -> None:
    """A recusa vem com 200 e uma mensagem; lida como "sem dado", um código
    errado contaria como verificado."""
    recusa = [{"message": [{"id": "120", "key": "Invalid value"}]}]
    factory = _client_returning(_response(200, recusa))

    with patch("app.clients.worldbank_client.httpx.AsyncClient", factory):
        with pytest.raises(WorldBankClientError):
            await WorldBankClient().get_raw("https://api.worldbank.org/v2/x")
