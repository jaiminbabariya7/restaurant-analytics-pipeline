-- Silver: Cleaned & conformed orders
-- Filters refunds, adds time dimensions, surrogate key
{{ config(
    materialized='incremental',
    schema='silver',
    unique_key='surrogate_key',
    on_schema_change='append_new_columns'
) }}

WITH source AS (
    SELECT * FROM {{ ref('src_orders') }}
    {% if is_incremental() %}
        WHERE order_date > (SELECT MAX(order_date) FROM {{ this }})
    {% endif %}
),

enriched AS (
    SELECT
        MD5(order_id)                           AS surrogate_key,
        order_id,
        location_id,
        location_name,
        order_date,
        order_time,
        EXTRACT(YEAR  FROM order_date)::INT     AS order_year,
        EXTRACT(MONTH FROM order_date)::INT     AS order_month,
        EXTRACT(WEEK  FROM order_date)::INT     AS order_week,
        EXTRACT(DOW   FROM order_date)::INT     AS day_of_week,
        CASE EXTRACT(DOW FROM order_date)
            WHEN 0 THEN 'Sunday'
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
        END                                     AS day_name,
        CASE WHEN EXTRACT(DOW FROM order_date) IN (5,6) THEN TRUE ELSE FALSE END AS is_weekend,
        EXTRACT(HOUR FROM order_time)::INT      AS order_hour,
        CASE
            WHEN EXTRACT(HOUR FROM order_time) BETWEEN 11 AND 14 THEN 'Lunch'
            WHEN EXTRACT(HOUR FROM order_time) BETWEEN 15 AND 16 THEN 'Afternoon'
            WHEN EXTRACT(HOUR FROM order_time) BETWEEN 17 AND 21 THEN 'Dinner'
            ELSE 'Late Night'
        END                                     AS day_part,
        order_type,
        cashier_id,
        subtotal,
        discount_amount,
        tax_amount,
        total_amount,
        payment_method,
        is_refund,
        CURRENT_TIMESTAMP                       AS _transformed_at
    FROM source
    WHERE order_id IS NOT NULL
      AND location_id IN ('LOC-GRM','LOC-WTD','LOC-DUN','LOC-WIN','LOC-PTC')
)

SELECT * FROM enriched
