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
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_key, revision._observed_at
        ORDER BY
            CASE
                WHEN pair.eff_tmstp <= revision._observed_at
                    THEN pair.eff_tmstp
            END DESC NULLS LAST,
            pair.eff_tmstp ASC,
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
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_key, revision._observed_at
        ORDER BY
            CASE
                WHEN pair.eff_tmstp <= revision._observed_at
                    THEN pair.eff_tmstp
            END DESC NULLS LAST,
            pair.eff_tmstp ASC,
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
),

ordered__version AS (
    SELECT
        revision."ORDER_LINE_key" AS order_line_key,
        revision.eff_tmstp AS _observed_at,
        cast(revision."REVENUE" AS DECIMAL(28, 8)) AS _measure__order_line__revenue_order_lines_amount
    FROM dab."view_ORDER_LINE_hist" AS revision
    QUALIFY row_number() OVER (
        PARTITION BY revision."ORDER_LINE_key"
        ORDER BY revision.eff_tmstp DESC
    ) = 1
),

ordered__order_line_is_for_product AS (
    SELECT
        revision.order_line_key AS order_line_key,
        revision._observed_at AS _observed_at,
        pair."PRODUCT_key" AS product_key
    FROM ordered__version AS revision
    LEFT JOIN dab."v_ORDER_LINE_IS_FOR_PRODUCT" AS pair
        ON
            revision.order_line_key = pair."ORDER_LINE_key"
            AND pair.rel_name = 'ORDER_LINE_IS_FOR_PRODUCT'
            AND pair.row_st = 'Y'
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_line_key, revision._observed_at
        ORDER BY
            CASE
                WHEN pair.eff_tmstp <= revision._observed_at
                    THEN pair.eff_tmstp
            END DESC NULLS LAST,
            pair.eff_tmstp ASC,
            pair.ver_tmstp DESC,
            pair."PRODUCT_key" ASC
    ) = 1
),

ordered__order_line_is_part_of_order AS (
    SELECT
        revision.order_line_key AS order_line_key,
        revision._observed_at AS _observed_at,
        pair."ORDER_key" AS order_key,
        cast(dated."PLACED_ON" AS DATE) AS _event_date
    FROM ordered__version AS revision
    LEFT JOIN dab."v_ORDER_LINE_IS_PART_OF_ORDER" AS pair
        ON
            revision.order_line_key = pair."ORDER_LINE_key"
            AND pair.rel_name = 'ORDER_LINE_IS_PART_OF_ORDER'
            AND pair.row_st = 'Y'
    LEFT JOIN dab."view_ORDER_hist" AS dated
        ON
            pair."ORDER_key" = dated."ORDER_key"
            AND dated."PLACED_ON" IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_line_key, revision._observed_at
        ORDER BY
            CASE
                WHEN pair.eff_tmstp <= revision._observed_at
                    THEN pair.eff_tmstp
            END DESC NULLS LAST,
            pair.eff_tmstp ASC,
            pair.ver_tmstp DESC,
            pair."ORDER_key" ASC,
            CASE
                WHEN dated.eff_tmstp <= revision._observed_at
                    THEN dated.eff_tmstp
            END DESC NULLS LAST,
            dated.eff_tmstp ASC
    ) = 1
),

ordered__product_is_in_category AS (
    SELECT
        revision.order_line_key AS order_line_key,
        revision._observed_at AS _observed_at,
        pair."CATEGORY_key" AS category_key
    FROM ordered__order_line_is_for_product AS revision
    LEFT JOIN dab."v_PRODUCT_IS_IN_CATEGORY" AS pair
        ON
            revision.product_key = pair."PRODUCT_key"
            AND pair.rel_name = 'PRODUCT_IS_IN_CATEGORY'
            AND pair.row_st = 'Y'
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_line_key, revision._observed_at
        ORDER BY
            CASE
                WHEN pair.eff_tmstp <= revision._observed_at
                    THEN pair.eff_tmstp
            END DESC NULLS LAST,
            pair.eff_tmstp ASC,
            pair.ver_tmstp DESC,
            pair."CATEGORY_key" ASC
    ) = 1
),

