-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS unloaded
FROM (SELECT 1 AS declared) AS edge
WHERE NOT EXISTS (
    SELECT 1
    FROM dab."v_ORDER_LINE_IS_PART_OF_ORDER" AS pair
    WHERE
        pair.rel_name = 'ORDER_LINE_IS_PART_OF_ORDER'
        AND pair.row_st = 'Y'
);
