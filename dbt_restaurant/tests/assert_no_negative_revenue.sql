-- Test: No negative revenue in gold layer (refunds already excluded)
SELECT COUNT(*) AS failures
FROM {{ ref('mart_menu_performance') }}
WHERE total_revenue < 0
