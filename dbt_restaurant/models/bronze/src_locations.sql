{{ config(materialized='view') }}

SELECT
    location_id,
    location_name,
    city,
    province,
    postal_code,
    phone,
    opened_date::DATE AS opened_date
FROM {{ source('bronze', 'bronze_locations') }}
WHERE location_id IS NOT NULL
