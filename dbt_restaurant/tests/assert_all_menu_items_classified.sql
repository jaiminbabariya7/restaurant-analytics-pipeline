-- Test: Every active menu item must have a menu engineering classification
SELECT COUNT(*) AS failures
FROM {{ ref('mart_menu_performance') }}
WHERE menu_class NOT IN ('Star', 'Plow Horse', 'Puzzle', 'Dog')
