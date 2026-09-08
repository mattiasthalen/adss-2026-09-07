-- The answer, from the generated star schema. This is what the destination reads.
--
-- One join to reach the category, and the bridge has already walked to it: a line's stage
-- carries the key of everything it reaches at any depth, so the two hops the control query
-- spells out by hand are not spelled here at all. That is the whole of what this layer buys,
-- and it is why the two queries agreeing means something. ADR 0014.
SELECT
    cal.quarter_label AS order_quarter,
    ca.category_name AS product_category,
    cast(sum(b._measure__order_line__revenue_order_lines_amount) AS DECIMAL(28, 8))
        AS revenue_order_lines_amount
FROM dar__uss._bridge AS b
INNER JOIN dar__uss._calendar AS cal ON b._event_date = cal.date_key
INNER JOIN dar__uss.category AS ca ON b.category_key = ca.category_key
WHERE b._event = 'ordered'
GROUP BY cal.quarter_label, ca.category_name
ORDER BY order_quarter, product_category
