-- The control. Straight from what the source sent, bypassing the business model and the
-- star schema. It may not mention dab or dar__uss: independence is the whole value.
SELECT
    strftime(o.shipped_date, '%Y-%m') AS shipping_month,
    count(*) AS shipped_orders_count,
    cast(sum(date_diff('day', o.order_date, o.shipped_date)) AS DECIMAL(28, 8))
        AS ship_lag_orders_days
FROM das__staged.orders__current AS o
WHERE o.shipped_date IS NOT NULL
GROUP BY strftime(o.shipped_date, '%Y-%m')
ORDER BY shipping_month
