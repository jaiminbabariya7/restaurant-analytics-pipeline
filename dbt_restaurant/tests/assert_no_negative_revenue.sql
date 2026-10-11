-- Fails (returns rows) if any menu item has negative revenue (refunds are excluded upstream)
SELECT item_id, total_revenue
FROM {{ ref('mart_menu_performance') }}
WHERE total_revenue < 0
