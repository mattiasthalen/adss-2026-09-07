-- The answer, from the generated star schema. This is what the destination reads.
SELECT
    cal.quarter_label AS order_quarter,
    cu.based_in_country AS customer_country,
    cast(sum(b._measure__order__freight_orders_amount) AS DECIMAL(28, 8))
        AS freight_orders_amount
FROM dar__uss._bridge AS b
INNER JOIN dar__uss._calendar AS cal ON b._event_date = cal.date_key
LEFT JOIN dar__uss.customer AS cu ON b.customer_key = cu.customer_key
WHERE b._event = 'placed'
GROUP BY cal.quarter_label, cu.based_in_country
ORDER BY order_quarter, customer_country
