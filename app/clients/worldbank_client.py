from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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

# Retry transient upstream failures — timeouts, 429, and 5xx (the World Bank
# public API returns intermittent 502/503/504 under load; without retry a
# single blip permanently drops an indicator and, downstream, aborts a whole
# MarketMind analysis via its completeness gate). Non-transient errors (4xx,
# parse) are NOT retried.
RETRY_DECORATOR = retry(
    stop=stop_after_attempt(settings.default_retries),
    wait=wait_exponential(multiplier=settings.default_backoff, min=2, max=60),
    retry=retry_if_exception_type((WorldBankTimeoutError, WorldBankRateLimitError, WorldBankTransientError)),
    reraise=True,
)


class WorldBankClient:
    def __init__(self) -> None:
        self._base_url = settings.worldbank_base_url
        self._timeout = settings.default_timeout
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

    @RETRY_DECORATOR
    async def get_raw(self, url: str, params: dict[str, Any] | None = None) -> tuple[Any, str]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code == 429:
                    raise WorldBankRateLimitError(f"Rate limited: {response.status_code}")
                if response.status_code >= 500:
                    raise WorldBankTransientError(f"Server error {response.status_code}: {url}")

                response.raise_for_status()

                try:
                    data = response.json()
                except Exception as e:
                    raise WorldBankParsingError(f"Failed to parse JSON response: {e}") from e

                return data, str(response.url)

        except httpx.TimeoutException as e:
            raise WorldBankTimeoutError(f"Timeout calling World Bank API: {url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise WorldBankRateLimitError(f"Rate limited: {e.response.status_code}") from e
            raise WorldBankClientError(f"HTTP error {e.response.status_code}: {url}") from e
        except (WorldBankTimeoutError, WorldBankRateLimitError, WorldBankTransientError, WorldBankParsingError):
            raise
        except httpx.HTTPError as e:
            raise WorldBankClientError(f"HTTP error calling World Bank API: {e}") from e

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