ordered__order_is_placed_by_customer AS (
    SELECT
        revision.order_line_key AS order_line_key,
        revision._observed_at AS _observed_at,
        pair."CUSTOMER_key" AS customer_key
    FROM ordered__order_line_is_part_of_order AS revision
    LEFT JOIN dab."v_ORDER_IS_PLACED_BY_CUSTOMER" AS pair
        ON
            revision.order_key = pair."ORDER_key"
            AND pair.rel_name = 'ORDER_IS_PLACED_BY_CUSTOMER'
            AND pair.row_st = 'Y'
    QUALIFY row_number() OVER (
        PARTITION BY revision.order_line_key, revision._observed_at
        ORDER BY
            CASE
                WHEN pair.eff_tmstp <= revision._observed_at
                    THEN pair.eff_tmstp
            END DESC NULLS LAST,
            pair.eff_tmstp ASC,
            pair.ver_tmstp DESC,
            pair."CUSTOMER_key" ASC
    ) = 1
),

ordered AS (
    SELECT
        revision.order_line_key AS order_line_key,
        revision._observed_at AS _observed_at,
        order_line_is_part_of_order._event_date AS _event_date,
        order_line_is_for_product.product_key AS product_key,
        order_line_is_part_of_order.order_key AS order_key,
        product_is_in_category.category_key AS category_key,
        order_is_placed_by_customer.customer_key AS customer_key,
        revision._measure__order_line__revenue_order_lines_amount AS _measure__order_line__revenue_order_lines_amount
    FROM ordered__version AS revision
    LEFT JOIN ordered__order_line_is_for_product AS order_line_is_for_product
        ON
            revision.order_line_key = order_line_is_for_product.order_line_key
            AND revision._observed_at = order_line_is_for_product._observed_at
    LEFT JOIN ordered__order_line_is_part_of_order AS order_line_is_part_of_order
        ON
            revision.order_line_key = order_line_is_part_of_order.order_line_key
            AND revision._observed_at = order_line_is_part_of_order._observed_at
    LEFT JOIN ordered__product_is_in_category AS product_is_in_category
        ON
            revision.order_line_key = product_is_in_category.order_line_key
            AND revision._observed_at = product_is_in_category._observed_at
    LEFT JOIN ordered__order_is_placed_by_customer AS order_is_placed_by_customer
        ON
            revision.order_line_key = order_is_placed_by_customer.order_line_key
            AND revision._observed_at = order_is_placed_by_customer._observed_at
    WHERE order_line_is_part_of_order._event_date IS NOT NULL
)

SELECT
    'order' AS _stage,
    'placed' AS _event,
    placed._event_date AS _event_date,
    TRUE AS _is_current,
    placed._observed_at AS _observed_at,
    placed.order_key AS order_key,
    placed.customer_key AS customer_key,
    cast(NULL AS VARCHAR) AS order_line_key,
    cast(NULL AS VARCHAR) AS product_key,
    cast(NULL AS VARCHAR) AS category_key,
    placed._measure__order__placed_orders_count AS _measure__order__placed_orders_count,
    placed._measure__order__freight_orders_amount AS _measure__order__freight_orders_amount,
    cast(NULL AS BIGINT) AS _measure__order__shipped_orders_count,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order__ship_lag_orders_days,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order_line__revenue_order_lines_amount
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
    cast(NULL AS VARCHAR) AS order_line_key,
    cast(NULL AS VARCHAR) AS product_key,
    cast(NULL AS VARCHAR) AS category_key,
    cast(NULL AS BIGINT) AS _measure__order__placed_orders_count,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order__freight_orders_amount,
    shipped._measure__order__shipped_orders_count AS _measure__order__shipped_orders_count,
    shipped._measure__order__ship_lag_orders_days AS _measure__order__ship_lag_orders_days,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order_line__revenue_order_lines_amount
FROM shipped AS shipped

UNION ALL

SELECT
    'order_line' AS _stage,
    'ordered' AS _event,
    ordered._event_date AS _event_date,
    TRUE AS _is_current,
    ordered._observed_at AS _observed_at,
    ordered.order_key AS order_key,
    ordered.customer_key AS customer_key,
    ordered.order_line_key AS order_line_key,
    ordered.product_key AS product_key,
    ordered.category_key AS category_key,
    cast(NULL AS BIGINT) AS _measure__order__placed_orders_count,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order__freight_orders_amount,
    cast(NULL AS BIGINT) AS _measure__order__shipped_orders_count,
    cast(NULL AS DECIMAL(28, 8)) AS _measure__order__ship_lag_orders_days,
    ordered._measure__order_line__revenue_order_lines_amount AS _measure__order_line__revenue_order_lines_amount
FROM ordered AS ordered;
