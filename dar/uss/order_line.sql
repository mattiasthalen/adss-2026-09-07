-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss.order_line AS
SELECT
    e."ORDER_LINE_key" AS order_line_key,
    e.eff_tmstp AS _observed_at,
    e."LINE_NUMBER" AS line_number,
    e."QUANTITY" AS quantity,
    e."AGREED_UNIT_PRICE" AS agreed_unit_price,
    e."DISCOUNT_RATE" AS discount_rate,
    e."REVENUE" AS revenue
FROM dab."view_ORDER_LINE_hist" AS e
QUALIFY row_number() OVER (
    PARTITION BY e."ORDER_LINE_key"
    ORDER BY e.eff_tmstp DESC
) = 1;
