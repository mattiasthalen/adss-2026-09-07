-- The control. Straight from what the source sent, bypassing the business model and the
-- star schema. It may not mention dab or dar__uss: independence is the whole value.
--
-- Three joins, spelled in the source's own words, because the source has no notion of a chain:
-- a line names a product, a product names a category, and neither the line nor the order says
-- anything about a category at all. That is the same walk the star schema does in the
-- generator, done here by hand -- which is what makes the agreement worth having.
SELECT
    strftime(o.order_date, '%Y') || '-Q' || cast(quarter(o.order_date) AS VARCHAR)
        AS order_quarter,
    ca.category_name AS product_category,
    cast(sum(d.quantity * d.unit_price * (1 - d.discount)) AS DECIMAL(28, 8))
        AS revenue_order_lines_amount
FROM das__staged.order_details__current AS d
INNER JOIN das__staged.orders__current AS o ON d.order_id = o.order_id
INNER JOIN das__staged.products__current AS p ON d.product_id = p.product_id
INNER JOIN das__staged.categories__current AS ca ON p.category_id = ca.category_id
GROUP BY
    strftime(o.order_date, '%Y') || '-Q' || cast(quarter(o.order_date) AS VARCHAR),
    ca.category_name
ORDER BY order_quarter, product_category
