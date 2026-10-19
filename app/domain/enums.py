from enum import StrEnum


class IngestionStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class WorldBankEndpoint(StrEnum):
    COUNTRIES = "countries"
    INDICATOR_METADATA = "indicator_metadata"
    OBSERVATIONS = "observations"
    INDICATORS_CATALOG = "indicators_catalog"
    INDICATORS_CATALOG_SEED = "indicators_catalog_seed"
    INDICATORS_COLLECT = "indicators_collect"
