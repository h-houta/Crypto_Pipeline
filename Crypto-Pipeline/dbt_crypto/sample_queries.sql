-- =====================================================
-- DBT Crypto Analytics - Sample Queries
-- =====================================================
-- Use these queries to explore and validate your DBT models
-- Run them in your PostgreSQL client or via psql

-- -----------------------------------------------------
-- 1. LATEST CRYPTO PRICES
-- -----------------------------------------------------

-- Get current prices for all symbols with 24h change
SELECT 
    symbol,
    ROUND(latest_price::numeric, 2) AS current_price,
    ROUND(price_change_pct_24h::numeric, 2) AS "24h_change_%",
    ROUND(volume_24h::numeric, 2) AS "24h_volume",
    ROUND(spread_percentage::numeric, 4) AS "spread_%",
    TO_CHAR(last_updated, 'YYYY-MM-DD HH24:MI:SS') AS last_update
FROM latest_crypto_prices
ORDER BY symbol;

-- Top gainers in last 24 hours
SELECT 
    symbol,
    ROUND(latest_price::numeric, 2) AS price,
    ROUND(price_change_pct_24h::numeric, 2) AS "gain_%"
FROM latest_crypto_prices
WHERE price_change_pct_24h > 0
ORDER BY price_change_pct_24h DESC
LIMIT 5;

-- Top losers in last 24 hours
SELECT 
    symbol,
    ROUND(latest_price::numeric, 2) AS price,
    ROUND(price_change_pct_24h::numeric, 2) AS "loss_%"
FROM latest_crypto_prices
WHERE price_change_pct_24h < 0
ORDER BY price_change_pct_24h ASC
LIMIT 5;

-- Symbols with highest trading activity
SELECT 
    symbol,
    updates_24h AS "24h_updates",
    ROUND(volume_24h::numeric, 2) AS "24h_volume",
    ROUND(latest_price::numeric, 2) AS current_price
FROM latest_crypto_prices
ORDER BY updates_24h DESC
LIMIT 10;

-- -----------------------------------------------------
-- 2. 15-MINUTE PRICE SUMMARIES
-- -----------------------------------------------------

-- Recent 15-minute windows for a specific symbol (e.g., BTC-USD)
SELECT 
    TO_CHAR(window_start, 'YYYY-MM-DD HH24:MI') AS period,
    symbol,
    ROUND(min_price::numeric, 2) AS low,
    ROUND(avg_price::numeric, 2) AS average,
    ROUND(max_price::numeric, 2) AS high,
    ROUND(price_range_percentage::numeric, 2) AS "volatility_%",
    update_count AS updates,
    activity_level
FROM price_summary_15min
WHERE symbol = 'BTC-USD'
    AND window_start >= CURRENT_TIMESTAMP - INTERVAL '2 hours'
ORDER BY window_start DESC;

-- Most volatile periods in the last hour
SELECT 
    TO_CHAR(window_start, 'HH24:MI') AS time,
    symbol,
    ROUND(price_range_percentage::numeric, 2) AS "price_range_%",
    ROUND(coefficient_of_variation::numeric, 2) AS "cv_%",
    activity_level
FROM price_summary_15min
WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    AND price_range_percentage > 0.5  -- More than 0.5% price range
ORDER BY price_range_percentage DESC
LIMIT 10;

-- Trading activity heatmap (last 4 hours)
SELECT 
    symbol,
    TO_CHAR(window_start, 'HH24:MI') AS time_slot,
    activity_level,
    update_count
FROM price_summary_15min
WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '4 hours'
ORDER BY symbol, window_start DESC;

-- Average spreads by symbol over last hour
SELECT 
    symbol,
    COUNT(*) AS windows,
    ROUND(AVG(avg_spread::numeric), 4) AS avg_spread,
    ROUND(AVG(avg_spread_pct::numeric), 4) AS "avg_spread_%",
    ROUND(MAX(max_spread::numeric), 4) AS max_spread_seen
FROM price_summary_15min
WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY "avg_spread_%" DESC;

-- -----------------------------------------------------
-- 3. CROSS-MODEL ANALYSIS
-- -----------------------------------------------------

-- Compare current price with 15-min averages
SELECT 
    l.symbol,
    ROUND(l.latest_price::numeric, 2) AS current_price,
    ROUND(p.avg_price::numeric, 2) AS "15min_avg",
    ROUND(((l.latest_price - p.avg_price) / p.avg_price * 100)::numeric, 2) AS "diff_%"
FROM latest_crypto_prices l
JOIN (
    SELECT DISTINCT ON (symbol) 
        symbol, 
        avg_price
    FROM price_summary_15min
    WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
    ORDER BY symbol, window_start DESC
) p ON l.symbol = p.symbol;

-- Daily statistics summary
SELECT 
    COUNT(DISTINCT symbol) AS active_symbols,
    SUM(updates_24h) AS total_updates_24h,
    ROUND(AVG(price_change_pct_24h::numeric), 2) AS "avg_change_%",
    ROUND(SUM(volume_24h::numeric), 2) AS total_volume_24h
FROM latest_crypto_prices;

-- -----------------------------------------------------
-- 4. DATA QUALITY CHECKS
-- -----------------------------------------------------

-- Check for stale data
SELECT 
    symbol,
    TO_CHAR(last_updated, 'YYYY-MM-DD HH24:MI:SS') AS last_update,
    EXTRACT(EPOCH FROM (NOW() - last_updated))/60 AS minutes_since_update
FROM latest_crypto_prices
WHERE last_updated < NOW() - INTERVAL '5 minutes'
ORDER BY last_updated ASC;

-- Check data completeness in recent windows
SELECT 
    TO_CHAR(window_start, 'YYYY-MM-DD HH24:MI') AS window,
    COUNT(DISTINCT symbol) AS symbols_count,
    SUM(update_count) AS total_updates
FROM price_summary_15min
WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
GROUP BY window_start
ORDER BY window_start DESC;

-- Identify symbols with irregular updates
SELECT 
    symbol,
    COUNT(*) AS windows_with_data,
    ROUND(AVG(update_count)::numeric, 2) AS avg_updates_per_window,
    MIN(update_count) AS min_updates,
    MAX(update_count) AS max_updates
FROM price_summary_15min
WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '2 hours'
GROUP BY symbol
HAVING COUNT(*) < 8  -- Less than expected 8 windows in 2 hours
ORDER BY windows_with_data ASC;

-- -----------------------------------------------------
-- 5. PERFORMANCE MONITORING
-- -----------------------------------------------------

-- Model refresh timestamps
SELECT 
    'latest_crypto_prices' AS model,
    MAX(refreshed_at) AS last_refresh,
    EXTRACT(EPOCH FROM (NOW() - MAX(refreshed_at)))/60 AS minutes_since_refresh
FROM latest_crypto_prices
UNION ALL
SELECT 
    'price_summary_15min' AS model,
    MAX(updated_at) AS last_refresh,
    EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/60 AS minutes_since_refresh
FROM price_summary_15min;

-- Row counts by model
SELECT 
    'stg_crypto_prices' AS model,
    COUNT(*) AS row_count
FROM stg_crypto_prices
UNION ALL
SELECT 
    'latest_crypto_prices' AS model,
    COUNT(*) AS row_count
FROM latest_crypto_prices
UNION ALL
SELECT 
    'price_summary_15min' AS model,
    COUNT(*) AS row_count
FROM price_summary_15min
ORDER BY model;
