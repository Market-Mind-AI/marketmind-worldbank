import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import (
    WorldBankClientError,
    WorldBankEmptyResponseError,
    WorldBankParsingError,
    WorldBankRateLimitError,
    WorldBankTimeoutError,
    WorldBankTransientError,
)
from app.core.logging import logger
from app.utils.pagination import get_total_pages, parse_worldbank_response
from app.utils.retry import backoff_seconds, is_retryable_status


class WorldBankClient:
    def __init__(self) -> None:
        self._base_url = settings.worldbank_base_url
        self._timeout = settings.default_timeout
        self._retries = settings.default_retries
        self._format = settings.default_format
        self._per_page = settings.default_per_page

    def _build_params(self, extra_params: dict[str, Any] | None = None, per_page: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "format": self._format,
            "per_page": per_page or self._per_page,
        }
        if extra_params:
            params.update(extra_params)
        return params

    async def get_raw(self, url: str, params: dict[str, Any] | None = None) -> tuple[Any, str]:
        """Uma chamada à API, insistindo enquanto a falha for passageira.

        Quando e quanto insistir é a política comum aos quatro coletores, em
        app/utils/retry.py. Esgotadas as tentativas, a falha passageira sobe como
        WorldBankTransientError (503). Um 404 é a fonte dizendo que não tem o
        dado e sobe como WorldBankEmptyResponseError, sem repetir; os outros 4xx
        sobem como WorldBankClientError, também sem repetir.
        """
        last_error: WorldBankTransientError | None = None
        for attempt in range(1, self._retries + 1):
            retry_after: str | None = None
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params)
            except httpx.TimeoutException:
                last_error = WorldBankTimeoutError(f"Timeout calling World Bank API: {url}")
            except httpx.HTTPError as e:
                # Rede: DNS, conexão recusada ou derrubada. É a fonte (ou o
                # caminho até ela) fora do ar, e esperar resolve.
                last_error = WorldBankTransientError(f"Network error calling World Bank API: {e}")
            else:
                status = response.status_code
                if is_retryable_status(status):
                    retry_after = response.headers.get("Retry-After")
                    if status == 429:
                        last_error = WorldBankRateLimitError(f"Rate limited: {status}")
                    else:
                        last_error = WorldBankTransientError(f"Server error {status}: {url}")
                elif status == 404:
                    raise WorldBankEmptyResponseError(f"No data at {url}")
                elif status >= 400:
                    raise WorldBankClientError(f"HTTP error {status}: {url}")
                else:
                    try:
                        data = response.json()
                    except Exception as e:
                        raise WorldBankParsingError(f"Failed to parse JSON response: {e}") from e
                    _raise_if_rejected(data, url)
                    return data, str(response.url)

            logger.warning(f"World Bank attempt {attempt}/{self._retries} failed: {last_error}")
            if attempt < self._retries:
                await asyncio.sleep(backoff_seconds(attempt, retry_after))

        raise last_error or WorldBankTransientError(f"Failed after {self._retries} attempts: {url}")

    async def _fetch_all_pages(
        self, url: str, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[Any], str]:
        all_data: list[dict[str, Any]] = []
        all_raw: list[Any] = []

        params["page"] = 1
        raw_response, final_url = await self.get_raw(url, params)
        all_raw.append(raw_response)

        metadata, data = parse_worldbank_response(raw_response)
        all_data.extend(data)

        total_pages = get_total_pages(metadata)

        for page in range(2, total_pages + 1):
            params["page"] = page
            raw_page, _ = await self.get_raw(url, params)
            all_raw.append(raw_page)
            _, page_data = parse_worldbank_response(raw_page)
            all_data.extend(page_data)

        logger.info(
            f"Fetched {len(all_data)} records across {total_pages} page(s) | url={final_url}"
        )

        return all_data, all_raw, final_url

    async def get_countries(self, per_page: int | None = None) -> tuple[list[dict[str, Any]], list[Any], str]:
        url = f"{self._base_url}/country"
        params = self._build_params(per_page=per_page)

        data, raw_responses, final_url = await self._fetch_all_pages(url, params)

        if not data:
            raise WorldBankEmptyResponseError("No countries returned from World Bank API")

        return data, raw_responses, final_url

    async def get_indicator_metadata(
        self, indicator_code: str
    ) -> tuple[list[dict[str, Any]], list[Any], str]:
        url = f"{self._base_url}/indicator/{indicator_code}"
        params = self._build_params()

        raw_response, final_url = await self.get_raw(url, params)
        metadata, data = parse_worldbank_response(raw_response)

        if not data:
            raise WorldBankEmptyResponseError(f"No metadata returned for indicator: {indicator_code}")

        return data, [raw_response], final_url

    async def get_observations(
        self,
        country: str,
        indicator_code: str,
        start_year: int,
        end_year: int,
        per_page: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[Any], str]:
        url = f"{self._base_url}/country/{country}/indicator/{indicator_code}"
        params = self._build_params(
            extra_params={"date": f"{start_year}:{end_year}"},
            per_page=per_page,
        )

        data, raw_responses, final_url = await self._fetch_all_pages(url, params)

        return data, raw_responses, final_url


def _raise_if_rejected(data: Any, url: str) -> None:
    """A API do World Bank recusa um pedido com 200 e uma mensagem no lugar dos
    dados -- código de indicador ou de país que ela não conhece. Sem esta
    checagem a recusa parecia "a fonte não tem dado", que conta como
    verificação: um código errado ficaria "fresco" por 90 dias sem nunca ter
    sido respondido. Recusa é erro do pedido, não ausência de dado."""
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) and "message" in data[0]:
        raise WorldBankClientError(f"World Bank rejected the request {url}: {data[0]['message']}")
