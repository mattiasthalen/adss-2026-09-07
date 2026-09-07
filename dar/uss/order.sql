-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss."order" AS
SELECT
    e."ORDER_key" AS order_key,
    e.eff_tmstp AS _observed_at,
    e."ORDER_NUMBER" AS order_number,
    e."PLACED_ON" AS placed_on,
    e."DESTINATION_COUNTRY" AS destination_country,
    e."FREIGHT_CHARGE" AS freight_charge
FROM dab."view_ORDER_hist" AS e
QUALIFY row_number() OVER (
    PARTITION BY e."ORDER_key"
    ORDER BY e.eff_tmstp DESC
) = 1;
