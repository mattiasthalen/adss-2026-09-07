-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS ambiguities
FROM (
    SELECT
        pair."ORDER_key" AS source_key,
        pair.eff_tmstp AS observed_at
    FROM dab."v_ORDER_IS_PLACED_BY_CUSTOMER" AS pair
    WHERE
        pair.rel_name = 'ORDER_IS_PLACED_BY_CUSTOMER'
        AND pair.row_st = 'Y'
    GROUP BY pair."ORDER_key", pair.eff_tmstp
    HAVING count(DISTINCT pair."CUSTOMER_key") > 1
) AS tied;
