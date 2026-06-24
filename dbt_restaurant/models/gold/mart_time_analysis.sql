-- Gold: Time Analysis — Hour x Day heatmap, day-part revenue, seasonality
{{ config(materialized='table', schema='gold') }}

SELECT
    location_id,
    location_name,
    order_year,
    order_month,
    day_of_week,
    day_name,
    is_weekend,
    order_hour,
    day_part,
    COUNT(DISTINCT order_id)        AS total_orders,
    ROUND(SUM(total_amount), 2)     AS total_revenue,
    ROUND(AVG(total_amount), 2)     AS avg_ticket,
    ROUND(SUM(discount_amount), 2)  AS total_discounts
FROM {{ ref('stg_orders') }}
WHERE is_refund = FALSE
GROUP BY 1,2,3,4,5,6,7,8,9
ORDER BY order_year, order_month, day_of_week, order_hour
