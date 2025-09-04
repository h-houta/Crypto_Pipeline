{{
  config(
    materialized='view',
    tags=['staging']
  )
}}

-- Staging model for raw crypto prices data
-- This view provides a clean interface to the raw crypto_prices table
-- with data quality filters and type casting

WITH source_data AS (
    SELECT
        time,
        symbol,
        CAST(price AS DECIMAL(20,8)) AS price,
        CAST(volume AS DECIMAL(30,8)) AS volume,
        NULL::DECIMAL(20,8) AS bid,
        NULL::DECIMAL(20,8) AS ask,
        COALESCE(exchange, 'coinbase') AS exchange,
        inserted_at
    FROM {{ source('raw', 'raw_crypto_prices_log') }}
)

SELECT
    time,
    symbol,
    price,
    volume,
    bid,
    ask,
    exchange,
    inserted_at,
    -- Add calculated fields
    CASE
        WHEN bid > 0 AND ask > 0 THEN ask - bid
        ELSE NULL
    END AS spread,
    CASE
        WHEN bid > 0 AND ask > 0 AND ask > 0 THEN ((ask - bid) / ask) * 100
        ELSE NULL
    END AS spread_pct
FROM source_data
WHERE
    price > 0  -- Filter out any invalid prices
    AND symbol IS NOT NULL
    AND time IS NOT NULL
