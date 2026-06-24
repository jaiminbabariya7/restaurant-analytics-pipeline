-- Silver: Cleaned order items joined with menu for cost data
{{ config(
    materialized='incremental',
    schema='silver',
    unique_key='surrogate_key',
    on_schema_change='append_new_columns'
) }}

WITH items AS (
    SELECT * FROM {{ ref('src_order_items') }}
),
orders AS (
    SELECT order_id, order_date, location_id, location_name, is_refund
    FROM {{ ref('stg_orders') }}
    {% if is_incremental() %}
        WHERE order_date > (SELECT MAX(order_date) FROM {{ this }})
    {% endif %}
),
menu AS (
    SELECT item_id, cost_price, subcategory FROM {{ ref('src_menu') }}
)

SELECT
    MD5(oi.order_item_id)                       AS surrogate_key,
    oi.order_item_id,
    oi.order_id,
    o.location_id,
    o.location_name,
    o.order_date,
    o.is_refund,
    oi.item_id,
    oi.item_name,
    oi.category,
    m.subcategory,
    oi.size,
    oi.quantity,
    oi.unit_price,
    m.cost_price,
    ROUND(m.cost_price * oi.quantity, 2)        AS total_cost,
    oi.discount_applied,
    oi.line_total,
    ROUND(oi.line_total - (m.cost_price * oi.quantity), 2) AS gross_profit,
    CASE WHEN oi.line_total > 0
         THEN ROUND((oi.line_total - m.cost_price * oi.quantity) / oi.line_total * 100, 2)
         ELSE 0 END                             AS margin_pct,
    oi.promo_id,
    CURRENT_TIMESTAMP                           AS _transformed_at
FROM items oi
INNER JOIN orders o ON oi.order_id = o.order_id
LEFT  JOIN menu   m ON oi.item_id  = m.item_id
WHERE oi.quantity > 0
  AND o.is_refund = FALSE
