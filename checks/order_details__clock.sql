-- Generated from das/contracts/order_details.yaml. Do not edit; edit the contract.
SELECT count(*) AS disagreements
FROM das__staged.order_details AS staged
WHERE staged.extracted_on IS DISTINCT FROM cast(timezone('UTC', staged.extracted_at) AS DATE);
