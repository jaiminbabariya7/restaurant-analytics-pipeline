"""
Restaurant Co. — Data Quality Layer
Great Expectations-style validation checks on Bronze layer before Silver promotion
"""

import duckdb
import json
import logging
import os
from datetime import datetime

BASE    = os.environ.get("PIPELINE_HOME", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.environ.get("RESTAURANT_DB_PATH", f"{BASE}/data/bronze/restaurant_bronze.duckdb")
LOG_FILE= f"{BASE}/output/logs/quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
REPORT  = f"{BASE}/output/reports/quality_report_{datetime.now().strftime('%Y%m%d')}.json"

os.makedirs(f"{BASE}/output/reports", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

CHECKS = [
    # Orders
    {"table":"bronze_orders","name":"orders_no_null_order_id",       "sql":"SELECT COUNT(*) FROM bronze_orders WHERE order_id IS NULL",                        "expect":0,   "operator":"eq"},
    {"table":"bronze_orders","name":"orders_no_null_location",        "sql":"SELECT COUNT(*) FROM bronze_orders WHERE location_id IS NULL",                     "expect":0,   "operator":"eq"},
    {"table":"bronze_orders","name":"orders_valid_locations",         "sql":"SELECT COUNT(*) FROM bronze_orders WHERE location_id NOT IN ('LOC-GRM','LOC-WTD','LOC-DUN','LOC-WIN','LOC-PTC')", "expect":0, "operator":"eq"},
    {"table":"bronze_orders","name":"orders_valid_order_types",       "sql":"SELECT COUNT(*) FROM bronze_orders WHERE order_type NOT IN ('Dine-In','Takeout','Delivery')", "expect":0, "operator":"eq"},
    {"table":"bronze_orders","name":"orders_tax_positive",            "sql":"SELECT COUNT(*) FROM bronze_orders WHERE tax_amount < 0 AND is_refund = false",    "expect":0,   "operator":"eq"},
    {"table":"bronze_orders","name":"orders_total_matches_subtotal",  "sql":"SELECT COUNT(*) FROM bronze_orders WHERE ABS(total_amount - subtotal - tax_amount) > 0.02 AND is_refund = false", "expect":0, "operator":"eq"},
    {"table":"bronze_orders","name":"orders_no_future_dates",         "sql":"SELECT COUNT(*) FROM bronze_orders WHERE order_date > '2024-12-31'",               "expect":0,   "operator":"eq"},
    {"table":"bronze_orders","name":"orders_date_range_valid",        "sql":"SELECT COUNT(*) FROM bronze_orders WHERE order_date < '2024-01-01'",               "expect":0,   "operator":"eq"},
    {"table":"bronze_orders","name":"orders_not_on_closed_days",      "sql":"SELECT COUNT(*) FROM bronze_orders WHERE order_date IN ('2024-12-25','2024-01-01')", "expect":0, "operator":"eq"},
    {"table":"bronze_orders","name":"orders_no_duplicate_order_ids",  "sql":"SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM bronze_orders",                   "expect":0,   "operator":"eq"},
    # Order Items
    {"table":"bronze_order_items","name":"items_no_null_order_id",    "sql":"SELECT COUNT(*) FROM bronze_order_items WHERE order_id IS NULL",                   "expect":0,   "operator":"eq"},
    {"table":"bronze_order_items","name":"items_quantity_positive",   "sql":"SELECT COUNT(*) FROM bronze_order_items WHERE quantity <= 0",                      "expect":0,   "operator":"eq"},
    {"table":"bronze_order_items","name":"items_price_in_range",      "sql":"SELECT COUNT(*) FROM bronze_order_items WHERE unit_price < 0.99 OR unit_price > 89.99", "expect":0, "operator":"eq"},
    {"table":"bronze_order_items","name":"items_no_null_item_id",     "sql":"SELECT COUNT(*) FROM bronze_order_items WHERE item_id IS NULL",                    "expect":0,   "operator":"eq"},
    {"table":"bronze_order_items","name":"items_valid_item_ids",      "sql":"SELECT COUNT(*) FROM bronze_order_items oi LEFT JOIN bronze_menu m ON oi.item_id=m.item_id WHERE m.item_id IS NULL", "expect":0, "operator":"eq"},
    # Menu
    {"table":"bronze_menu","name":"menu_47_items",                    "sql":"SELECT COUNT(*) FROM bronze_menu",                                                 "expect":47,  "operator":"eq"},
    {"table":"bronze_menu","name":"menu_cost_lt_price",               "sql":"SELECT COUNT(*) FROM bronze_menu WHERE cost_price >= selling_price",               "expect":0,   "operator":"eq"},
    {"table":"bronze_menu","name":"menu_food_cost_reasonable",        "sql":"SELECT COUNT(*) FROM bronze_menu WHERE (cost_price / selling_price) > 0.45",       "expect":0,   "operator":"eq"},
]

def run():
    log.info("=" * 60)
    log.info("  DATA QUALITY CHECKS — Restaurant Co.")
    log.info(f"  Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    conn = duckdb.connect(DB_PATH)
    results = []
    passed = failed = 0

    for check in CHECKS:
        val = conn.execute(check["sql"]).fetchone()[0]
        ok  = val == check["expect"] if check["operator"] == "eq" else val <= check["expect"]
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else:  failed += 1
        symbol = "✓" if ok else "✗"
        log.info(f"  {symbol} [{status}] {check['name']} → {val} (expected {check['expect']})")
        results.append({"check": check["name"], "table": check["table"],
                        "result": val, "expected": check["expect"], "status": status})

    conn.close()
    report = {
        "run_timestamp": datetime.now().isoformat(),
        "summary": {"total": len(CHECKS), "passed": passed, "failed": failed,
                    "pass_rate": f"{passed/len(CHECKS)*100:.1f}%"},
        "checks": results
    }
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=2)

    log.info("=" * 60)
    log.info(f"  ✅ Quality checks: {passed}/{len(CHECKS)} passed ({passed/len(CHECKS)*100:.1f}%)")
    if failed > 0:
        log.error(f"  ❌ {failed} checks FAILED — pipeline halted")
        raise Exception(f"{failed} data quality checks failed. See {REPORT}")
    log.info(f"  📄 Report saved: {REPORT}")
    log.info("=" * 60)
    return report

if __name__ == "__main__":
    run()
