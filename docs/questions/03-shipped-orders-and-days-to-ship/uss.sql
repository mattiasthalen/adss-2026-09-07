-- The answer, from the generated star schema. This is what the destination reads.
--
-- Two additive measures, and no ratio. The wait of a typical order is the second divided by
-- the first, and that division belongs to whoever asks -- conventions section 2. It also
-- keeps this comparison exact: every value here is a count or an exact decimal, and a float
-- would make the two answers disagree by a bit, since summing doubles is order-dependent.
SELECT
    cal.month_label AS shipping_month,
    cast(sum(b._measure__order__shipped_orders_count) AS BIGINT) AS shipped_orders_count,
    cast(sum(b._measure__order__ship_lag_orders_days) AS DECIMAL(28, 8)) AS ship_lag_orders_days
FROM dar__uss._bridge AS b
INNER JOIN dar__uss._calendar AS cal ON b._event_date = cal.date_key
WHERE b._event = 'shipped'
GROUP BY cal.month_label
ORDER BY shipping_month
