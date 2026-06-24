-- Bronze: Raw order line items as-is from POS export
{{ config(materialized='view', schema='bronze') }}

SELECT
    order_item_id,
    order_id,
    item_id,
    item_name,
    category,
    size,
    quantity::INT              AS quantity,
    unit_price::DECIMAL(10,2)  AS unit_price,
    discount_applied::DECIMAL(10,2) AS discount_applied,
    line_total::DECIMAL(10,2)  AS line_total,
    promo_id,
    CURRENT_TIMESTAMP          AS _ingested_at
FROM bronze_order_items
