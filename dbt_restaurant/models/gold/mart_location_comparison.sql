-- Gold: Location Comparison — Revenue, Orders, Avg Ticket across 5 locations
{{ config(materialized='table', schema='gold') }}

WITH monthly AS (
    SELECT
        o.location_id,
        o.location_name,
        o.order_year,
        o.order_month,
        COUNT(DISTINCT o.order_id)              AS total_orders,
        ROUND(SUM(o.total_amount), 2)           AS total_revenue,
        ROUND(AVG(o.total_amount), 2)           AS avg_ticket,
        ROUND(SUM(o.discount_amount), 2)        AS total_discounts,
        ROUND(SUM(oi.gross_profit), 2)          AS total_gross_profit,
        ROUND(AVG(oi.margin_pct), 2)            AS avg_margin_pct,
        COUNT(DISTINCT CASE WHEN o.order_type='Dine-In'  THEN o.order_id END) AS dine_in_orders,
        COUNT(DISTINCT CASE WHEN o.order_type='Takeout'  THEN o.order_id END) AS takeout_orders,
        COUNT(DISTINCT CASE WHEN o.order_type='Delivery' THEN o.order_id END) AS delivery_orders
    FROM {{ ref('stg_orders') }} o
    LEFT JOIN (
        SELECT order_id, SUM(gross_profit) AS gross_profit, AVG(margin_pct) AS margin_pct
        FROM {{ ref('stg_order_items') }}
        GROUP BY order_id
    ) oi ON o.order_id = oi.order_id
    WHERE o.is_refund = FALSE
    GROUP BY 1,2,3,4
)

SELECT
    location_id,
    location_name,
    order_year,
    order_month,
    total_orders,
    total_revenue,
    avg_ticket,
    total_discounts,
    total_gross_profit,
    avg_margin_pct,
    dine_in_orders,
    takeout_orders,
    delivery_orders,
    ROUND(total_revenue / NULLIF(SUM(total_revenue) OVER (PARTITION BY order_year, order_month), 0) * 100, 2) AS revenue_share_pct
FROM monthly
ORDER BY order_year, order_month, total_revenue DESC
