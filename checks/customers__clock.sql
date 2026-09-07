-- Generated from das/contracts/customers.yaml. Do not edit; edit the contract.
SELECT count(*) AS disagreements
FROM das__staged.customers AS staged
WHERE staged.extracted_on <> cast(timezone('UTC', staged.extracted_at) AS DATE);
