-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS unloaded
FROM (SELECT 1 AS declared) AS edge
WHERE NOT EXISTS (
    SELECT 1
    FROM dab."v_ORDER_IS_PLACED_BY_CUSTOMER" AS pair
    WHERE
        pair.rel_name = 'ORDER_IS_PLACED_BY_CUSTOMER'
        AND pair.row_st = 'Y'
);
