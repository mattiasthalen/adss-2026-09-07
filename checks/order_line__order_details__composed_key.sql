-- Generated from dab/mappings/. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS collisions
FROM (
    SELECT
        count(DISTINCT row(order_id, product_id)) AS parts,
        count(DISTINCT cast(order_id AS VARCHAR) || '-' || cast(product_id AS VARCHAR)) AS composed
    FROM das__staged.order_details__current
) AS counted
WHERE counted.parts != counted.composed;
