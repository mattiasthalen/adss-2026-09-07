-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate.
CREATE OR REPLACE TABLE dar__uss._calendar AS
WITH bounds AS (
    SELECT
        min(b._event_date) AS first_date,
        max(b._event_date) AS last_date
    FROM dar__uss._bridge AS b
),

every_day AS (
    SELECT
        cast(d.day AS DATE) AS date_key
    FROM bounds AS bo
    CROSS JOIN range(
        bo.first_date, bo.last_date + INTERVAL 1 DAY, INTERVAL 1 DAY
    ) AS d (day)
)

SELECT
    d.date_key AS date_key,
    cast(year(d.date_key) AS INTEGER) AS year_number,
    cast(quarter(d.date_key) AS INTEGER) AS quarter_of_year,
    cast(month(d.date_key) AS INTEGER) AS month_of_year,
    cast(day(d.date_key) AS INTEGER) AS day_of_month,
    cast(date_trunc('year', d.date_key) AS DATE) AS year_start,
    cast(date_trunc('quarter', d.date_key) AS DATE) AS quarter_start,
    cast(date_trunc('month', d.date_key) AS DATE) AS month_start,
    strftime(d.date_key, '%Y') || '-Q' || cast(quarter(d.date_key) AS VARCHAR) AS quarter_label,
    strftime(d.date_key, '%Y-%m') AS month_label
FROM every_day AS d;
