-- Generated from das/contracts/orders.yaml. Do not edit; edit the contract.
SELECT count(*) - count(DISTINCT latest.order_id) AS duplicates
FROM das__staged.orders__current AS latest;
