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


class IndicatorCategory(StrEnum):
    GDP_PER_CAPITA = "gdp_per_capita"
    GDP_GROWTH = "gdp_growth"
    INTERNET_USERS = "internet_users"
    POPULATION_TOTAL = "population_total"
    URBAN_POPULATION = "urban_population"
    MOBILE_SUBSCRIPTIONS = "mobile_subscriptions"
    BROADBAND_SUBSCRIPTIONS = "broadband_subscriptions"


class MarketMindDimension(StrEnum):
    MACROECONOMIC_STABILITY = "macroeconomic_stability"
    DIGITAL_READINESS = "digital_readiness"
    MARKET_POPULATION_POTENTIAL = "market_population_potential"
    URBAN_CONSUMPTION_POTENTIAL = "urban_consumption_potential"
