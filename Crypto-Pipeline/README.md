# Crypto Pipeline (Minimal, Fully Functional)

This is a minimal, production-like crypto streaming pipeline:

- Producer fetches Coinbase spot prices -> Kafka (Redpanda)
- Consumer writes append-only rows -> PostgreSQL (TimescaleDB enabled)
- Optional: DBT models + Airflow DAGs for transformations and checks

## Quick Start (Poetry-only)

This project uses Poetry and a single `pyproject.toml` for dependency management.

Note: Setup and run everything strictly via the commands below.

### 0) Prereqs

- Python 3.11.x (repo uses 3.11.7). If you use pyenv:
  - `pyenv install 3.11.7 && pyenv local 3.11.7`
- Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`

### 1) Install dependencies

```bash
cd /Users/houta/desktop/projects/Beltone/Beltone_Docker/Crypto-Pipeline
 && poetry install
 && poetry install -E dbt
 && poetry env use 3.11 # installs runtime + dev tools + optional DBT extras (only if you plan to run dbt locally):
```

### 2) Start core stack

```bash
poetry run make start
# Console: http://localhost:8080
```

This brings up Redpanda, Postgres, Producer, Consumer. DB schema is auto-initialized from `database/init`.

```bash
# Verify
make status
 && cd /Users/houta/desktop/projects/Beltone/Beltone_Docker/Crypto-Pipeline
 && docker compose logs -f producer
 && docker compose logs -f consumer


# Postgres shell
make psql
-- In psql:
SELECT COUNT(*), MAX(time) FROM raw_crypto_prices_log;
```

# Add Poetry to PATH (optional)

brew install poetry
poetry --version

### 3) DBT (optional)

```bash
cd dbt_crypto
poetry run dbt deps --profiles-dir .
poetry run dbt run --target dev --profiles-dir .
poetry run dbt test --target dev --profiles-dir .
```

### 4) Airflow (optional, orchestrates DAGs)

# run from root

```bash
poetry run make airflow-init
poetry run make airflow-start
poetry run make airflow-stop
 && poetry run make airflow-clean



# Airflow UI: http://127.0.0.1:8081  (admin / admin123)
```

### 5) Stop all services + AF

```bash
poetry run make airflow-stop
 && poetry run make airflow-clean

poetry run make stop
 && poetry run make clean
```

## 🔧 Troubleshooting

### Common DBT Issues

If you encounter `No module named 'dbt.main'` errors, use the automated fix:

```bash
# Automated fix (recommended)
poetry run make dbt-clean

# Manual fix (if needed)
poetry run pip uninstall pytest-dbt-adapter -y
poetry install -E dbt
poetry run dbt --version
```

### Why This Happens

The `pytest-dbt-adapter` package can conflict with dbt's internal module structure, causing import errors. The clean script automatically removes these conflicts.

#### **Issue 2: Profile not found errors**

If you get `Could not find profile named 'crypto_analytics'` errors:

```bash
# Use the smart DBT runner (recommended)
bash scripts/run_dbt.sh build --target prod

# Or run from the correct directory
cd dbt_crypto
poetry run dbt build --target prod
```

**Why This Happens**: DBT needs to find both `dbt_project.yml` and `profiles.yml` files. The smart runner automatically detects the correct paths.

### Installation in case of any errors from above >> ( "run poetry run make airflow-stop && poetry run make airflow-clean" ) first

```bash
# Install DBT with PostgreSQL adapter via Poetry
poetry install -E dbt

# Navigate to DBT project
cd dbt_crypto

# Run all models
poetry run dbt run --profiles-dir .

# Test connection (from project root)
DBT_POSTGRES_HOST=localhost DBT_POSTGRES_PORT=5434 DBT_POSTGRES_DB=crypto_db DBT_POSTGRES_USER=crypto_user DBT_POSTGRES_PASSWORD=cryptopass123 poetry run dbt build --profiles-dir dbt_crypto --target prod

