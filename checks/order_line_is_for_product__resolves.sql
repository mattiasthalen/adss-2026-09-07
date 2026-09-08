-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS dangling
FROM dar__uss._bridge AS b
LEFT JOIN dar__uss.product AS t
    ON b.product_key = t.product_key
WHERE
    b._stage = 'order_line'
    AND b.product_key IS NOT NULL
    AND t.product_key IS NULL;
