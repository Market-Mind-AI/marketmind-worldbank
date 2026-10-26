class WorldBankBaseException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class WorldBankClientError(WorldBankBaseException):
    """A fonte respondeu, e a resposta não serve: um 4xx que não é 404, uma
    recusa do pedido. Repetir não muda a resposta, então não se repete."""

    def __init__(self, message: str = "World Bank API client error"):
        super().__init__(message=message, status_code=502)


class WorldBankTransientError(WorldBankBaseException):
    """A fonte está ocupada ou fora do ar (5xx, 429, timeout, rede) e continuou
    assim depois de todas as tentativas. 503 em todos os coletores: quer dizer
    "tente de novo mais tarde", que é exatamente o que vale fazer."""

    def __init__(self, message: str = "World Bank API transient server error"):
        super().__init__(message=message, status_code=503)


class WorldBankTimeoutError(WorldBankTransientError):
    def __init__(self, message: str = "World Bank API request timed out"):
        super().__init__(message=message)


class WorldBankRateLimitError(WorldBankTransientError):
    def __init__(self, message: str = "World Bank API rate limit exceeded"):
        super().__init__(message=message)


class WorldBankEmptyResponseError(WorldBankBaseException):
    """A fonte disse, de forma definitiva, que não tem o dado. Numa coleta de
    indicadores isso é uma resposta -- conta como verificação -- e não uma
    falha."""

    def __init__(self, message: str = "World Bank API returned empty response"):
        super().__init__(message=message, status_code=404)


class WorldBankParsingError(WorldBankBaseException):
    def __init__(self, message: str = "Failed to parse World Bank API response"):
        super().__init__(message=message, status_code=502)


class IndicatorNotConfiguredError(WorldBankBaseException):
    """O pedido nomeia um indicador que este serviço não sabe coletar. É erro de
    quem pediu, o único caso de 4xx de uma coleta -- e o mesmo 422 nos três
    coletores de indicadores."""

    def __init__(self, message: str = "Indicator not configured for collection"):
        super().__init__(message=message, status_code=422)


class ValidationError(WorldBankBaseException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message=message, status_code=422)
