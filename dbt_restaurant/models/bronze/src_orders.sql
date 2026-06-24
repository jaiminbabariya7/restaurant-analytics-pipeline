-- Bronze: Raw orders as-is from POS export
-- No transformations — immutable raw layer
{{ config(materialized='view', schema='bronze') }}

SELECT
    order_id,
    location_id,
    location_name,
    order_date::DATE        AS order_date,
    order_time::TIME        AS order_time,
    order_type,
    cashier_id,
    subtotal::DECIMAL(10,2) AS subtotal,
    discount_amount::DECIMAL(10,2) AS discount_amount,
    tax_amount::DECIMAL(10,2)      AS tax_amount,
    total_amount::DECIMAL(10,2)    AS total_amount,
    payment_method,
    is_refund::BOOLEAN      AS is_refund,
    CURRENT_TIMESTAMP       AS _ingested_at
FROM bronze_orders
