-- Gold: Menu Engineering Matrix — Star/Plow Horse/Puzzle/Dog classification
{{ config(materialized='table', schema='gold') }}

WITH item_stats AS (
    SELECT
        item_id,
        item_name,
        category,
        subcategory,
        size,
        SUM(quantity)                           AS total_units_sold,
        COUNT(DISTINCT order_id)                AS total_orders,
        ROUND(SUM(line_total), 2)               AS total_revenue,
        ROUND(SUM(gross_profit), 2)             AS total_gross_profit,
        ROUND(AVG(margin_pct), 2)               AS avg_margin_pct,
        ROUND(AVG(unit_price), 2)               AS avg_selling_price,
        ROUND(AVG(cost_price), 2)               AS avg_cost_price
    FROM {{ ref('stg_order_items') }}
    GROUP BY 1,2,3,4,5
),

thresholds AS (
    SELECT
        AVG(total_units_sold) AS avg_units,
        AVG(avg_margin_pct)   AS avg_margin
    FROM item_stats
),

classified AS (
    SELECT
        s.*,
        t.avg_units,
        t.avg_margin,
        CASE
            WHEN s.total_units_sold >= t.avg_units AND s.avg_margin_pct >= t.avg_margin THEN 'Star'
            WHEN s.total_units_sold >= t.avg_units AND s.avg_margin_pct <  t.avg_margin THEN 'Plow Horse'
            WHEN s.total_units_sold <  t.avg_units AND s.avg_margin_pct >= t.avg_margin THEN 'Puzzle'
            ELSE 'Dog'
        END AS menu_class,
        CASE
            WHEN s.total_units_sold >= t.avg_units AND s.avg_margin_pct >= t.avg_margin THEN 'Keep & Promote'
            WHEN s.total_units_sold >= t.avg_units AND s.avg_margin_pct <  t.avg_margin THEN 'Increase Price'
            WHEN s.total_units_sold <  t.avg_units AND s.avg_margin_pct >= t.avg_margin THEN 'Remarket'
            ELSE 'Consider Removing'
        END AS recommendation
    FROM item_stats s CROSS JOIN thresholds t
)

SELECT * FROM classified ORDER BY total_revenue DESC
