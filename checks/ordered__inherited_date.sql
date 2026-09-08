-- Generated from dab/uss.yaml. Do not edit; regenerate with `adss dar generate`.
SELECT count(*) AS disagreements
FROM dar__uss._bridge AS inheriting
INNER JOIN dar__uss._bridge AS dating
    ON
        inheriting.order_key = dating.order_key
        AND dating._event = 'placed'
WHERE
    inheriting._event = 'ordered'
    AND inheriting._event_date != dating._event_date;
