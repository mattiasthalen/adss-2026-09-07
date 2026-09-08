-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss.category AS
SELECT
    e."CATEGORY_key" AS category_key,
    e.eff_tmstp AS _observed_at,
    e."CATEGORY_CODE" AS category_code,
    e."CATEGORY_NAME" AS category_name,
    e."CATEGORY_DESCRIPTION" AS category_description
FROM dab."view_CATEGORY_hist" AS e
QUALIFY row_number() OVER (
    PARTITION BY e."CATEGORY_key"
    ORDER BY e.eff_tmstp DESC
) = 1;
