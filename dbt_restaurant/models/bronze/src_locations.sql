{{ config(materialized='view') }}

SELECT
    location_id,
    location_name,
    address,
    seating_capacity::INT     AS seating_capacity,
    opening_date::DATE        AS opening_date,
    manager_name,
    phone,
    is_active::BOOLEAN        AS is_active
FROM {{ source('bronze', 'bronze_locations') }}
WHERE location_id IS NOT NULL
