-- Generated from das/contracts/orders.yaml. Do not edit; edit the contract.
CREATE OR REPLACE VIEW das__raw.orders AS
SELECT
    landed.payload AS payload,
    landed.source_system AS source_system,
    landed.source_entity AS source_entity,
    landed.source_url AS source_url,
    landed.extracted_on AS extracted_on,
    landed._dlt_load_id AS _dlt_load_id,
    landed._dlt_id AS _dlt_id
FROM read_parquet(
    '/home/user/adss-2026-09-07/das/lake/das__raw/orders/extracted_on=*/*.parquet',
    hive_partitioning => true,
    hive_types => { 'extracted_on': 'DATE' },
    union_by_name => true
) AS landed;

-- Generated from das/contracts/orders.yaml. Do not edit; edit the contract.
CREATE OR REPLACE VIEW das__staged.orders AS
SELECT
    cast(landed.payload ->> '$.OrderId' AS INTEGER) AS order_id,
    landed.payload ->> '$.CustomerId' AS customer_id,
    cast(landed.payload ->> '$.EmployeeId' AS INTEGER) AS employee_id,
    cast(landed.payload ->> '$.OrderDate' AS DATE) AS order_date,
    cast(landed.payload ->> '$.RequiredDate' AS DATE) AS required_date,
    cast(landed.payload ->> '$.ShippedDate' AS DATE) AS shipped_date,
    cast(landed.payload ->> '$.ShipVia' AS INTEGER) AS ship_via,
    cast(landed.payload ->> '$.Freight' AS DECIMAL(18, 4)) AS freight,
    landed.payload ->> '$.ShipName' AS ship_name,
    landed.payload ->> '$.ShipAddress' AS ship_address,
    landed.payload ->> '$.ShipCity' AS ship_city,
    landed.payload ->> '$.ShipRegion' AS ship_region,
    landed.payload ->> '$.ShipPostalCode' AS ship_postal_code,
    landed.payload ->> '$.ShipCountry' AS ship_country,
    landed.source_system AS source_system,
    landed.source_entity AS source_entity,
    landed.source_url AS source_url,
    to_timestamp(cast(landed._dlt_load_id AS DOUBLE)) AS extracted_at,
    landed.extracted_on AS extracted_on
FROM das__raw.orders AS landed;

-- Generated from das/contracts/orders.yaml. Do not edit; edit the contract.
CREATE OR REPLACE VIEW das__staged.orders__current AS
SELECT
    staged.order_id AS order_id,
    staged.customer_id AS customer_id,
    staged.employee_id AS employee_id,
    staged.order_date AS order_date,
    staged.required_date AS required_date,
    staged.shipped_date AS shipped_date,
    staged.ship_via AS ship_via,
    staged.freight AS freight,
    staged.ship_name AS ship_name,
    staged.ship_address AS ship_address,
    staged.ship_city AS ship_city,
    staged.ship_region AS ship_region,
    staged.ship_postal_code AS ship_postal_code,
    staged.ship_country AS ship_country,
    staged.source_system AS source_system,
    staged.source_entity AS source_entity,
    staged.source_url AS source_url,
    staged.extracted_at AS extracted_at,
    staged.extracted_on AS extracted_on
FROM das__staged.orders AS staged
QUALIFY row_number() OVER (
    PARTITION BY staged.order_id
    ORDER BY staged.extracted_at DESC
) = 1;
