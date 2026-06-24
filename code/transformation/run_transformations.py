"""
Restaurant Co. — Transformation Runner
Executes Bronze → Silver → Gold transformations directly in DuckDB
(mirrors dbt model logic for local execution)
"""

import duckdb
import os
import logging
from datetime import datetime

BASE    = os.environ.get("PIPELINE_HOME", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.environ.get("RESTAURANT_DB_PATH", f"{BASE}/data/bronze/restaurant_bronze.duckdb")
LOG_FILE= f"{BASE}/output/logs/transform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def run():
    log.info("=" * 60)
    log.info("  TRANSFORMATION LAYER — Restaurant Co.")
    log.info(f"  Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    conn = duckdb.connect(DB_PATH)

    # ── SILVER: stg_orders ──────────────────────────────────────────────────
    log.info("Running silver.stg_orders ...")
    conn.execute("DROP TABLE IF EXISTS silver_stg_orders")
    conn.execute("""
    CREATE TABLE silver_stg_orders AS
    SELECT
        MD5(order_id)                           AS surrogate_key,
        order_id,
        location_id,
        location_name,
        order_date::DATE                        AS order_date,
        order_time::TIME                        AS order_time,
        EXTRACT(YEAR  FROM order_date::DATE)::INT  AS order_year,
        EXTRACT(MONTH FROM order_date::DATE)::INT  AS order_month,
        EXTRACT(WEEK  FROM order_date::DATE)::INT  AS order_week,
        EXTRACT(DOW   FROM order_date::DATE)::INT  AS day_of_week,
        CASE EXTRACT(DOW FROM order_date::DATE)
            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'   WHEN 6 THEN 'Saturday'
        END                                     AS day_name,
        CASE WHEN EXTRACT(DOW FROM order_date::DATE) IN (5,6) THEN TRUE ELSE FALSE END AS is_weekend,
        EXTRACT(HOUR FROM order_time::TIME)::INT AS order_hour,
        CASE
            WHEN EXTRACT(HOUR FROM order_time::TIME) BETWEEN 11 AND 14 THEN 'Lunch'
            WHEN EXTRACT(HOUR FROM order_time::TIME) BETWEEN 15 AND 16 THEN 'Afternoon'
            WHEN EXTRACT(HOUR FROM order_time::TIME) BETWEEN 17 AND 21 THEN 'Dinner'
            ELSE 'Late Night'
        END                                     AS day_part,
        order_type, cashier_id,
        subtotal::DECIMAL(10,2)                 AS subtotal,
        discount_amount::DECIMAL(10,2)          AS discount_amount,
        tax_amount::DECIMAL(10,2)               AS tax_amount,
        total_amount::DECIMAL(10,2)             AS total_amount,
        payment_method, is_refund::BOOLEAN      AS is_refund,
        CURRENT_TIMESTAMP                       AS _transformed_at
    FROM bronze_orders
    WHERE order_id IS NOT NULL
      AND location_id IN ('LOC-GRM','LOC-WTD','LOC-DUN','LOC-WIN','LOC-PTC')
    """)
    n = conn.execute("SELECT COUNT(*) FROM silver_stg_orders").fetchone()[0]
    log.info(f"  ✓ silver_stg_orders: {n:,} rows")

    # ── SILVER: stg_order_items ─────────────────────────────────────────────
    log.info("Running silver.stg_order_items ...")
    conn.execute("DROP TABLE IF EXISTS silver_stg_order_items")
    conn.execute("""
    CREATE TABLE silver_stg_order_items AS
    SELECT
        MD5(oi.order_item_id)                   AS surrogate_key,
        oi.order_item_id, oi.order_id,
        o.location_id, o.location_name, o.order_date, o.is_refund,
        oi.item_id, oi.item_name, oi.category,
        m.subcategory, oi.size,
        oi.quantity::INT                        AS quantity,
        oi.unit_price::DECIMAL(10,2)            AS unit_price,
        m.cost_price::DECIMAL(10,2)             AS cost_price,
        ROUND(m.cost_price::DECIMAL * oi.quantity::INT, 2) AS total_cost,
        oi.discount_applied::DECIMAL(10,2)      AS discount_applied,
        oi.line_total::DECIMAL(10,2)            AS line_total,
        ROUND(oi.line_total::DECIMAL - (m.cost_price::DECIMAL * oi.quantity::INT), 2) AS gross_profit,
        CASE WHEN oi.line_total::DECIMAL > 0
             THEN ROUND((oi.line_total::DECIMAL - m.cost_price::DECIMAL * oi.quantity::INT)
                        / oi.line_total::DECIMAL * 100, 2)
             ELSE 0 END                         AS margin_pct,
        oi.promo_id,
        CURRENT_TIMESTAMP                       AS _transformed_at
    FROM bronze_order_items oi
    INNER JOIN silver_stg_orders o ON oi.order_id = o.order_id
    LEFT  JOIN bronze_menu m       ON oi.item_id  = m.item_id
    WHERE oi.quantity::INT > 0 AND o.is_refund = FALSE
    """)
    n = conn.execute("SELECT COUNT(*) FROM silver_stg_order_items").fetchone()[0]
    log.info(f"  ✓ silver_stg_order_items: {n:,} rows")

    # ── GOLD: mart_menu_performance ─────────────────────────────────────────
    log.info("Running gold.mart_menu_performance ...")
    conn.execute("DROP TABLE IF EXISTS gold_mart_menu_performance")
    conn.execute("""
    CREATE TABLE gold_mart_menu_performance AS
    WITH item_stats AS (
        SELECT item_id, item_name, category, subcategory, size,
            SUM(quantity)               AS total_units_sold,
            COUNT(DISTINCT order_id)    AS total_orders,
            ROUND(SUM(line_total),2)    AS total_revenue,
            ROUND(SUM(gross_profit),2)  AS total_gross_profit,
            ROUND(AVG(margin_pct),2)    AS avg_margin_pct,
            ROUND(AVG(unit_price),2)    AS avg_selling_price,
            ROUND(AVG(cost_price),2)    AS avg_cost_price
        FROM silver_stg_order_items GROUP BY 1,2,3,4,5
    ),
    thresholds AS (
        SELECT AVG(total_units_sold) AS avg_units, AVG(avg_margin_pct) AS avg_margin
        FROM item_stats
    )
    SELECT s.*,
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
    FROM item_stats s CROSS JOIN thresholds t ORDER BY total_revenue DESC
    """)
    n = conn.execute("SELECT COUNT(*) FROM gold_mart_menu_performance").fetchone()[0]
    log.info(f"  ✓ gold_mart_menu_performance: {n:,} items classified")

    # ── GOLD: mart_location_comparison ──────────────────────────────────────
    log.info("Running gold.mart_location_comparison ...")
    conn.execute("DROP TABLE IF EXISTS gold_mart_location_comparison")
    conn.execute("""
    CREATE TABLE gold_mart_location_comparison AS
    WITH monthly AS (
        SELECT o.location_id, o.location_name, o.order_year, o.order_month,
            COUNT(DISTINCT o.order_id)    AS total_orders,
            ROUND(SUM(o.total_amount),2)  AS total_revenue,
            ROUND(AVG(o.total_amount),2)  AS avg_ticket,
            ROUND(SUM(o.discount_amount),2) AS total_discounts,
            ROUND(SUM(oi.gp),2)           AS total_gross_profit,
            ROUND(AVG(oi.mp),2)           AS avg_margin_pct,
            COUNT(DISTINCT CASE WHEN o.order_type='Dine-In'  THEN o.order_id END) AS dine_in_orders,
            COUNT(DISTINCT CASE WHEN o.order_type='Takeout'  THEN o.order_id END) AS takeout_orders,
            COUNT(DISTINCT CASE WHEN o.order_type='Delivery' THEN o.order_id END) AS delivery_orders
        FROM silver_stg_orders o
        LEFT JOIN (
            SELECT order_id, SUM(gross_profit) AS gp, AVG(margin_pct) AS mp
            FROM silver_stg_order_items GROUP BY order_id
        ) oi ON o.order_id = oi.order_id
        WHERE o.is_refund = FALSE
        GROUP BY 1,2,3,4
    )
    SELECT *, ROUND(total_revenue / NULLIF(SUM(total_revenue) OVER (
        PARTITION BY order_year, order_month),0)*100,2) AS revenue_share_pct
    FROM monthly ORDER BY order_year, order_month, total_revenue DESC
    """)
    n = conn.execute("SELECT COUNT(*) FROM gold_mart_location_comparison").fetchone()[0]
    log.info(f"  ✓ gold_mart_location_comparison: {n:,} rows")

    # ── GOLD: mart_time_analysis ────────────────────────────────────────────
    log.info("Running gold.mart_time_analysis ...")
    conn.execute("DROP TABLE IF EXISTS gold_mart_time_analysis")
    conn.execute("""
    CREATE TABLE gold_mart_time_analysis AS
    SELECT location_id, location_name, order_year, order_month,
        day_of_week, day_name, is_weekend, order_hour, day_part,
        COUNT(DISTINCT order_id)        AS total_orders,
        ROUND(SUM(total_amount),2)      AS total_revenue,
        ROUND(AVG(total_amount),2)      AS avg_ticket,
        ROUND(SUM(discount_amount),2)   AS total_discounts
    FROM silver_stg_orders WHERE is_refund = FALSE
    GROUP BY 1,2,3,4,5,6,7,8,9
    ORDER BY order_year, order_month, day_of_week, order_hour
    """)
    n = conn.execute("SELECT COUNT(*) FROM gold_mart_time_analysis").fetchone()[0]
    log.info(f"  ✓ gold_mart_time_analysis: {n:,} rows")

    # ── GOLD: mart_revenue_trends ───────────────────────────────────────────
    log.info("Running gold.mart_revenue_trends ...")
    conn.execute("DROP TABLE IF EXISTS gold_mart_revenue_trends")
    conn.execute("""
    CREATE TABLE gold_mart_revenue_trends AS
    WITH monthly AS (
        SELECT location_id, location_name, order_year, order_month,
            COUNT(DISTINCT order_id)        AS total_orders,
            ROUND(SUM(total_amount),2)      AS total_revenue,
            ROUND(SUM(discount_amount),2)   AS total_discounts,
            ROUND(AVG(total_amount),2)      AS avg_ticket
        FROM silver_stg_orders WHERE is_refund = FALSE GROUP BY 1,2,3,4
    )
    SELECT *, LAG(total_revenue) OVER (PARTITION BY location_id ORDER BY order_year, order_month) AS prev_month_revenue,
        ROUND((total_revenue - LAG(total_revenue) OVER (PARTITION BY location_id ORDER BY order_year, order_month))
            / NULLIF(LAG(total_revenue) OVER (PARTITION BY location_id ORDER BY order_year, order_month),0)*100,2) AS mom_growth_pct,
        SUM(total_revenue) OVER (PARTITION BY location_id, order_year ORDER BY order_month ROWS UNBOUNDED PRECEDING) AS ytd_revenue
    FROM monthly ORDER BY location_id, order_year, order_month
    """)
    n = conn.execute("SELECT COUNT(*) FROM gold_mart_revenue_trends").fetchone()[0]
    log.info(f"  ✓ gold_mart_revenue_trends: {n:,} rows")

    conn.close()
    log.info("=" * 60)
    log.info("  ✅ All transformations complete — Bronze → Silver → Gold")
    log.info("=" * 60)

if __name__ == "__main__":
    run()
