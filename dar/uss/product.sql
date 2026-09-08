-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss.product AS
SELECT
    e."PRODUCT_key" AS product_key,
    e.eff_tmstp AS _observed_at,
    e."PRODUCT_CODE" AS product_code,
    e."PRODUCT_NAME" AS product_name,
    e."LIST_PRICE" AS list_price
FROM dab."view_PRODUCT_hist" AS e
QUALIFY row_number() OVER (
    PARTITION BY e."PRODUCT_key"
    ORDER BY e.eff_tmstp DESC
) = 1;
