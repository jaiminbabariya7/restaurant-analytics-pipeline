"""
Restaurant Co. — Daily Report Generator
Reads Gold layer tables and exports summary CSVs for Power BI refresh and owner email.
"""

import duckdb
import os
import logging
from datetime import datetime

BASE    = os.environ.get("PIPELINE_HOME", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.environ.get("RESTAURANT_DB_PATH", f"{BASE}/data/bronze/restaurant_bronze.duckdb")
OUT_DIR = f"{BASE}/output/reports"
LOG_FILE= f"{BASE}/output/logs/reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

os.makedirs(OUT_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

REPORTS = {
    "menu_performance":    "SELECT * FROM gold_mart_menu_performance ORDER BY total_revenue DESC",
    "location_comparison": "SELECT * FROM gold_mart_location_comparison ORDER BY order_year, order_month, total_revenue DESC",
    "revenue_trends":      "SELECT * FROM gold_mart_revenue_trends ORDER BY location_id, order_year, order_month",
    "time_analysis":       "SELECT location_name, day_name, order_hour, SUM(total_orders) AS total_orders, ROUND(SUM(total_revenue),2) AS total_revenue FROM gold_mart_time_analysis GROUP BY 1,2,3 ORDER BY 2,3",
}

def run():
    log.info("=" * 60)
    log.info("  REPORT GENERATION — Restaurant Co.")
    log.info(f"  Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    conn = duckdb.connect(DB_PATH, read_only=True)

    for name, sql in REPORTS.items():
        df = conn.execute(sql).df()
        out_path = f"{OUT_DIR}/{name}_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(out_path, index=False)
        log.info(f"  ✓ {name}: {len(df):,} rows → {os.path.basename(out_path)}")

    conn.close()
    log.info("=" * 60)
    log.info("  ✅ All reports exported successfully")
    log.info("=" * 60)

if __name__ == "__main__":
    run()
