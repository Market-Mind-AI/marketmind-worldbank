"""One value per year: drop the copies that repeated collections left behind

Até 26/10/2026 cada coleta só acrescentava observações, e um ano coletado duas
vezes ficava guardado duas vezes -- a leitura com `limit=3` devolvia
[2025, 2025, 2024]. A coleta agora substitui os anos que traz
(`replace_periods`), e esta migração limpa o que ficou de antes, com a mesma
regra: para cada (país, indicador, ano) fica a coleta mais recente.

O índice cobre a série como ela é lida e substituída: país, indicador, ano.

Revision ID: 003
Revises: 002
Create Date: 2026-10-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM worldbank_observations AS antiga
        USING worldbank_observations AS nova
        WHERE nova.country_iso2 IS NOT DISTINCT FROM antiga.country_iso2
          AND nova.indicator_code = antiga.indicator_code
          AND nova.year = antiga.year
          AND nova.created_at > antiga.created_at
        """
    )
    op.create_index(
        "ix_worldbank_observations_series",
        "worldbank_observations",
        ["country_iso2", "indicator_code", "year"],
    )


def downgrade() -> None:
    # As cópias apagadas não voltam: eram o mesmo ano guardado de novo.
    op.drop_index("ix_worldbank_observations_series", table_name="worldbank_observations")
