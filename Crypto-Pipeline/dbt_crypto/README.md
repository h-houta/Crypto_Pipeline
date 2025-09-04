# DBT Crypto Analytics

This DBT project transforms raw cryptocurrency price data from the `crypto_prices` table into analytical models optimized for real-time analytics and reporting.

## 📊 Data Models

### Staging Layer

- **stg_crypto_prices**: Clean staging view of raw crypto_prices table with data validation, type casting, and calculated spread metrics

### Marts Layer

- **latest_crypto_prices**: Real-time snapshot with enhanced 24-hour statistics and performance metrics
- **price_summary_15min**: Advanced 15-minute aggregations with volatility indicators and activity levels
- **crypto_ohlcv_15min**: Standard OHLCV candlestick data for charting

## 🚀 Quick Start

### Installation

```bash
# Install DBT with PostgreSQL adapter (via Poetry extras)
poetry install -E dbt

# Navigate to DBT project
cd dbt_crypto

# Test connection
poetry run dbt debug --profiles-dir .

# All 3 commands above bundled
poetry install -E dbt && poetry run dbt --version | cat && poetry run dbt debug --profiles-dir . | cat
```

### Running Models

```bash
# Run all models
poetry run dbt run --profiles-dir .

# Run specific model
poetry run dbt run --select latest_crypto_prices --profiles-dir .

# Full refresh incremental models
poetry run dbt run --select price_summary_15min --full-refresh --profiles-dir .

# Run tests
DBT_POSTGRES_HOST=localhost DBT_POSTGRES_PORT=5432 DBT_POSTGRES_DB=crypto_db DBT_POSTGRES_USER=crypto_user DBT_POSTGRES_PASSWORD=cryptopass123 poetry run dbt build --profiles-dir . --target prod

DBT_POSTGRES_HOST=localhost DBT_POSTGRES_PORT=5432 DBT_POSTGRES_DB=crypto_db DBT_POSTGRES_USER=crypto_user DBT_POSTGRES_PASSWORD=cryptopass123 poetry run dbt build --profiles-dir . --target dev

# Generate documentation
poetry run dbt run --profiles-dir . && poetry run dbt docs generate --profiles-dir .
# Open in browser
poetry run dbt docs serve --port 8080 --profiles-dir .
```

## 🧪 Testing

We provide multiple testing options:

### 1. Bash Test Script

```bash
bash dbt_crypto/test_models.sh
bash dbt_crypto/test_dbt_setup.sh
```

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

Pre-written queries to explore and validate your data.

## 📈 Model Details

### latest_crypto_prices

**Type**: Table (fully refreshed on each run)

**New Features**:

- 24-hour price change (absolute and percentage)
- 24-hour high/low/average prices
- 24-hour trading volume aggregation
- Update frequency metrics
- Enhanced spread analysis

**Key Columns**:

- `latest_price`: Current price
- `price_change_24h`: Absolute 24h change
- `price_change_pct_24h`: Percentage 24h change
- `min_price_24h`, `max_price_24h`: 24h range
- `volume_24h`: Total 24h volume
- `updates_24h`: Number of updates in 24h

### price_summary_15min

**Type**: Incremental table with merge strategy

**New Features**:

- Bid/ask spread statistics
- Volatility indicators (coefficient of variation)
- Activity level classification
- Update distribution metrics
- Improved incremental logic with 2-hour lookback

**Key Columns**:

- `min_price`, `max_price`, `avg_price`: Price statistics
- `avg_spread`, `avg_spread_pct`: Spread metrics
- `coefficient_of_variation`: Volatility measure
- `activity_level`: Trading intensity (Very Low to Very High)
- `period_return_percentage`: 15-min returns

### crypto_ohlcv_15min

**Type**: Incremental table

**Features**:

- Open, High, Low, Close prices
- Total volume per period
- Trade count metrics

## ⚙️ Configuration

### Database Connection

The `profiles.yml` is pre-configured for:

- **Dev**: Local PostgreSQL (localhost:5432)
- **Prod**: Environment variable based configuration

### Model Materializations

- **Staging**: Views for real-time data access
- **Latest Prices**: Table with indexes on symbol and timestamp
- **15-min Summary**: Incremental table with merge strategy
- **OHLCV**: Incremental table for efficient updates

## 📊 Key Metrics Explained

### Price Metrics

