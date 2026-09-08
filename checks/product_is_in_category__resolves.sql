-- Generated from dab/model.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS dangling
FROM dar__uss._bridge AS b
LEFT JOIN dar__uss.category AS t
    ON b.category_key = t.category_key
WHERE
    b._stage = 'product'
    AND b.category_key IS NOT NULL
    AND t.category_key IS NULL;
