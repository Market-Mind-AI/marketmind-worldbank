from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.requests import RefreshStaleRequest
from app.services.worldbank_service import WorldBankService
from app.utils.time import utc_now

_GDP = "NY.GDP.PCAP.CD"


def _service(
    mock_session: AsyncMock,
    *,
    checks: dict | None = None,
    payloads: dict | None = None,
) -> WorldBankService:
    service = WorldBankService(mock_session)
    service._freshness_repo.last_checks = AsyncMock(return_value=checks or {})
    service._freshness_repo.observation_facts = AsyncMock(return_value={})
    service._ingestion_repo.last_collect_setup_by_country = AsyncMock(return_value=payloads or {})
    service.collect_indicators = AsyncMock(return_value=_collected())
    return service


def _collected(failed: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(data=SimpleNamespace(indicators_failed=failed or []))


def _payload(country: str, indicators: list[str] | None = None) -> dict:
    return {"country": country, "start_year": 2015, "end_year": 2020, "indicator_codes": indicators or [_GDP]}


async def test_a_stale_country_is_collected_again(mock_session: AsyncMock) -> None:
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=91)},
        payloads={"ESP": _payload("ESP")},
    )

    response = await service.refresh_stale(RefreshStaleRequest())

    assert response.data.refreshed == 1
    service.collect_indicators.assert_awaited_once()


async def test_a_fresh_country_is_left_alone(mock_session: AsyncMock) -> None:
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=2)},
        payloads={"ESP": _payload("ESP")},
    )

    response = await service.refresh_stale(RefreshStaleRequest())

    assert response.data.stale_countries == 0
    service.collect_indicators.assert_not_awaited()


async def test_the_window_moves_to_now(mock_session: AsyncMock) -> None:
    """The stored request is replayed, not repeated: collecting 2015-2020 again
    every day would keep re-fetching a window that already ended."""
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=91)},
        payloads={"ESP": _payload("ESP")},
    )

    await service.refresh_stale(RefreshStaleRequest(years_back=5))

    sent = service.collect_indicators.await_args.args[0]
    assert sent.end_year == utc_now().year
    assert sent.start_year == utc_now().year - 5


async def test_the_default_window_is_the_one_the_core_asks_for(mock_session: AsyncMock) -> None:
    """O Core coleta de dez anos atrás até este ano; a renovação noturna pede o
    mesmo, para não guardar uma série mais curta que a da primeira coleta."""
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=91)},
        payloads={"ESP": _payload("ESP")},
    )

    await service.refresh_stale(RefreshStaleRequest())

    sent = service.collect_indicators.await_args.args[0]
    assert (sent.start_year, sent.end_year) == (utc_now().year - 10, utc_now().year)


async def test_a_country_with_an_indicator_left_behind_counts_as_failed(mock_session: AsyncMock) -> None:
    """Renovado só quando todo indicador teve resposta. Uma queda parcial da
    fonte passava como noite boa, e `fail_if_incomplete` nunca a acusava."""
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=91)},
        payloads={"ESP": _payload("ESP", [_GDP, "SP.POP.TOTL"])},
    )
    service.collect_indicators = AsyncMock(return_value=_collected(["SP.POP.TOTL"]))

    response = await service.refresh_stale(RefreshStaleRequest())

    assert (response.data.refreshed, response.data.failed) == (0, 1)
    assert "SP.POP.TOTL" in response.data.countries[0].detail


async def test_the_indicators_come_from_the_stored_request(mock_session: AsyncMock) -> None:
    """Whatever a caller once set up for a country keeps working, without this
    service having to know which indicators that country was configured with."""
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=91)},
        payloads={"ESP": _payload("ESP", ["NY.GDP.MKTP.CD", "SP.POP.TOTL"])},
    )

    await service.refresh_stale(RefreshStaleRequest())

    sent = service.collect_indicators.await_args.args[0]
    assert sent.indicator_codes == ["NY.GDP.MKTP.CD", "SP.POP.TOTL"]


async def test_a_country_never_collected_is_skipped_not_invented(mock_session: AsyncMock) -> None:
    """Nothing to replay means no idea what to ask for. It arrives through the
    on-demand path the first time instead."""
    service = _service(mock_session, checks={("PER", _GDP): utc_now() - timedelta(days=91)}, payloads={})

    response = await service.refresh_stale(RefreshStaleRequest())

    assert response.data.skipped == 1
    assert response.data.refreshed == 0
    assert response.data.countries[0].outcome == "skipped"
    service.collect_indicators.assert_not_awaited()


