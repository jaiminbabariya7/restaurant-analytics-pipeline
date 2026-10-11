-- Fails (returns rows) if a non-refund order in Silver has a negative total
SELECT order_id, total_amount
FROM {{ ref('stg_orders') }}
WHERE is_refund = FALSE
  AND total_amount < 0
