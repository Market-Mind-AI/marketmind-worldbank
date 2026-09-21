from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.worldbank_service import WorldBankService

_GDP = "NY.GDP.PCAP.CD"


def _observation(year: int, value: str) -> SimpleNamespace:
    return SimpleNamespace(year=year, value=Decimal(value), unit="current US$", obs_status=None)


def _service(mock_session: AsyncMock, rows: list) -> WorldBankService:
    service = WorldBankService(mock_session)
    service._observation_repo.series = AsyncMock(return_value=rows)
    return service


async def test_returns_the_points_newest_first(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [_observation(2024, "34500.5"), _observation(2023, "33100.0")])

    response = await service.get_series(country_iso2="ES", indicator_code=_GDP)

    assert [(p.year, p.value) for p in response.data.points] == [
        (2024, Decimal("34500.5")),
        (2023, Decimal("33100.0")),
    ]


async def test_it_returns_rows_rather_than_doing_the_arithmetic(mock_session: AsyncMock) -> None:
    """Averaging the last three years is Cap. 4 method and is versioned there.
    If this service averaged, the method would live in two places at once."""
    service = _service(mock_session, [_observation(2024, "3.0"), _observation(2023, "1.0")])

    response = await service.get_series(country_iso2="ES", indicator_code=_GDP, limit=3)

    assert len(response.data.points) == 2
    assert all(hasattr(p, "year") for p in response.data.points)


async def test_the_limit_is_passed_through(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [])

    await service.get_series(country_iso2="ES", indicator_code=_GDP, limit=3)

    assert service._observation_repo.series.await_args.kwargs["limit"] == 3


async def test_a_country_with_nothing_stored_returns_an_empty_series(mock_session: AsyncMock) -> None:
    """Empty is an answer, not an error: the caller decides whether that means
    "collect it" or "this source has nothing", using /freshness."""
    service = _service(mock_session, [])

    response = await service.get_series(country_iso2="PE", indicator_code=_GDP)

    assert response.data.points == []
    assert response.data.country_iso2 == "PE"


async def test_the_country_code_is_normalised(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [])

    response = await service.get_series(country_iso2=" es ", indicator_code=f" {_GDP} ")

    assert response.data.country_iso2 == "ES"
    assert response.data.indicator_code == _GDP
    assert service._observation_repo.series.await_args.kwargs["country_iso2"] == "ES"
