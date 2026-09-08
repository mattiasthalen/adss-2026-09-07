-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss._bridge AS
WITH placed AS (
    SELECT
        placed."ORDER_key" AS order_key,
        placed.eff_tmstp AS _observed_at,
        cast(placed."PLACED_ON" AS DATE) AS _event_date,
        cast(1 AS BIGINT) AS _measure__order__placed_orders_count
    FROM dab."view_ORDER_hist" AS placed
    WHERE placed."PLACED_ON" IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY placed."ORDER_key"
        ORDER BY placed.eff_tmstp DESC
    ) = 1
)

SELECT
    'order' AS _stage,
    'placed' AS _event,
    placed._event_date AS _event_date,
    TRUE AS _is_current,
    placed._observed_at AS _observed_at,
    placed.order_key AS order_key,
    placed._measure__order__placed_orders_count AS _measure__order__placed_orders_count
FROM placed AS placed;
