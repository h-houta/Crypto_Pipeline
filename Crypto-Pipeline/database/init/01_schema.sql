-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create main price table
CREATE TABLE raw_crypto_prices_log (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    volume DECIMAL(30,8),
    bid DECIMAL(20,8),
    ask DECIMAL(20,8),
    exchange VARCHAR(50) DEFAULT 'coinbase',
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('raw_crypto_prices_log', 'time');

-- Create BRIN index for time-series queries
CREATE INDEX idx_crypto_time_brin ON raw_crypto_prices_log
  USING BRIN(time) WITH (pages_per_range = 128);

-- Create index for symbol queries
CREATE INDEX idx_crypto_symbol ON raw_crypto_prices_log(symbol, time DESC);

-- Enable compression after 7 days
ALTER TABLE raw_crypto_prices_log SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'symbol',
  timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('raw_crypto_prices_log', INTERVAL '7 days');

-- Update continuous aggregate reference
CREATE MATERIALIZED VIEW crypto_ohlcv_15min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', time) AS bucket,
    symbol,
    FIRST(price, time) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, time) AS close,
    SUM(volume) AS volume,
    COUNT(*) AS num_trades
FROM raw_crypto_prices_log
GROUP BY bucket, symbol
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('crypto_ohlcv_15min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
