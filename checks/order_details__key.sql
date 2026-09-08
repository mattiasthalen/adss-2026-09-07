-- Generated from das/contracts/order_details.yaml. Do not edit; edit the contract.
SELECT count(*) - count(DISTINCT row(latest.order_id, latest.product_id)) AS duplicates
FROM das__staged.order_details__current AS latest;
