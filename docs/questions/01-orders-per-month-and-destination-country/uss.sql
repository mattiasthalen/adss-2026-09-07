-- The answer, from the generated star schema. This is what the destination reads.
SELECT
    cal.month_label AS order_month,
    o.destination_country AS destination_country,
    cast(sum(b._measure__order__placed_orders_count) AS BIGINT) AS placed_orders_count
FROM dar__uss._bridge AS b
INNER JOIN dar__uss._calendar AS cal ON b._event_date = cal.date_key
INNER JOIN dar__uss."order" AS o ON b.order_key = o.order_key
WHERE b._event = 'placed'
GROUP BY cal.month_label, o.destination_country
ORDER BY order_month, destination_country
