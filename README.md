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
- Exposes all data via REST API with Swagger documentation

## What this service does NOT do

- Does **NOT** calculate MOS (Market Opportunity Score)
- Does **NOT** calculate Entropy Weight
- Does **NOT** calculate TOPSIS
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
  clients/             → WorldBankClient (httpx)
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
| HTTP Client | httpx |
| Data Processing | Pandas |
| ORM | SQLAlchemy 2.x (async) |
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
- **API** at [http://localhost:8000](http://localhost:8000)
- **PostgreSQL 16** at `localhost:5432`

### 3. Run database migrations

```bash
docker compose exec marketmind-worldbank-api alembic upgrade head
```

### 4. Access Swagger

Open [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Access pgAdmin

pgAdmin was consolidated into `marketmind-core` (single instance pointing at
all 5 services' databases). See `marketmind-core/README.md`.

The server connection is pre-configured.

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

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | marketmind-worldbank | Service name |
| `APP_ENV` | local | Environment |
| `APP_PORT` | 8000 | API port |
| `DATABASE_HOST` | postgres | PostgreSQL host |
| `DATABASE_PORT` | 5432 | PostgreSQL port |
| `DATABASE_NAME` | marketmind_worldbank | Database name |
| `DATABASE_USER` | marketmind | Database user |
| `DATABASE_PASSWORD` | marketmind_password | Database password |
| `WORLDBANK_BASE_URL` | https://api.worldbank.org/v2 | World Bank API base URL |
| `DEFAULT_FORMAT` | json | Response format |
| `DEFAULT_PER_PAGE` | 1000 | Records per page |
| `DEFAULT_TIMEOUT` | 30 | HTTP timeout (seconds) |
| `DEFAULT_RETRIES` | 3 | Retry attempts |
| `DEFAULT_BACKOFF` | 2 | Backoff multiplier |
| `LOG_LEVEL` | INFO | Log level |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check with DB status |
| `GET` | `/version` | Service version |
| `POST` | `/countries` | Collect countries from World Bank |
| `POST` | `/indicators/metadata` | Collect indicator metadata |
| `POST` | `/observations` | Collect observations for country/indicator/period |
| `POST` | `/indicators/catalog/seed` | Seed default MarketMind indicators |
| `POST` | `/indicators/catalog` | Create/update catalog entries |
| `GET` | `/indicators/catalog` | List all catalog entries |
| `POST` | `/indicators/collect` | Collect data for catalog indicators |
| `GET` | `/requests/{id}` | Get request details |
| `GET` | `/runs/{id}` | Get ingestion run details |

## Usage Examples

### Health check

```bash
curl http://localhost:8000/health
```

### Collect countries

```bash
curl -X POST http://localhost:8000/countries \
  -H "Content-Type: application/json" \
  -d '{"per_page": 1000}'
```

### Seed the indicator catalog

```bash
curl -X POST http://localhost:8000/indicators/catalog/seed
```

### Collect indicator metadata

```bash
curl -X POST http://localhost:8000/indicators/metadata \
  -H "Content-Type: application/json" \
  -d '{"indicator_code": "NY.GDP.PCAP.CD"}'
```

### Collect observations

```bash
curl -X POST http://localhost:8000/observations \
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
curl -X POST http://localhost:8000/indicators/collect \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "start_year": 2018,
    "end_year": 2026
  }'
```

### Collect specific indicators

```bash
curl -X POST http://localhost:8000/indicators/collect \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "start_year": 2018,
    "end_year": 2026,
    "indicator_codes": ["NY.GDP.PCAP.CD", "IT.NET.USER.ZS"]
  }'
```

## Default MarketMind Indicators

| Code | Name | Dimension |
|------|------|-----------|
| `NY.GDP.PCAP.CD` | GDP per capita (current US$) | macroeconomic_stability |
| `NY.GDP.MKTP.KD.ZG` | GDP growth (annual %) | macroeconomic_stability |
| `IT.NET.USER.ZS` | Internet users (% of population) | digital_readiness |
| `SP.POP.TOTL` | Population, total | market_population_potential |
| `SP.URB.TOTL.IN.ZS` | Urban population (% of total) | urban_consumption_potential |
| `IT.CEL.SETS.P2` | Mobile subscriptions (per 100 people) | digital_readiness |
| `IT.NET.BBND.P2` | Broadband subscriptions (per 100 people) | digital_readiness |

## Database Tables

| Table | Purpose |
|-------|---------|
| `ingestion_runs` | Tracks each ingestion execution |
| `worldbank_requests` | Each API call made to World Bank |
| `raw_api_responses` | Raw JSON responses (JSONB) |
| `worldbank_countries` | Normalized country data |
| `worldbank_indicators_catalog` | Internal indicator registry |
| `worldbank_observations` | Normalized time-series observations |

## Running Tests

```bash
# Install dev dependencies
poetry install

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing
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
# Lint
ruff check .

# Format
black .

# Type check
mypy .
```

## World Bank API Limitations

- **Rate limiting**: The World Bank API may throttle requests. The client implements exponential backoff with retry.
- **Data availability**: Not all indicators have data for all countries or years. Null values are preserved.
- **Response format**: The API returns a two-element array `[metadata, data]`. The client handles this defensively.
- **Pagination**: Large result sets are paginated. The client automatically fetches all pages.
- **Eventual consistency**: Data may be updated or revised by the World Bank at any time.

## Rate Limit Best Practices

- Use `per_page=1000` to minimize the number of requests
- Avoid parallel bulk collection of many indicators simultaneously
- Use `/indicators/collect` which collects sequentially with proper error handling
- The client retries on timeout and rate limit errors with exponential backoff
- Monitor `ingestion_runs` for failed status to detect persistent issues
