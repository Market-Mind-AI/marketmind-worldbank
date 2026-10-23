# MarketMind World Bank

Microservice for consuming, normalizing and persisting **World Bank Open Data** via the [World Bank Indicators API](https://api.worldbank.org/v2).

Part of the **MarketMind** ecosystem for the TFM (Trabajo Fin de Máster).

## What this service does

- Discovers countries available in the World Bank API
- Collects indicator metadata (name, source, description)
- Collects time-series observations by country, indicator, and period
- Maintains an internal catalog of MarketMind-relevant indicators
- Normalizes all API responses (types, nulls, encoding)
- Persists raw API responses (JSONB) and normalized data in PostgreSQL
- Provides full audit trail: every call creates an `ingestion_run` and `worldbank_request`
- Exposes stored data, freshness and a stale-refresh pass over REST, with Swagger documentation

## What this service does NOT do

- Does **NOT** calculate MOS (Market Opportunity Score)
- Does **NOT** calculate Rank Order Centroid weights or TOPSIS
- Does **NOT** use LLM
- Does **NOT** know Semantic Layer
- Does **NOT** know final MarketMind rules
- Does **NOT** compute dimensions (Digital Readiness, Macroeconomic Stability, etc.)

It only collects and delivers clean, auditable, normalized economic and digital data.

## Architecture

```
app/
  api/routes/          → FastAPI endpoints (no business logic)
  core/                → config, logging, exceptions
  domain/              → enums, entities
  clients/             → WorldBankClient (httpx + tenacity)
  services/            → WorldBankService (orchestration)
  repositories/        → Data access layer (SQLAlchemy)
  db/models/           → SQLAlchemy ORM models
  schemas/             → Pydantic request/response models
  utils/               → normalization, pagination, time
```

**Flow:** Route → Service → Client + Normalization + Repositories → Database

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Framework | FastAPI |
| Validation | Pydantic v2 |
| HTTP Client | httpx (retries via tenacity) |
| ORM | SQLAlchemy 2.0 (async, asyncpg) |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Package Manager | Poetry |
| Containers | Docker + Docker Compose |
| Linting | Ruff, Black, Mypy |
| Testing | Pytest |

## Running with Docker

### 1. Create `.env` file

```bash
cp .env.example .env
```

### 2. Start all services

```bash
docker compose up --build
```

This starts:
- **API** at `http://localhost:${APP_PORT}` (8003 in `.env.example`; the container always listens on 8000)
- **PostgreSQL 16** at `localhost:${DATABASE_EXTERNAL_PORT}` (5434 in `.env.example`)

Migrations run automatically when the container starts (`alembic upgrade head`).

### 3. Access Swagger

Open `http://localhost:8003/docs`

### pgAdmin

pgAdmin was consolidated into `marketmind-scoring` (single instance pointing at
all 5 services' databases). See `marketmind-scoring/README.md`.

## Running locally (without Docker)

```bash
# Install dependencies
poetry install

# Set environment variables
cp .env.example .env
# Edit .env: set DATABASE_HOST=localhost

# Run migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

| Variable | Default in code | Description |
|----------|-----------------|-------------|
| `APP_NAME` | marketmind-worldbank | Service name |
| `APP_ENV` | local | Environment |
| `APP_PORT` | — | Host port mapped by `docker-compose.yml` only (8003 in `.env.example`); the app itself does not read it |
| `DATABASE_HOST` | localhost | PostgreSQL host (`postgres` in `.env.example`) |
| `DATABASE_PORT` | 5432 | PostgreSQL port |
| `DATABASE_EXTERNAL_PORT` | — | Host port for Postgres in `docker-compose.yml` (5434 in `.env.example`) |
| `DATABASE_NAME` | marketmind_worldbank | Database name |
| `DATABASE_USER` | marketmind | Database user |
| `DATABASE_PASSWORD` | marketmind_password | Database password |
| `DATABASE_SSL_MODE` | disable | `disable`, `require` or `verify-full` (Azure needs at least `require`) |
| `WORLDBANK_BASE_URL` | https://api.worldbank.org/v2 | World Bank API base URL |
| `DEFAULT_FORMAT` | json | Response format |
| `DEFAULT_PER_PAGE` | 1000 | Records per page |
| `DEFAULT_TIMEOUT` | 30 | HTTP timeout (seconds) |
| `DEFAULT_RETRIES` | 5 | Retry attempts (`.env.example` and the deployed environment set 3) |
| `DEFAULT_BACKOFF` | 2 | Exponential backoff multiplier (tenacity, min 2 s, max 60 s) |
| `LOG_LEVEL` | INFO | Log level |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness: is the process up (no DB access) |
| `GET` | `/health` | Readiness: health check with DB status |
| `GET` | `/version` | Service version |
| `POST` | `/countries` | Collect countries from World Bank |
| `POST` | `/indicators/metadata` | Collect indicator metadata |
| `POST` | `/observations` | Collect observations for country/indicator/period |
| `POST` | `/indicators/catalog/seed` | Seed the 13 default MarketMind indicators |
| `POST` | `/indicators/catalog` | Create/update catalog entries |
| `GET` | `/indicators/catalog` | List all catalog entries |
| `POST` | `/indicators/collect` | Collect data for catalog indicators |
| `GET` | `/observations/series` | Read one indicator's stored values for one country (`country_iso2`, `indicator_code`, optional `limit`) |
| `GET` | `/freshness` | What is stored and when it was last checked (`country`, `indicator`, `stale_after_days`, `only_stale`) |
| `POST` | `/maintenance/refresh-stale` | Collect again every country whose last check is older than `stale_after_days` (default 30); `limit`, `fail_if_incomplete` |
| `GET` | `/requests/{id}` | Get request details |
| `GET` | `/runs/{id}` | Get ingestion run details |

Consumers (e.g. `marketmind-scoring`) read this service over HTTP (`/observations/series`,
`/freshness`); they do not connect to its database.

## Usage Examples

### Health check

```bash
curl http://localhost:8003/health
```

### Collect countries

```bash
curl -X POST http://localhost:8003/countries \
  -H "Content-Type: application/json" \
  -d '{"per_page": 1000}'
```

### Seed the indicator catalog

```bash
curl -X POST http://localhost:8003/indicators/catalog/seed
```

### Collect indicator metadata

```bash
curl -X POST http://localhost:8003/indicators/metadata \
  -H "Content-Type: application/json" \
  -d '{"indicator_code": "NY.GDP.PCAP.CD"}'
```

### Collect observations

```bash
curl -X POST http://localhost:8003/observations \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "indicator_code": "NY.GDP.PCAP.CD",
    "start_year": 2018,
    "end_year": 2026
  }'
```

### Collect all catalog indicators for a country

```bash
curl -X POST http://localhost:8003/indicators/collect \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "start_year": 2018,
    "end_year": 2026
  }'
