-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS ambiguities
FROM (
    SELECT
        pair."PRODUCT_key" AS source_key,
        pair.eff_tmstp AS observed_at
    FROM dab."v_PRODUCT_IS_IN_CATEGORY" AS pair
    WHERE
        pair.rel_name = 'PRODUCT_IS_IN_CATEGORY'
        AND pair.row_st = 'Y'
    GROUP BY pair."PRODUCT_key", pair.eff_tmstp
    HAVING count(DISTINCT pair."CATEGORY_key") > 1
) AS tied;