DBT_POSTGRES_HOST=localhost DBT_POSTGRES_PORT=5434 DBT_POSTGRES_DB=crypto_db DBT_POSTGRES_USER=crypto_user DBT_POSTGRES_PASSWORD=cryptopass123 poetry run dbt build --profiles-dir dbt_crypto --target dev

poetry run dbt debug --profiles-dir .

# All 3 commands above bundled
poetry install -E dbt && poetry run dbt --version | cat && cd dbt_crypto && poetry run dbt debug --profiles-dir . | cat
```

### Running Models

**Important**: DBT commands work differently depending on where you run them from:

#### **From dbt_crypto directory (Recommended):**

```bash
cd dbt_crypto
poetry run dbt run --target dev
poetry run dbt test --target dev
poetry run dbt build --target prod
```

#### **From project root:**

```bash
# Run specific model
poetry run dbt run --select latest_crypto_prices --profiles-dir dbt_crypto

# Full refresh incremental models
poetry run dbt run --select price_summary_15min --full-refresh --profiles-dir dbt_crypto
```

#### **Smart DBT Runner (Recommended for any directory):**

```bash
# From anywhere in the project
bash scripts/run_dbt.sh build --target prod
bash scripts/run_dbt.sh run --target dev
bash scripts/run_dbt.sh test --target dev

# Or use make
make dbt-smart build --target prod
```

The smart runner automatically detects your DBT project structure and uses the correct profiles directory.

# Generate documentation

poetry run dbt run --profiles-dir . && poetry run dbt docs generate --profiles-dir .

# Open in browser

poetry run dbt docs serve --port 8080 --profiles-dir .

````

## 🧪 Testing

We provide multiple testing options:

### 1. Bash Test Script

```bash
bash dbt_crypto/test_models.sh
bash dbt_crypto/test_dbt_setup.sh
````

Comprehensive testing with colored output and progress tracking.

### 2. Python Test Script

```bash
poetry run pytest dbt_crypto/test_models.py
```

Python-based testing with detailed query results.

### 3. Sample SQL Queries

```bash
psql -U postgres -d crypto_db -f sample_queries.sql
```

DAGs:

- `airflow/dags/crypto_pipeline_dag.py`: health checks, batch producer/consumer, data quality
- `airflow/dags/crypto_streaming_dag.py`: monitor/restart services
- `airflow/dags/crypto_dbt_dag.py`: run DBT models and validations

## 📁 Directory Structure

```
producer/           # Coinbase price producer
consumer/           # PostgreSQL consumer (append-only)
database/init/      # TimescaleDB schema + optimizations
airflow/            # Airflow image + DAGs + compose
dbt_crypto/         # DBT project (staging + marts)
monitoring/         # Optional monitoring utilities
docker-compose.yml  # Minimal unified compose
Makefile            # Simple dev commands
```

## Environment

Adjust via environment variables (examples already set in compose and code):

- `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Producer symbols: `CRYPTO_SYMBOLS=BTC-USD,ETH-USD,SOL-USD,DOGE-USD`

### 5) Monitoring UI (optional)

```bash
# Already covered by root Poetry install; monitoring runs via Docker/Grafana
```

## Local execution (without Docker)

The stack is designed for Docker. For quick local runs (useful for dev):

```bash
# Producer (fetches Coinbase spot prices and writes to Kafka)
poetry run python producer/coinbase_producer.py --duration 30

# Consumer (reads from Kafka and writes to Postgres)
poetry run python consumer/postgres_consumer.py --duration 30
```

## Developer workflow

```bash
# Lint/format/type-check
poetry run black .
poetry run isort .
poetry run flake8 .
poetry run mypy producer consumer alerting

# Tests
poetry run pytest -q
```

## 📚 Additional Resources

- DBT: https://docs.getdbt.com/
- TimescaleDB: https://docs.timescale.com/
- Redpanda: https://docs.redpanda.com/
