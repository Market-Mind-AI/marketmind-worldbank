from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.repositories.freshness_repository import ObservationFacts
from app.services.worldbank_service import WorldBankService
from app.utils.time import utc_now

_GDP = "NY.GDP.MKTP.CD"
_POP = "SP.POP.TOTL"


def _service(
    mock_session: AsyncMock,
    *,
    checks: dict | None = None,
    observed: dict | None = None,
) -> WorldBankService:
    service = WorldBankService(mock_session)
    service._freshness_repo.last_checks = AsyncMock(return_value=checks or {})
    service._freshness_repo.observation_facts = AsyncMock(return_value=observed or {})
    return service


async def test_a_recent_check_is_not_stale(mock_session: AsyncMock) -> None:
    yesterday = utc_now() - timedelta(days=1)
    service = _service(mock_session, checks={("ESP", _GDP): yesterday})

    response = await service.get_freshness(countries=["ESP"], indicators=[_GDP])

    assert [(i.country, i.stale) for i in response.data.items] == [("ESP", False)]
    assert response.data.items[0].last_checked_at == yesterday


async def test_an_old_check_is_stale(mock_session: AsyncMock) -> None:
    service = _service(mock_session, checks={("ESP", _GDP): utc_now() - timedelta(days=31)})

    response = await service.get_freshness(countries=["ESP"], indicators=[_GDP])

    assert response.data.items[0].stale is True


async def test_yearly_data_is_not_stale_just_because_the_value_is_old(mock_session: AsyncMock) -> None:
    """The whole point of measuring the check and not the datum: World Bank GDP
    for 2024 is the current value, and a rule written against the year would
    re-fetch it every day of 2026."""
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now() - timedelta(days=2)},
        observed={
            ("ESP", _GDP): ObservationFacts(
                last_observation_at=utc_now() - timedelta(days=2), latest_year=2024, observation_count=60
            )
        },
    )

    response = await service.get_freshness(countries=["ESP"], indicators=[_GDP])

    assert response.data.items[0].latest_year == 2024
    assert response.data.items[0].stale is False


async def test_a_pair_never_checked_is_reported_rather_than_omitted(mock_session: AsyncMock) -> None:
    """Asking about a specific pair must never answer with an empty list --
    the caller cannot tell that apart from "everything is fresh"."""
    service = _service(mock_session)

    response = await service.get_freshness(countries=["PER"], indicators=[_GDP])

    assert len(response.data.items) == 1
    item = response.data.items[0]
    assert item.last_checked_at is None
    assert item.observation_count == 0
    assert item.stale is True


async def test_a_check_that_returned_nothing_still_counts_as_checked(mock_session: AsyncMock) -> None:
    """The source having no data for a country is not the same as never having
    tried. Without this the pair would be re-fetched every single day."""
    service = _service(mock_session, checks={("PER", _GDP): utc_now() - timedelta(days=3)})

    response = await service.get_freshness(countries=["PER"], indicators=[_GDP])

    item = response.data.items[0]
    assert item.observation_count == 0
    assert item.last_observation_at is None
    assert item.stale is False


async def test_only_stale_filters_out_what_is_fresh(mock_session: AsyncMock) -> None:
    service = _service(
        mock_session,
        checks={
            ("ESP", _GDP): utc_now() - timedelta(days=1),
            ("ESP", _POP): utc_now() - timedelta(days=90),
        },
    )

    response = await service.get_freshness(countries=["ESP"], indicators=[_GDP, _POP], only_stale=True)

    assert [i.indicator_code for i in response.data.items] == [_POP]


async def test_country_codes_are_normalised(mock_session: AsyncMock) -> None:
    service = _service(mock_session, checks={("ESP", _GDP): utc_now()})

    response = await service.get_freshness(countries=[" esp "], indicators=[_GDP])

    assert response.data.items[0].country == "ESP"
    assert response.data.items[0].stale is False


async def test_without_both_filters_it_lists_what_it_knows(mock_session: AsyncMock) -> None:
    service = _service(
        mock_session,
        checks={("ESP", _GDP): utc_now(), ("BRA", _POP): utc_now()},
    )

    response = await service.get_freshness()

    assert {(i.country, i.indicator_code) for i in response.data.items} == {("ESP", _GDP), ("BRA", _POP)}


async def test_the_threshold_is_configurable(mock_session: AsyncMock) -> None:
    service = _service(mock_session, checks={("ESP", _GDP): utc_now() - timedelta(days=10)})

    fresh = await service.get_freshness(countries=["ESP"], indicators=[_GDP], stale_after_days=30)
    stale = await service.get_freshness(countries=["ESP"], indicators=[_GDP], stale_after_days=7)

    assert fresh.data.items[0].stale is False
    assert stale.data.items[0].stale is True
    assert stale.data.stale_after_days == 7


async def test_a_check_read_back_as_aware_is_compared_not_crashed(mock_session: AsyncMock) -> None:
    # worldbank_requests.created_at is `timestamp with time zone`, so the driver
    # hands the value back aware while utc_now() is naive. Comparing the two
    # raises TypeError — the same defect that made the OECD service answer 500
    # for every country it had already fetched.
    aware = datetime.now(UTC) - timedelta(days=1)
    service = _service(mock_session, checks={("MEX", _GDP): aware})

    response = await service.get_freshness(countries=["MEX"], indicators=[_GDP])

    assert response.data.items[0].stale is False


async def test_an_old_aware_check_is_stale(mock_session: AsyncMock) -> None:
    aware = datetime.now(UTC) - timedelta(days=31)
    service = _service(mock_session, checks={("MEX", _GDP): aware})

    response = await service.get_freshness(countries=["MEX"], indicators=[_GDP])

    assert response.data.items[0].stale is True