```

### Collect specific indicators

```bash
curl -X POST http://localhost:8003/indicators/collect \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "start_year": 2018,
    "end_year": 2026,
    "indicator_codes": ["NY.GDP.PCAP.CD", "IT.NET.USER.ZS"]
  }'
```

### Read a stored series

```bash
curl "http://localhost:8003/observations/series?country_iso2=ES&indicator_code=NY.GDP.PCAP.CD&limit=3"
```

### Check freshness and refresh what is stale

```bash
curl "http://localhost:8003/freshness?country=ESP&stale_after_days=30&only_stale=true"

curl -X POST http://localhost:8003/maintenance/refresh-stale \
  -H "Content-Type: application/json" \
  -d '{"stale_after_days": 30, "fail_if_incomplete": true}'
```

## Default MarketMind Indicators

The 13 indicators seeded by `POST /indicators/catalog/seed` (`SEED_INDICATORS` in `app/services/worldbank_service.py`):

| Code | Name | Dimension |
|------|------|-----------|
| `NY.GDP.PCAP.CD` | GDP per capita (current US$) | macroeconomic_stability |
| `NY.GDP.MKTP.KD.ZG` | GDP growth (annual %) | macroeconomic_stability |
| `FP.CPI.TOTL.ZG` | Inflation, consumer prices (annual %) | macroeconomic_stability |
| `IT.NET.USER.ZS` | Individuals using the Internet (% of population) | digital_readiness |
| `IT.CEL.SETS.P2` | Mobile cellular subscriptions (per 100 people) | digital_readiness |
| `IT.NET.BBND.P2` | Fixed broadband subscriptions (per 100 people) | digital_readiness |
| `SP.POP.TOTL` | Population, total | market_population_potential |
| `SP.URB.TOTL.IN.ZS` | Urban population (% of total population) | urban_consumption_potential |
| `NE.CON.PRVT.ZS` | Households and NPISHs final consumption expenditure (% of GDP) | macro_demand_structure |
| `NE.CON.GOVT.ZS` | General government final consumption expenditure (% of GDP) | macro_demand_structure |
| `NE.GDI.FTOT.ZS` | Gross fixed capital formation (% of GDP) | macro_demand_structure |
| `NE.RSB.GNFS.ZS` | External balance on goods and services (% of GDP) | macro_demand_structure |
| `NE.TRD.GNFS.ZS` | Trade (% of GDP) | macro_demand_structure |

## Database Tables

| Table | Purpose |
|-------|---------|
| `ingestion_runs` | Tracks each ingestion execution |
| `worldbank_requests` | Each API call made to World Bank |
| `raw_api_responses` | Raw JSON responses (JSONB) |
| `worldbank_countries` | Normalized country data |
| `worldbank_indicators_catalog` | Internal indicator registry |
| `worldbank_observations` | Normalized time-series observations |

Migration `002_create_readonly_role` creates a `marketmind_readonly` Postgres role. It is
legacy: it dates from when `marketmind-scoring` read this database directly. Collectors are
now read over HTTP, so nothing uses the role; the migration is kept only so existing
databases keep a linear revision history (technical debt).

## Running Tests

```bash
# Install dev dependencies
poetry install

