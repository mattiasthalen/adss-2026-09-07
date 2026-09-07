-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS dangling
FROM dar__uss._bridge AS b
LEFT JOIN dar__uss.customer AS t
    ON b.customer_key = t.customer_key
WHERE
    b._stage = 'order'
    AND b.customer_key IS NOT NULL
    AND t.customer_key IS NULL;
