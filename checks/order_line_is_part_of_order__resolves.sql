-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS dangling
FROM dar__uss._bridge AS b
LEFT JOIN dar__uss."order" AS t
    ON b.order_key = t.order_key
WHERE
    b._stage = 'order_line'
    AND b.order_key IS NOT NULL
    AND t.order_key IS NULL;