# Run tests (unit tests, all external calls mocked)
pytest
```

## Running Migrations

```bash
# Apply all migrations
alembic upgrade head

# Check current revision
alembic current

# Generate new migration (after model changes)
alembic revision --autogenerate -m "description"
```

## Code Quality

```bash
ruff check .
black .
mypy .
```

## World Bank API Limitations

- **Rate limiting**: The World Bank API may throttle requests. The client retries timeouts, 429 and 5xx with exponential backoff (tenacity: `DEFAULT_RETRIES` attempts, multiplier `DEFAULT_BACKOFF`, wait between 2 s and 60 s). 4xx errors other than 429 are not retried.
- **Data availability**: Not all indicators have data for all countries or years. Null values are preserved.
- **Response format**: The API returns a two-element array `[metadata, data]`. The client handles this defensively.
- **Pagination**: Large result sets are paginated. The client automatically fetches all pages.
- **Eventual consistency**: Data may be updated or revised by the World Bank at any time.
- **Partial failures**: a `/indicators/collect` run is marked `failed` only when every requested indicator failed; otherwise it succeeds and lists the indicators that failed.

## Rate Limit Best Practices

- Use `per_page=1000` to minimize the number of requests
- Avoid parallel bulk collection of many indicators simultaneously
- Use `/indicators/collect` which collects sequentially with proper error handling
- Use `/freshness` and `/maintenance/refresh-stale` instead of re-collecting everything on a schedule
- Monitor `ingestion_runs` for failed status to detect persistent issues

## Team

Final project (TFM) for the *Máster en Ingeniería y Desarrollo de Soluciones de IA Generativa* — **EBIS Business Techschool**. The whole system and how to run it: [marketmind-ai](https://github.com/Market-Mind-AI/marketmind-ai).

- **Miguel Antonio Blanco Salcedo** — [@mikews93](https://github.com/mikews93)
- **Álvaro Augusto De Marco Neto** — [@ironeto](https://github.com/ironeto)
