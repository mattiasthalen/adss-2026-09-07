-- Generated from das/contracts/categories.yaml. Do not edit; edit the contract.
SELECT count(*) - count(DISTINCT latest.category_id) AS duplicates
FROM das__staged.categories__current AS latest;
