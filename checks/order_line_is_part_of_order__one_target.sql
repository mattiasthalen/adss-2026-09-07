-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS ambiguities
FROM (
    SELECT
        pair."ORDER_LINE_key" AS source_key,
        pair.eff_tmstp AS observed_at
    FROM dab."v_ORDER_LINE_IS_PART_OF_ORDER" AS pair
    WHERE
        pair.rel_name = 'ORDER_LINE_IS_PART_OF_ORDER'
        AND pair.row_st = 'Y'
    GROUP BY pair."ORDER_LINE_key", pair.eff_tmstp
    HAVING count(DISTINCT pair."ORDER_key") > 1
) AS tied;
