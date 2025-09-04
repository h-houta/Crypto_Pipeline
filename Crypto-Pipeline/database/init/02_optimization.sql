-- Optimization settings for TimescaleDB
-- Forward clustering and partitioning optimizations

-- 1. PARTITIONING OPTIMIZATION WITH FORWARD CLUSTERING
-- =====================================================

-- Set chunk time interval to 1 day for optimal performance
-- Smaller chunks = better compression and faster queries for recent data
SELECT set_chunk_time_interval('raw_crypto_prices_log', INTERVAL '1 day');

-- Enable chunk reordering for better compression (forward clustering)
-- This reorders data within chunks by symbol and time for optimal storage
ALTER TABLE raw_crypto_prices_log SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'symbol,exchange',
  timescaledb.compress_orderby = 'time DESC',
  timescaledb.compress_chunk_time_interval = '1 day'
);

-- Add compression policy for older data
SELECT remove_compression_policy('raw_crypto_prices_log', if_exists => true);
SELECT add_compression_policy('raw_crypto_prices_log',
  compress_after => INTERVAL '3 days',
  if_not_exists => true
);

-- 2. BRIN INDEX OPTIMIZATION FOR TIME-SERIES
-- ===========================================

-- Drop existing BRIN index if it exists
DROP INDEX IF EXISTS idx_crypto_time_brin;

-- Create optimized BRIN index with smaller pages_per_range for better selectivity
-- BRIN is perfect for append-only time-series data
CREATE INDEX idx_crypto_time_brin ON raw_crypto_prices_log
  USING BRIN(time, symbol)
  WITH (pages_per_range = 32, autosummarize = on);

-- Create additional BRIN index for inserted_at column
CREATE INDEX idx_crypto_inserted_brin ON raw_crypto_prices_log
  USING BRIN(inserted_at)
  WITH (pages_per_range = 32, autosummarize = on);

-- 3. BTREE INDEX OPTIMIZATION
-- ============================

-- Drop and recreate symbol index with better configuration
DROP INDEX IF EXISTS idx_crypto_symbol;

-- Create covering index to avoid heap lookups
-- Use a stable cutoff for init time to avoid IMMUTABLE issue during bootstrap
DO $$ BEGIN
  EXECUTE format('CREATE INDEX IF NOT EXISTS idx_crypto_symbol_covering ON raw_crypto_prices_log(symbol, time DESC)
    INCLUDE (price, volume, bid, ask)
    WHERE time > %L', NOW() - INTERVAL '7 days');
END $$;

-- Create partial index for recent data queries
DO $$ BEGIN
  EXECUTE format('CREATE INDEX IF NOT EXISTS idx_crypto_recent ON raw_crypto_prices_log(time DESC, symbol)
    WHERE time > %L', NOW() - INTERVAL '24 hours');
END $$;

-- 4. DATA RETENTION POLICIES
-- ==========================

-- Add data retention policy (keep 90 days of raw data)
SELECT add_retention_policy('raw_crypto_prices_log',
  drop_after => INTERVAL '90 days',
  if_not_exists => true
);

-- 5. CONTINUOUS AGGREGATE OPTIMIZATION
-- =====================================

-- Drop existing continuous aggregate
DROP MATERIALIZED VIEW IF EXISTS crypto_ohlcv_15min CASCADE;

-- Create optimized continuous aggregate with real-time aggregation
CREATE MATERIALIZED VIEW crypto_ohlcv_15min
WITH (
  timescaledb.continuous,
  timescaledb.materialized_only = false,
  timescaledb.create_group_indexes = true
) AS
SELECT
    time_bucket('15 minutes', time) AS bucket,
    symbol,
    exchange,
    FIRST(price, time) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, time) AS close,
    SUM(volume) AS volume,
    COUNT(*) AS num_trades,
    AVG(price) AS avg_price,
    STDDEV(price) AS price_stddev
FROM raw_crypto_prices_log
GROUP BY bucket, symbol, exchange
WITH NO DATA;

-- Create indexes on continuous aggregate
CREATE INDEX idx_ohlcv_symbol_bucket ON crypto_ohlcv_15min(symbol, bucket DESC);
CREATE INDEX idx_ohlcv_bucket ON crypto_ohlcv_15min(bucket DESC);

-- Add refresh policy with real-time updates
SELECT add_continuous_aggregate_policy('crypto_ohlcv_15min',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => true
);

-- 6. STATISTICS AND AUTOVACUUM OPTIMIZATION
-- ==========================================

-- Optimize table statistics for better query planning
ALTER TABLE raw_crypto_prices_log SET (
  autovacuum_vacuum_scale_factor = 0.01,
  autovacuum_analyze_scale_factor = 0.005,
  autovacuum_vacuum_cost_delay = 2,
  autovacuum_vacuum_cost_limit = 1000
);

-- Update statistics target for frequently queried columns
ALTER TABLE raw_crypto_prices_log ALTER COLUMN time SET STATISTICS 1000;
ALTER TABLE raw_crypto_prices_log ALTER COLUMN symbol SET STATISTICS 500;

-- 7. CREATE HELPER FUNCTIONS
-- ==========================

-- Function to get partition info
CREATE OR REPLACE FUNCTION get_partition_info()
RETURNS TABLE(
    chunk_name text,
    chunk_tablespace text,
    range_start timestamptz,
    range_end timestamptz,
    is_compressed boolean,
    compressed_size text,
    uncompressed_size text
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ch.chunk_name::text,
        ch.chunk_tablespace::text,
        ch.range_start,
        ch.range_end,
        COALESCE(comp.chunk_name IS NOT NULL, false) as is_compressed,
        pg_size_pretty(COALESCE(comp.compressed_total_bytes, 0)) as compressed_size,
        pg_size_pretty(COALESCE(comp.uncompressed_total_bytes,
                                ch.total_bytes)) as uncompressed_size
    FROM timescaledb_information.chunks ch
    LEFT JOIN timescaledb_information.compression_chunk_stats comp
        ON ch.chunk_name = comp.chunk_name
    WHERE ch.hypertable_name = 'raw_crypto_prices_log'
    ORDER BY ch.range_start DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to check write throughput
CREATE OR REPLACE FUNCTION get_write_throughput(
    interval_minutes integer DEFAULT 5
)
RETURNS TABLE(
    time_window timestamptz,
    records_written bigint,
    records_per_second numeric,
    mb_written numeric,
    mb_per_second numeric
) AS $$
BEGIN
    RETURN QUERY
    WITH write_stats AS (
        SELECT
            date_trunc('minute', inserted_at) as minute,
            COUNT(*) as record_count,
            SUM(pg_column_size(raw_crypto_prices_log.*)) as bytes_written
        FROM raw_crypto_prices_log
        WHERE inserted_at > NOW() - (interval_minutes || ' minutes')::interval
        GROUP BY date_trunc('minute', inserted_at)
    )
    SELECT
        minute,
        record_count,
        ROUND(record_count::numeric / 60, 2) as rps,
        ROUND(bytes_written::numeric / 1024 / 1024, 2) as mb,
        ROUND(bytes_written::numeric / 1024 / 1024 / 60, 4) as mbps
    FROM write_stats
    ORDER BY minute DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_partition_info() TO crypto_user;
GRANT EXECUTE ON FUNCTION get_write_throughput(integer) TO crypto_user;

-- Analyze tables to update statistics
ANALYZE raw_crypto_prices_log;
