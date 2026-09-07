-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss.customer AS
SELECT
    e."CUSTOMER_key" AS customer_key,
    e.eff_tmstp AS _observed_at,
    e."CUSTOMER_CODE" AS customer_code,
    e."TRADING_NAME" AS trading_name,
    e."BASED_IN_COUNTRY" AS based_in_country
FROM dab."view_CUSTOMER_hist" AS e
QUALIFY row_number() OVER (
    PARTITION BY e."CUSTOMER_key"
    ORDER BY e.eff_tmstp DESC
) = 1;
