import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.worldbank_request_repository import WorldBankRequestRepository


class TestIngestionRunRepository:
    @pytest.fixture
    def repo(self, mock_session: AsyncMock) -> IngestionRunRepository:
        return IngestionRunRepository(mock_session)

    @pytest.mark.asyncio
    async def test_create(self, repo: IngestionRunRepository, mock_session: AsyncMock) -> None:
        run = await repo.create(source="worldbank", request_payload={"test": True})
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert run.source == "worldbank"
        assert run.status == "running"
        assert run.request_payload == {"test": True}

    @pytest.mark.asyncio
    async def test_mark_success(self, repo: IngestionRunRepository, mock_session: AsyncMock) -> None:
        run = await repo.create(source="worldbank", request_payload={})
        result = await repo.mark_success(run, execution_time_ms=500)
        assert result.status == "success"
        assert result.execution_time_ms == 500
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_mark_failed(self, repo: IngestionRunRepository, mock_session: AsyncMock) -> None:
        run = await repo.create(source="worldbank", request_payload={})
        result = await repo.mark_failed(run, execution_time_ms=100, error_message="test error")
        assert result.status == "failed"
        assert result.error_message == "test error"


class TestWorldBankRequestRepository:
    @pytest.fixture
    def repo(self, mock_session: AsyncMock) -> WorldBankRequestRepository:
        return WorldBankRequestRepository(mock_session)

    @pytest.mark.asyncio
    async def test_create(self, repo: WorldBankRequestRepository, mock_session: AsyncMock) -> None:
        run_id = uuid.uuid4()
        request = await repo.create(
            ingestion_run_id=run_id,
            endpoint="countries",
            url="https://api.worldbank.org/v2/country",
            country="ES",
        )
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()
        assert request.endpoint == "countries"
        assert request.country == "ES"
        assert request.ingestion_run_id == run_id
