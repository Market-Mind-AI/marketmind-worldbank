"""O que uma coleta de indicadores responde, e o que ela conta como verificação.

As regras são as mesmas nos três coletores de indicadores."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import (
    IndicatorNotConfiguredError,
    WorldBankClientError,
    WorldBankEmptyResponseError,
    WorldBankTimeoutError,
    WorldBankTransientError,
)
from app.schemas.requests import IndicatorCollectRequest
from app.services.worldbank_service import WorldBankService

_GDP = "NY.GDP.PCAP.CD"
_POP = "SP.POP.TOTL"


def _service(mock_session: AsyncMock, *outcomes: object, codes: tuple[str, ...] = (_GDP, _POP)) -> WorldBankService:
    service = WorldBankService(mock_session)
    service._indicator_repo.get_by_codes = AsyncMock(
        return_value=[SimpleNamespace(indicator_code=code) for code in codes]
    )
    service._ingestion_repo = MagicMock(create=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    service._ingestion_repo.mark_success = AsyncMock()
    service._ingestion_repo.mark_failed = AsyncMock()
    service._request_repo = MagicMock(create=AsyncMock(side_effect=lambda **kw: SimpleNamespace(id=uuid.uuid4(), **kw)))
    service._raw_response_repo = MagicMock(bulk_create=AsyncMock())
    service._observation_repo = MagicMock(replace_periods=AsyncMock())
    service._client = MagicMock(get_observations=AsyncMock(side_effect=list(outcomes)))
    return service


def _request(*codes: str) -> IndicatorCollectRequest:
    return IndicatorCollectRequest(country="ESP", start_year=2016, end_year=2026, indicator_codes=list(codes))


def _checks(service: WorldBankService) -> list[str]:
    return [
        call.kwargs["indicator_code"]
        for call in service._request_repo.create.await_args_list
        if call.kwargs.get("indicator_code")
    ]


async def test_the_source_being_down_for_every_indicator_is_a_503(mock_session: AsyncMock) -> None:
    """Era um 200 com a execução marcada como falha por dentro, e a manutenção
    diária contava a queda como país renovado."""
    service = _service(mock_session, WorldBankTransientError("502"), WorldBankTimeoutError("timeout"))

    with pytest.raises(WorldBankTransientError) as raised:
        await service.collect_indicators(_request(_GDP, _POP))

    assert raised.value.status_code == 503
    service._ingestion_repo.mark_failed.assert_awaited_once()
    assert _checks(service) == []


async def test_nothing_collected_for_another_reason_is_a_502(mock_session: AsyncMock) -> None:
    service = _service(mock_session, WorldBankTransientError("502"), WorldBankClientError("400"))

    with pytest.raises(WorldBankClientError) as raised:
        await service.collect_indicators(_request(_GDP, _POP))

    assert raised.value.status_code == 502


async def test_an_unknown_indicator_is_a_422_before_anything_is_collected(mock_session: AsyncMock) -> None:
    service = _service(mock_session, codes=(_GDP,))

    with pytest.raises(IndicatorNotConfiguredError) as raised:
        await service.collect_indicators(_request(_GDP, "NOT.A.CODE"))

    assert raised.value.status_code == 422
    service._client.get_observations.assert_not_awaited()
    service._ingestion_repo.create.assert_not_awaited()


async def test_the_source_having_no_data_is_an_answer_and_a_check(mock_session: AsyncMock) -> None:
    """"Não tenho" é resposta definitiva: conta como verificação, e o par não é
    recoletado toda noite."""
    service = _service(mock_session, WorldBankEmptyResponseError("404"), codes=(_GDP,))

    response = await service.collect_indicators(_request(_GDP))

    assert response.metadata.status == "success"
    assert response.data.indicators_failed == []
    assert _checks(service) == [_GDP]


async def test_only_the_indicators_that_got_an_answer_are_checks(mock_session: AsyncMock) -> None:
    """Um código que falhou não ganha linha de verificação -- antes ele ficava
    "fresco" por 90 dias sem nunca ter sido respondido."""
    service = _service(mock_session, ([], [], "url"), WorldBankTransientError("502"))

    response = await service.collect_indicators(_request(_GDP, _POP))

    assert _checks(service) == [_GDP]
    assert response.data.indicators_failed == [_POP]
    service._ingestion_repo.mark_success.assert_awaited_once()
