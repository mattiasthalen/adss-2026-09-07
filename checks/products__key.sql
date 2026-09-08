-- Generated from das/contracts/products.yaml. Do not edit; edit the contract.
SELECT count(*) - count(DISTINCT latest.product_id) AS duplicates
FROM das__staged.products__current AS latest;
