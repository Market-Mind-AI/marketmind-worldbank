from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


class TestHealthEndpoint:
    def test_health_ok(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        session.execute.return_value = mock_result

        async def override_session():  # type: ignore[no-untyped-def]
            yield session

        app.dependency_overrides[get_session] = override_session

        try:
            client = TestClient(app)
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["database"] == "connected"
            assert data["app_name"] == "marketmind-worldbank"
        finally:
            app.dependency_overrides.clear()

    def test_version(self) -> None:
        client = TestClient(app)
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == "marketmind-worldbank"
        assert "version" in data


class TestCountriesEndpoint:
    @patch("app.clients.worldbank_client.WorldBankClient.get_countries")
    def test_countries_success(
        self,
        mock_get_countries: AsyncMock,
        sample_countries_raw: list[dict[str, Any]],
    ) -> None:
        session = _mock_session()

        async def override_session():  # type: ignore[no-untyped-def]
            yield session

        app.dependency_overrides[get_session] = override_session

        mock_get_countries.return_value = (
            sample_countries_raw,
            [[{"page": 1}, sample_countries_raw]],
            "https://api.worldbank.org/v2/country",
        )

        try:
            client = TestClient(app)
            response = client.post("/countries", json={"per_page": 1000})
            assert response.status_code == 200
            data = response.json()
            assert "metadata" in data
            assert "data" in data
            assert data["metadata"]["provider"] == "World Bank"
            assert data["metadata"]["status"] == "success"
            assert data["metadata"]["stored"] is True
            assert "ingestion_run_id" in data["metadata"]
            assert "worldbank_request_id" in data["metadata"]
            assert len(data["data"]["countries"]) == 2
            assert data["data"]["countries"][0]["country_id"] == "ESP"
        finally:
            app.dependency_overrides.clear()


class TestObservationsEndpoint:
    @patch("app.clients.worldbank_client.WorldBankClient.get_observations")
    def test_observations_success(
        self,
        mock_get_observations: AsyncMock,
        sample_observations_raw: list[dict[str, Any]],
    ) -> None:
        session = _mock_session()

        async def override_session():  # type: ignore[no-untyped-def]
            yield session

        app.dependency_overrides[get_session] = override_session

        mock_get_observations.return_value = (
            sample_observations_raw,
            [[{"page": 1}, sample_observations_raw]],
            "https://api.worldbank.org/v2/country/ES/indicator/NY.GDP.PCAP.CD",
        )

        try:
            client = TestClient(app)
            response = client.post(
                "/observations",
                json={
                    "country": "ES",
                    "indicator_code": "NY.GDP.PCAP.CD",
                    "start_year": 2020,
                    "end_year": 2024,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["provider"] == "World Bank"
            assert data["metadata"]["endpoint"] == "observations"
            assert len(data["data"]["observations"]) == 3
        finally:
            app.dependency_overrides.clear()


class TestIndicatorMetadataEndpoint:
    @patch("app.clients.worldbank_client.WorldBankClient.get_indicator_metadata")
    def test_metadata_success(
        self,
        mock_get_metadata: AsyncMock,
        sample_indicator_metadata_raw: list[dict[str, Any]],
    ) -> None:
        session = _mock_session()

        async def override_session():  # type: ignore[no-untyped-def]
            yield session

        app.dependency_overrides[get_session] = override_session

        mock_get_metadata.return_value = (
            sample_indicator_metadata_raw,
            [[{"page": 1}, sample_indicator_metadata_raw]],
            "https://api.worldbank.org/v2/indicator/NY.GDP.PCAP.CD",
        )

        try:
            client = TestClient(app)
            response = client.post("/indicators/metadata", json={"indicator_code": "NY.GDP.PCAP.CD"})
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["indicator"]["indicator_code"] == "NY.GDP.PCAP.CD"
            assert data["data"]["indicator"]["indicator_name"] == "GDP per capita (current US$)"
        finally:
            app.dependency_overrides.clear()


class TestCatalogSeedEndpoint:
    def test_seed_catalog(self) -> None:
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        async def override_session():  # type: ignore[no-untyped-def]
            yield session

        app.dependency_overrides[get_session] = override_session

        try:
            client = TestClient(app)
            response = client.post("/indicators/catalog/seed")
            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["status"] == "success"
            # 7 original + FP.CPI.TOTL.ZG (was live in the catalog but never
            # in this code-level list until 2026-07-08 — restored so a
            # fresh database's seed matches what was actually running) + 5
            # Macro Demand Structure indicators (marketmind-core GDP=C+I+G+NX
            # identity) — see SEED_INDICATORS.
            assert len(data["data"]["indicators"]) == 13
        finally:
            app.dependency_overrides.clear()
