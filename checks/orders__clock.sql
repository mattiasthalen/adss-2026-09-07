-- Generated from das/contracts/orders.yaml. Do not edit; edit the contract.
SELECT count(*) AS disagreements
FROM das__staged.orders AS staged
WHERE staged.extracted_on IS DISTINCT FROM cast(timezone('UTC', staged.extracted_at) AS DATE);
