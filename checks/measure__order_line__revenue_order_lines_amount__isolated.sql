-- Generated from dab/uss.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS leaked
FROM dar__uss._bridge AS b
WHERE
    b._event != 'ordered'
    AND b._measure__order_line__revenue_order_lines_amount IS NOT NULL;
