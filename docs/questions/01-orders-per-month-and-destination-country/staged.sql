-- The control. Straight from what the source sent, bypassing the business model and the
-- star schema. It may not mention dab or dar__uss: independence is the whole value.
SELECT
    strftime(o.order_date, '%Y-%m') AS order_month,
    o.ship_country AS destination_country,
    count(*) AS placed_orders_count
FROM das__staged.orders__current AS o
WHERE o.order_date IS NOT NULL
GROUP BY strftime(o.order_date, '%Y-%m'), o.ship_country
ORDER BY order_month, destination_country
