-- The control. Straight from what the source sent, bypassing the business model and the
-- star schema. It may not mention dab or dar__uss: independence is the whole value.
--
-- A line has no date of its own, so the month comes from the order it is part of -- which is
-- the same join the star schema walks, spelled in the source's words. Orders with no line
-- contribute nothing and lines whose order is missing are dropped, which is what the star
-- schema does too: a row whose inherited date does not resolve gets no bridge row.
SELECT
    strftime(o.order_date, '%Y-%m') AS order_month,
    cast(sum(d.quantity * d.unit_price * (1 - d.discount)) AS DECIMAL(28, 8))
        AS revenue_order_lines_amount
FROM das__staged.order_details__current AS d
INNER JOIN das__staged.orders__current AS o ON d.order_id = o.order_id
GROUP BY strftime(o.order_date, '%Y-%m')
ORDER BY order_month