async def test_the_pass_is_bounded(mock_session: AsyncMock) -> None:
    """A first run against a long-idle database finds everything stale at once,
    and the upstream API has its own patience."""
    old = utc_now() - timedelta(days=91)
    countries = ["ESP", "BRA", "USA", "DEU", "JPN"]
    service = _service(
        mock_session,
        checks={(c, _GDP): old for c in countries},
        payloads={c: _payload(c) for c in countries},
    )

    response = await service.refresh_stale(RefreshStaleRequest(limit=2))

    assert response.data.stale_countries == 5
    assert response.data.attempted == 2
    assert service.collect_indicators.await_count == 2


async def test_one_country_failing_does_not_end_the_pass(mock_session: AsyncMock) -> None:
    old = utc_now() - timedelta(days=91)
    service = _service(
        mock_session,
        checks={("ESP", _GDP): old, ("BRA", _GDP): old},
        payloads={"ESP": _payload("ESP"), "BRA": _payload("BRA")},
    )
    service.collect_indicators = AsyncMock(side_effect=[RuntimeError("upstream down"), _collected()])

    response = await service.refresh_stale(RefreshStaleRequest())

    assert response.data.failed == 1
    assert response.data.refreshed == 1
    assert "upstream down" in [c.detail for c in response.data.countries if c.outcome == "failed"][0]


def test_no_limit_means_every_stale_country(mock_session) -> None:
    """Um teto de 10 contra 24 países não limpava nem o atraso de uma noite:
    sobravam 14, que na noite seguinte disputavam as mesmas 10 vagas com os que
    tinham acabado de vencer. O padrão agora é sem teto."""
    pedido = RefreshStaleRequest()

    assert pedido.limit is None


def test_a_pass_that_left_countries_behind_can_refuse() -> None:
    """O CronJob chama com `curl --fail`, então um 503 sai diferente de zero: o
    Kubernetes retenta e o que não se resolve fica como Job `Failed`. Sem isso,
    `failed` era só um campo dentro de um 200 — uma noite em que TODOS os países
    falharam terminava com o CronJob anotando lastSuccessfulTime."""
    from types import SimpleNamespace

    import pytest
    from fastapi import HTTPException

    from app.api.routes.worldbank import _refuse_if_incomplete

    resposta = SimpleNamespace(data=SimpleNamespace(failed=3))

    with pytest.raises(HTTPException) as erro:
        _refuse_if_incomplete(resposta, RefreshStaleRequest(fail_if_incomplete=True))
    assert erro.value.status_code == 503

    # Sem pedir, a chamada manual continua recebendo o relatório parcial.
    _refuse_if_incomplete(resposta, RefreshStaleRequest())


def test_a_complete_pass_never_refuses() -> None:
    from types import SimpleNamespace

    from app.api.routes.worldbank import _refuse_if_incomplete

    completa = SimpleNamespace(data=SimpleNamespace(failed=0))
    _refuse_if_incomplete(completa, RefreshStaleRequest(fail_if_incomplete=True))


async def test_the_replay_gathers_every_indicator_from_every_run(mock_session: AsyncMock) -> None:
    """O Core pede um indicador por coleta. Replicar só o pedido mais recente
    renovava um indicador por país por noite; os outros ficavam vencidos."""
    from app.repositories.ingestion_run_repository import IngestionRunRepository

    linhas = [
        ("ESP", {"country": "ESP", "indicator_codes": [_GDP]}),
        ("ESP", {"country": "ESP", "indicator_codes": ["SP.POP.TOTL"]}),
        ("ESP", {"country": "ESP", "indicator_codes": [_GDP]}),
        ("BRA", {"country": "BRA", "indicator_codes": None}),
    ]
    mock_session.execute = AsyncMock(return_value=SimpleNamespace(all=lambda: linhas))

    setups = await IngestionRunRepository(mock_session).last_collect_setup_by_country()

    assert setups["ESP"]["indicator_codes"] == [_GDP, "SP.POP.TOTL"]
    assert setups["BRA"]["indicator_codes"] == []
