{{ config(materialized='view') }}

SELECT
    item_id,
    item_name,
    category,
    subcategory,
    size,
    CAST(price AS DECIMAL(10,2))      AS price,
    CAST(cost_price AS DECIMAL(10,2)) AS cost_price,
    is_active::BOOLEAN                AS is_active
FROM {{ source('bronze', 'bronze_menu') }}
WHERE item_id IS NOT NULL