- **Spread %**: `(ask - bid) / ask * 100` - Market liquidity indicator
- **24h Change %**: `(current - 24h_ago) / 24h_ago * 100` - Daily performance
- **Coefficient of Variation**: `stddev / avg * 100` - Volatility measure
- **Period Return %**: `(close - open) / open * 100` - Window performance

### Activity Metrics

- **Activity Level**: Classification based on update frequency
  - Very High: 100+ updates
  - High: 50-99 updates
  - Medium: 20-49 updates
  - Low: 5-19 updates
  - Very Low: <5 updates
- **Update Distribution %**: Measure of how evenly distributed updates are

## 🔄 Scheduling

### Using Airflow

```python
# See: airflow/dags/crypto_dbt_dag.py
# Default schedule: Every 15 minutes
```

### Manual Refresh

```bash
# Quick refresh (latest prices only)
dbt run --select latest_crypto_prices --profiles-dir .

# Full pipeline refresh
dbt run --profiles-dir .
```

### Recommended Schedule

- `latest_crypto_prices`: Every 1-5 minutes
- `price_summary_15min`: Every 15 minutes
- `crypto_ohlcv_15min`: Every 15 minutes

## 📝 Data Quality

### Built-in Tests

- Not-null constraints on critical fields
- Unique constraints on primary keys
- Source data validation
- Referential integrity checks

### Monitoring Queries

```sql
-- Check for stale data
SELECT * FROM latest_crypto_prices
WHERE last_updated < NOW() - INTERVAL '5 minutes';

-- Verify incremental loads
SELECT MAX(window_start), COUNT(*)
FROM price_summary_15min
WHERE window_start >= CURRENT_DATE;

-- Data completeness check
SELECT symbol, COUNT(*) as windows
FROM price_summary_15min
WHERE window_start >= NOW() - INTERVAL '2 hours'
GROUP BY symbol;
```

## 🐛 Troubleshooting

### Common Issues

1. **Connection Failed**

   ```bash
   dbt debug --profiles-dir .
   ```

   - Verify PostgreSQL is running
   - Check credentials in profiles.yml
   - Ensure database exists

2. **Model Compilation Errors**

   ```bash
   dbt compile --profiles-dir . --models <model_name>
   ```

   - Review SQL syntax
   - Check column references

3. **Incremental Model Issues**

   ```bash
   # Force rebuild
   dbt run --select price_summary_15min --full-refresh --profiles-dir .
   ```

   - Check for duplicate keys
   - Verify unique_key configuration

4. **Performance Issues**
   - Verify indexes are created
   - Check PostgreSQL query plans
   - Consider table partitioning for large datasets

## 📁 Directory Structure

```
dbt_crypto/
├── models/
│   ├── staging/
│   │   └── stg_crypto_prices.sql      # Enhanced with spread calculations
│   ├── marts/
│   │   ├── latest_crypto_prices.sql   # Added 24h statistics
│   │   ├── price_summary_15min.sql    # Enhanced with volatility metrics
│   │   └── crypto_ohlcv_15min.sql     # Standard OHLCV
│   └── schema.yml                     # Complete column documentation
├── test_models.sh                     # Bash test script
├── test_models.py                     # Python test script
├── sample_queries.sql                 # Example queries
├── dbt_project.yml                   # Project configuration
├── profiles.yml                      # Connection profiles
└── README.md                         # This file
```

## 🔗 Dependencies

- PostgreSQL 12+ with TimescaleDB extension
- Python 3.8+
- dbt-core >= 1.0
- dbt-postgres >= 1.0
- psycopg2 (for Python scripts)

## 📚 Additional Resources

- [DBT Best Practices](https://docs.getdbt.com/guides/best-practices)
- [PostgreSQL Window Functions](https://www.postgresql.org/docs/current/tutorial-window.html)
- [TimescaleDB Continuous Aggregates](https://docs.timescale.com/timescaledb/latest/how-to-guides/continuous-aggregates/)

## 🎯 Next Steps

1. **Add More Models**:

   - Hourly/Daily aggregations
   - Technical indicators (RSI, MACD)
   - Cross-pair correlations

2. **Enhance Testing**:

   - Add custom schema tests
   - Implement anomaly detection
   - Create data freshness checks

3. **Optimize Performance**:

   - Implement table partitioning
   - Add materialized views
   - Configure query optimization

4. **Build Dashboards**:
   - Connect to Grafana/Superset
   - Create real-time monitoring
   - Build alerting systems
