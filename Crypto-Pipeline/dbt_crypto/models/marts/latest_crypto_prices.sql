{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['symbol'], 'type': 'btree'},
      {'columns': ['last_updated'], 'type': 'btree'}
    ],
    tags=['marts', 'latest_data']
  )
}}

-- Latest crypto prices model
-- Produces the most recent price for each currency pair
-- Uses window functions for efficient latest record retrieval

WITH latest_prices AS (
  SELECT
    symbol,
    price,
    volume,
    bid,
    ask,
    spread,
    spread_pct,
    exchange,
    time AS last_updated,
    inserted_at,
    -- Use DISTINCT ON for better performance in PostgreSQL
    ROW_NUMBER() OVER (
      PARTITION BY symbol
      ORDER BY time DESC, inserted_at DESC
    ) AS rn
  FROM {{ ref('stg_crypto_prices') }}
  WHERE time >= CURRENT_TIMESTAMP - INTERVAL '24 hours'  -- Only consider recent data
),

price_history AS (
  -- Get 24h ago price for comparison
  SELECT
    symbol,
    price AS price_24h_ago,
    ROW_NUMBER() OVER (
      PARTITION BY symbol
      ORDER BY ABS(EXTRACT(EPOCH FROM (time - (CURRENT_TIMESTAMP - INTERVAL '24 hours'))))
    ) AS rn_24h
  FROM {{ ref('stg_crypto_prices') }}
  WHERE time BETWEEN CURRENT_TIMESTAMP - INTERVAL '25 hours'
    AND CURRENT_TIMESTAMP - INTERVAL '23 hours'
),

price_stats_24h AS (
  -- Calculate 24h statistics
  SELECT
    symbol,
    MIN(price) AS min_price_24h,
    MAX(price) AS max_price_24h,
    AVG(price) AS avg_price_24h,
    SUM(volume) AS volume_24h,
    COUNT(*) AS updates_24h
  FROM {{ ref('stg_crypto_prices') }}
  WHERE time >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
  GROUP BY symbol
)

SELECT
    lp.symbol,
    lp.price AS latest_price,
    lp.volume AS latest_volume,
    lp.bid AS latest_bid,
    lp.ask AS latest_ask,
    lp.spread,
    lp.spread_pct AS spread_percentage,

    -- 24h change metrics
    ph.price_24h_ago,
    CASE
        WHEN ph.price_24h_ago > 0 THEN lp.price - ph.price_24h_ago
        ELSE NULL
    END AS price_change_24h,
    CASE
        WHEN ph.price_24h_ago > 0 THEN ((lp.price - ph.price_24h_ago) / ph.price_24h_ago) * 100
        ELSE NULL
    END AS price_change_pct_24h,

    -- 24h statistics
    ps.min_price_24h,
    ps.max_price_24h,
    ps.avg_price_24h,
    ps.volume_24h,
    ps.updates_24h,

    -- Metadata
    lp.exchange,
    lp.last_updated,
    lp.inserted_at AS last_inserted_at,
    CURRENT_TIMESTAMP AS refreshed_at

FROM latest_prices lp
LEFT JOIN price_history ph
    ON lp.symbol = ph.symbol
    AND ph.rn_24h = 1
LEFT JOIN price_stats_24h ps
    ON lp.symbol = ps.symbol
WHERE lp.rn = 1
