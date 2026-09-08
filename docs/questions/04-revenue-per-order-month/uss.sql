-- The answer, from the generated star schema. This is what the destination reads.
--
-- One stage, at the grain of the line. The order's own measures are on other rows of the same
-- bridge and are null here, so this sum cannot pick up a freight charge however the query is
-- grouped -- which is the property the whole shared star schema rests on, and slice four is
-- the first slice with two grains for it to be true of. ADR 0012.
SELECT
    cal.month_label AS order_month,
    cast(sum(b._measure__order_line__revenue_order_lines_amount) AS DECIMAL(28, 8))
        AS revenue_order_lines_amount
FROM dar__uss._bridge AS b
INNER JOIN dar__uss._calendar AS cal ON b._event_date = cal.date_key
WHERE b._event = 'ordered'
GROUP BY cal.month_label
ORDER BY order_month
