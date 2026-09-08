-- The control. Straight from what the source sent, bypassing the business model and the
-- star schema. It may not mention dab or dar__uss: independence is the whole value.
SELECT
    strftime(o.order_date, '%Y') || '-Q' || cast(quarter(o.order_date) AS VARCHAR)
        AS order_quarter,
    c.country AS customer_country,
    cast(sum(o.freight) AS DECIMAL(28, 8)) AS freight_orders_amount
FROM das__staged.orders__current AS o
LEFT JOIN das__staged.customers__current AS c ON o.customer_id = c.customer_id
WHERE o.order_date IS NOT NULL
GROUP BY
    strftime(o.order_date, '%Y') || '-Q' || cast(quarter(o.order_date) AS VARCHAR),
    c.country
ORDER BY order_quarter, customer_country
