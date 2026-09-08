-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss._bridge AS
WITH placed__version AS (
    SELECT
        revision."ORDER_key" AS order_key,
        revision.eff_tmstp AS _observed_at,
        cast(revision."PLACED_ON" AS DATE) AS _event_date,
        cast(1 AS BIGINT) AS _measure__order__placed_orders_count,
        cast(revision."FREIGHT_CHARGE" AS DECIMAL(28, 8)) AS _measure__order__freight_orders_amount
    FROM dab."view_ORDER_hist" AS revision
    WHERE revision."PLACED_ON" IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY revision."ORDER_key"
        ORDER BY revision.eff_tmstp DESC
    ) = 1
),

placed__order_is_placed_by_customer AS (
    SELECT
        revision.order_key AS order_key,
        revision._observed_at AS _observed_at,
        pair."CUSTOMER_key" AS customer_key
    FROM placed__version AS revision
    LEFT JOIN dab."v_ORDER_IS_PLACED_BY_CUSTOMER" AS pair
        ON
            revision.order_key = pair."ORDER_key"
            AND pair.rel_name = 'ORDER_IS_PLACED_BY_CUSTOMER'
            AND pair.row_st = 'Y'
            AND revision._observed_at >= pair.eff_tmstp
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_key, revision._observed_at
        ORDER BY
            pair.eff_tmstp DESC,
            pair.ver_tmstp DESC,
            pair."CUSTOMER_key" ASC
    ) = 1
),

placed AS (
    SELECT
        revision.order_key AS order_key,
        revision._observed_at AS _observed_at,
        revision._event_date AS _event_date,
        order_is_placed_by_customer.customer_key AS customer_key,
        revision._measure__order__placed_orders_count AS _measure__order__placed_orders_count,
        revision._measure__order__freight_orders_amount AS _measure__order__freight_orders_amount
    FROM placed__version AS revision
    LEFT JOIN placed__order_is_placed_by_customer AS order_is_placed_by_customer
        ON
            revision.order_key = order_is_placed_by_customer.order_key
            AND revision._observed_at = order_is_placed_by_customer._observed_at
),

shipped__version AS (
    SELECT
        revision."ORDER_key" AS order_key,
        revision.eff_tmstp AS _observed_at,
        cast(revision."SHIPPED_ON" AS DATE) AS _event_date,
        cast(1 AS BIGINT) AS _measure__order__shipped_orders_count,
        cast(revision."SHIP_LAG_DAYS" AS DECIMAL(28, 8)) AS _measure__order__ship_lag_orders_days
    FROM dab."view_ORDER_hist" AS revision
    WHERE revision."SHIPPED_ON" IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY revision."ORDER_key"
        ORDER BY revision.eff_tmstp DESC
    ) = 1
),

shipped__order_is_placed_by_customer AS (
    SELECT
        revision.order_key AS order_key,
        revision._observed_at AS _observed_at,
        pair."CUSTOMER_key" AS customer_key
    FROM shipped__version AS revision
    LEFT JOIN dab."v_ORDER_IS_PLACED_BY_CUSTOMER" AS pair
        ON
            revision.order_key = pair."ORDER_key"
            AND pair.rel_name = 'ORDER_IS_PLACED_BY_CUSTOMER'
            AND pair.row_st = 'Y'
            AND revision._observed_at >= pair.eff_tmstp
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_key, revision._observed_at
        ORDER BY
            pair.eff_tmstp DESC,
            pair.ver_tmstp DESC,
            pair."CUSTOMER_key" ASC
    ) = 1
),

shipped AS (
    SELECT
        revision.order_key AS order_key,
        revision._observed_at AS _observed_at,
        revision._event_date AS _event_date,
        order_is_placed_by_customer.customer_key AS customer_key,
        revision._measure__order__shipped_orders_count AS _measure__order__shipped_orders_count,
        revision._measure__order__ship_lag_orders_days AS _measure__order__ship_lag_orders_days
    FROM shipped__version AS revision
    LEFT JOIN shipped__order_is_placed_by_customer AS order_is_placed_by_customer
        ON
            revision.order_key = order_is_placed_by_customer.order_key
            AND revision._observed_at = order_is_placed_by_customer._observed_at
)

SELECT
    'order' AS _stage,
    'placed' AS _event,
    placed._event_date AS _event_date,
    TRUE AS _is_current,
    placed._observed_at AS _observed_at,
    placed.order_key AS order_key,
    placed.customer_key AS customer_key,
    placed._measure__order__placed_orders_count AS _measure__order__placed_orders_count,
    placed._measure__order__freight_orders_amount AS _measure__order__freight_orders_amount,
    cast(NULL AS BIGINT) AS _measure__order__shipped_orders_count,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order__ship_lag_orders_days
FROM placed AS placed

UNION ALL

SELECT
    'order' AS _stage,
    'shipped' AS _event,
    shipped._event_date AS _event_date,
    TRUE AS _is_current,
    shipped._observed_at AS _observed_at,
    shipped.order_key AS order_key,
    shipped.customer_key AS customer_key,
    cast(NULL AS BIGINT) AS _measure__order__placed_orders_count,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order__freight_orders_amount,
    shipped._measure__order__shipped_orders_count AS _measure__order__shipped_orders_count,
    shipped._measure__order__ship_lag_orders_days AS _measure__order__ship_lag_orders_days
FROM shipped AS shipped;
