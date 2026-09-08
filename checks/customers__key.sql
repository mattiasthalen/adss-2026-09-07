-- Generated from das/contracts/customers.yaml. Do not edit; edit the contract.
SELECT count(*) - count(DISTINCT latest.customer_id) AS duplicates
FROM das__staged.customers__current AS latest;
