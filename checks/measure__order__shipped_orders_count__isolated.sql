-- Generated from dab/uss.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS leaked
FROM dar__uss._bridge AS b
WHERE
    b._event != 'shipped'
    AND b._measure__order__shipped_orders_count IS NOT NULL;
