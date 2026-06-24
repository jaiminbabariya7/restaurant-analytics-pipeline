-- Gold: Revenue Trends — MoM growth, WoW, running totals
{{ config(materialized='table', schema='gold') }}

WITH monthly AS (
    SELECT
        location_id,
        location_name,
        order_year,
        order_month,
        COUNT(DISTINCT order_id)                AS total_orders,
        ROUND(SUM(total_amount), 2)             AS total_revenue,
        ROUND(SUM(discount_amount), 2)          AS total_discounts,
        ROUND(AVG(total_amount), 2)             AS avg_ticket
    FROM {{ ref('stg_orders') }}
    WHERE is_refund = FALSE
    GROUP BY 1,2,3,4
)

SELECT
    *,
    LAG(total_revenue) OVER (
        PARTITION BY location_id ORDER BY order_year, order_month
    )                                           AS prev_month_revenue,
    ROUND(
        (total_revenue - LAG(total_revenue) OVER (
            PARTITION BY location_id ORDER BY order_year, order_month
        )) / NULLIF(LAG(total_revenue) OVER (
            PARTITION BY location_id ORDER BY order_year, order_month
        ), 0) * 100, 2
    )                                           AS mom_growth_pct,
    SUM(total_revenue) OVER (
        PARTITION BY location_id, order_year ORDER BY order_month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                           AS ytd_revenue,
    SUM(total_revenue) OVER (
        PARTITION BY order_year, order_month
    )                                           AS all_locations_revenue
FROM monthly
ORDER BY location_id, order_year, order_month
