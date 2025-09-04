{{
  config(
    materialized='incremental',
    alias='crypto_ohlcv_15min_tbl',
    unique_key='period_key',
    on_schema_change='fail',
    indexes=[
      {'columns': ['symbol', 'period_start'], 'type': 'btree'},
    ]
  )
}}

WITH price_windows AS (
  SELECT
    DATE_TRUNC('minute', time) -
      (EXTRACT(MINUTE FROM time)::INT % 15) * INTERVAL '1 minute' AS period_start,
    symbol,
    price,
    volume,
    time
  FROM {{ ref('stg_crypto_prices') }}

  {% if is_incremental() %}
    WHERE time >= (
      SELECT COALESCE(MAX(period_start), '2024-01-01'::TIMESTAMP) - INTERVAL '1 hour'
      FROM {{ this }}
    )
  {% endif %}
),
windowed AS (
  SELECT
    period_start,
    symbol,
    price,
    volume,
    time,
    FIRST_VALUE(price) OVER w AS open,
    MAX(price) OVER w AS high,
    MIN(price) OVER w AS low,
    LAST_VALUE(price) OVER w AS close,
    SUM(volume) OVER w AS total_volume,
    COUNT(*) OVER w AS trade_count,
    ROW_NUMBER() OVER (PARTITION BY period_start, symbol ORDER BY time DESC) AS rn
  FROM price_windows
  WINDOW w AS (
    PARTITION BY period_start, symbol
    ORDER BY time
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  )
)

SELECT
  MD5(period_start::TEXT || '|' || symbol) AS period_key,
  period_start,
  symbol,
  open,
  high,
  low,
  close,
  total_volume,
  trade_count,
  CURRENT_TIMESTAMP AS updated_at
FROM windowed
WHERE rn = 1
