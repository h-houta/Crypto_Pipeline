{{
  config(
    materialized='incremental',
    unique_key='window_id',
    on_schema_change='fail',
    incremental_strategy='merge',
    cluster_by=['window_start', 'symbol'],
    indexes=[
      {'columns': ['symbol', 'window_start'], 'type': 'btree'},
      {'columns': ['window_start'], 'type': 'btree'},
      {'columns': ['window_id'], 'unique': true, 'type': 'btree'}
    ],
    tags=['marts', 'time_series']
  )
}}

-- Price summary for 15-minute windows
-- Aggregates min, max, avg, and count of updates per pair for every 15-minute window

WITH price_windows AS (
  SELECT
    -- Create 15-minute time buckets using time_bucket for better performance
    -- This ensures consistent window boundaries
    DATE_TRUNC('hour', time) +
      (FLOOR(EXTRACT(MINUTE FROM time) / 15) * INTERVAL '15 minutes') AS window_start,
    DATE_TRUNC('hour', time) +
      (FLOOR(EXTRACT(MINUTE FROM time) / 15) * INTERVAL '15 minutes') + INTERVAL '15 minutes' AS window_end,
    symbol,
    price,
    volume,
    bid,
    ask,
    spread,
    spread_pct,
    time
  FROM {{ ref('stg_crypto_prices') }}

  {% if is_incremental() %}
    -- On incremental runs, only process new data
    -- Look back 2 hours to handle late-arriving data
    WHERE time >= (
      SELECT COALESCE(MAX(window_start), '2024-01-01'::TIMESTAMP) - INTERVAL '2 hours'
      FROM {{ this }}
    )
  {% endif %}
),

window_aggregates AS (
  SELECT
    window_start,
    window_end,
    symbol,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    AVG(price) AS avg_price,
    STDDEV(price) AS price_stddev,
    SUM(volume) AS total_volume,
    AVG(volume) AS avg_volume,

    -- Bid/Ask statistics
    AVG(bid) AS avg_bid,
    AVG(ask) AS avg_ask,
    AVG(spread) AS avg_spread,
    AVG(spread_pct) AS avg_spread_pct,
    MAX(spread) AS max_spread,

    -- Update statistics
    COUNT(*) AS update_count,
    COUNT(DISTINCT DATE_TRUNC('second', time)) AS unique_seconds_with_updates,
    MIN(time) AS first_time,
    MAX(time) AS last_time
  FROM price_windows
  GROUP BY window_start, window_end, symbol
),

window_with_endpoints AS (
  SELECT
    wa.*,
    first_price.price AS first_price,
    last_price.price AS last_price
  FROM window_aggregates wa
  LEFT JOIN LATERAL (
    SELECT price
    FROM price_windows pw
    WHERE pw.window_start = wa.window_start
      AND pw.symbol = wa.symbol
      AND pw.time = wa.first_time
    LIMIT 1
  ) first_price ON TRUE
  LEFT JOIN LATERAL (
    SELECT price
    FROM price_windows pw
    WHERE pw.window_start = wa.window_start
      AND pw.symbol = wa.symbol
      AND pw.time = wa.last_time
    LIMIT 1
  ) last_price ON TRUE
)

SELECT
  -- Create a unique key for incremental updates
  MD5(window_start::TEXT || '|' || symbol) AS window_id,
  window_start,
  window_end,
  symbol,

  -- Price aggregations
  min_price,
  max_price,
  avg_price,
  price_stddev,

  -- Volume aggregations
  total_volume,
  avg_volume,

  -- Bid/Ask metrics
  avg_bid,
  avg_ask,
  avg_spread,
  avg_spread_pct,
  max_spread,

  -- Update statistics
  update_count,
  unique_seconds_with_updates,
  CASE
    WHEN update_count > 0 THEN ROUND(unique_seconds_with_updates::DECIMAL / update_count * 100, 2)
    ELSE NULL
  END AS update_distribution_pct,

  -- Price movement metrics
  max_price - min_price AS price_range,
  CASE
    WHEN min_price > 0 THEN ((max_price - min_price) / min_price) * 100
    ELSE NULL
  END AS price_range_percentage,

  -- Volatility indicator
  CASE
    WHEN avg_price > 0 THEN (price_stddev / avg_price) * 100
    ELSE NULL
  END AS coefficient_of_variation,

  -- Trend analysis
  first_price,
  last_price,
  CASE
    WHEN first_price > 0 THEN ((last_price - first_price) / first_price) * 100
    ELSE NULL
  END AS period_return_percentage,

  -- Trading activity indicator
  CASE
    WHEN update_count >= 100 THEN 'Very High'
    WHEN update_count >= 50 THEN 'High'
    WHEN update_count >= 20 THEN 'Medium'
    WHEN update_count >= 5 THEN 'Low'
    ELSE 'Very Low'
  END AS activity_level,

  CURRENT_TIMESTAMP AS updated_at

FROM window_with_endpoints
