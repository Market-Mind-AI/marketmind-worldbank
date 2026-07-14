class WorldBankBaseException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class WorldBankClientError(WorldBankBaseException):
    def __init__(self, message: str = "World Bank API client error"):
        super().__init__(message=message, status_code=502)


class WorldBankTimeoutError(WorldBankBaseException):
    def __init__(self, message: str = "World Bank API request timed out"):
        super().__init__(message=message, status_code=504)


class WorldBankRateLimitError(WorldBankBaseException):
    def __init__(self, message: str = "World Bank API rate limit exceeded"):
        super().__init__(message=message, status_code=429)


class WorldBankTransientError(WorldBankBaseException):
    """A transient upstream failure (HTTP 5xx) worth retrying — the World Bank
    public API returns intermittent 502/503/504 under load. Distinct from
    WorldBankClientError (non-retryable, e.g. 4xx) so the retry decorator can
    back off and try again instead of failing the whole collection on a blip."""

    def __init__(self, message: str = "World Bank API transient server error"):
        super().__init__(message=message, status_code=503)


class WorldBankEmptyResponseError(WorldBankBaseException):
    def __init__(self, message: str = "World Bank API returned empty response"):
        super().__init__(message=message, status_code=404)


class WorldBankParsingError(WorldBankBaseException):
    def __init__(self, message: str = "Failed to parse World Bank API response"):
        super().__init__(message=message, status_code=502)


class ValidationError(WorldBankBaseException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message=message, status_code=422)


class IngestionError(WorldBankBaseException):
    def __init__(self, message: str = "Ingestion error"):
        super().__init__(message=message, status_code=500)


class DatabaseError(WorldBankBaseException):
    def __init__(self, message: str = "Database error"):
        super().__init__(message=message, status_code=500)
