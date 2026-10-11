-- Fails (returns rows) if any menu item has no valid menu-engineering class
SELECT item_id, menu_class
FROM {{ ref('mart_menu_performance') }}
WHERE menu_class IS NULL
   OR menu_class NOT IN ('Star', 'Plow Horse', 'Puzzle', 'Dog')
