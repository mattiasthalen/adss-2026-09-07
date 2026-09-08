-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS unloaded
FROM (SELECT 1 AS declared) AS edge
WHERE NOT EXISTS (
    SELECT 1
    FROM dab."v_PRODUCT_IS_IN_CATEGORY" AS pair
    WHERE
        pair.rel_name = 'PRODUCT_IS_IN_CATEGORY'
        AND pair.row_st = 'Y'
);
