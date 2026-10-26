"""Uma linha por período na leitura, e a coleta nova substituindo a velha na escrita."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.repositories.worldbank_observation_repository import WorldBankObservationRepository


def _sql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


async def test_the_series_holds_one_value_per_year_from_the_latest_collection(mock_session: AsyncMock) -> None:
    """Depois de uma segunda coleta, `limit=3` devolvia [2025, 2025, 2024] e a
    média de três anos do Core saía errada."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)

    await WorldBankObservationRepository(mock_session).series(country_iso2="ES", indicator_code="X", limit=3)

    sql = _sql(mock_session.execute.call_args.args[0])
    assert "DISTINCT ON (worldbank_observations.year)" in sql
    assert (
        "ORDER BY worldbank_observations.year DESC, worldbank_observations.created_at DESC, "
        "worldbank_observations.value DESC" in sql
    )


async def test_a_new_collection_replaces_the_years_it_brings(mock_session: AsyncMock) -> None:
    observations = [
        {"country": "ESP", "country_iso2": "ES", "indicator_code": "X", "year": 2025, "value": 1},
        {"country": "ESP", "country_iso2": "ES", "indicator_code": "X", "year": 2024, "value": 2},
    ]

    await WorldBankObservationRepository(mock_session).replace_periods(
        worldbank_request_id="req",  # type: ignore[arg-type]
        observations=observations,
    )

    sql = _sql(mock_session.execute.call_args.args[0])
    assert sql.startswith("DELETE FROM worldbank_observations")
    assert "worldbank_observations.year IN (2024, 2025)" in sql
