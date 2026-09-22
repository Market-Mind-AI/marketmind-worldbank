from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def as_naive_utc(moment: datetime | None) -> datetime | None:
    """Um instante comparável com `utc_now()`.

    Este serviço trata datetime sem fuso como UTC — é o que `utc_now()` devolve.
    Mas a coluna `worldbank_requests.created_at` é `timestamp with time zone` e
    volta COM fuso, e comparar um com o outro é `TypeError: can't compare
    offset-naive and offset-aware datetimes`.

    Ficou latente por muito tempo: a consulta de frescor exigia `indicator_code`
    preenchido, nenhuma linha atendia, e o laço que compara nunca rodava. No dia
    em que a consulta passou a devolver linhas, o /freshness inteiro começou a
    responder 500 — o mesmo defeito que derrubou o serviço da OCDE, escondido
    atrás de outro.
    """
    if moment is None:
        return None
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo is not None else moment


def elapsed_ms(start: datetime) -> int:
    delta = utc_now() - start
    return int(delta.total_seconds() * 1000)
