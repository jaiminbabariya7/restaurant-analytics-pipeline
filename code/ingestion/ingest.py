"""
Restaurant Co. — Ingestion Layer
Reads raw POS exports → validates schema → loads into Bronze layer (DuckDB)
Supports incremental loading via watermark tracking
"""

import pandas as pd
import duckdb
import os
import json
import logging
from datetime import datetime

BASE        = os.environ.get("PIPELINE_HOME", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RAW_DIR     = f"{BASE}/data/raw"
BRONZE_DIR  = f"{BASE}/data/bronze"
DB_PATH     = os.environ.get("RESTAURANT_DB_PATH", f"{BASE}/data/bronze/restaurant_bronze.duckdb")
WATERMARK_F = f"{BASE}/output/logs/watermark.json"
LOG_FILE    = f"{BASE}/output/logs/ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

os.makedirs(f"{BASE}/output/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

EXPECTED_SCHEMAS = {
    "orders": ["order_id","location_id","location_name","order_date","order_time",
                "order_type","cashier_id","subtotal","discount_amount","tax_amount",
                "total_amount","payment_method","is_refund"],
    "order_items": ["order_item_id","order_id","item_id","item_name","category","size",
                    "quantity","unit_price","discount_applied","line_total","promo_id"],
    "menu": ["item_id","item_name","category","subcategory","size","selling_price",
             "cost_price","is_active","launch_date","is_seasonal"],
    "locations": ["location_id","location_name","address","seating_capacity",
                  "opening_date","manager_name","phone","is_active"],
    "promotions": ["promo_id","promo_name","discount_type","discount_value","applies_to",
                   "start_date","end_date","location_id","day_of_week"],
    "menu_price_history": ["price_history_id","item_id","selling_price","cost_price",
                           "effective_from","effective_to","is_current","change_reason"],
}

def load_watermark():
    if os.path.exists(WATERMARK_F):
        with open(WATERMARK_F) as f:
            return json.load(f)
    return {}

def save_watermark(wm):
    with open(WATERMARK_F, "w") as f:
        json.dump(wm, f, indent=2)

def validate_schema(df, table_name):
    expected = set(EXPECTED_SCHEMAS[table_name])
    actual   = set(df.columns)
    missing  = expected - actual
    if missing:
        raise ValueError(f"Schema mismatch in {table_name}: missing columns {missing}")
    log.info(f"  ✓ Schema validated: {table_name} ({len(df.columns)} columns)")

def ingest_table(conn, table_name, watermark):
    path = f"{RAW_DIR}/{table_name}.csv"
    log.info(f"Loading {table_name}.csv ...")
    df = pd.read_csv(path)
    validate_schema(df, table_name)

    # Incremental load for orders and order_items
    if table_name in ["orders", "order_items"] and table_name in watermark:
        last_wm = watermark[table_name]
        if table_name == "orders":
            df["order_date"] = pd.to_datetime(df["order_date"])
            new_df = df[df["order_date"].dt.strftime("%Y-%m-%d") > last_wm]
        else:
            # join on order_id to get date
            orders = pd.read_csv(f"{RAW_DIR}/orders.csv", usecols=["order_id","order_date"])
            df = df.merge(orders, on="order_id", how="left")
            df["order_date"] = pd.to_datetime(df["order_date"])
            new_df = df[df["order_date"].dt.strftime("%Y-%m-%d") > last_wm]
            new_df = new_df.drop(columns=["order_date"])
        log.info(f"  ↑ Incremental: {len(new_df):,} new rows (after {last_wm})")
        df = new_df
    else:
        log.info(f"  ↑ Full load: {len(df):,} rows")

    # Write to DuckDB bronze
    conn.execute(f"DROP TABLE IF EXISTS bronze_{table_name}")
    conn.execute(f"CREATE TABLE bronze_{table_name} AS SELECT * FROM df")
    row_count = conn.execute(f"SELECT COUNT(*) FROM bronze_{table_name}").fetchone()[0]
    log.info(f"  ✓ Loaded → bronze_{table_name}: {row_count:,} rows")
    return len(df)

def run():
    log.info("=" * 60)
    log.info("  INGESTION LAYER — Restaurant Co. POS Data")
    log.info(f"  Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    watermark = load_watermark()
    conn = duckdb.connect(DB_PATH)

    total_rows = 0
    for table in EXPECTED_SCHEMAS:
        rows = ingest_table(conn, table, watermark)
        total_rows += rows

    # Update watermark to latest order date
    latest = conn.execute("SELECT MAX(order_date) FROM bronze_orders").fetchone()[0]
    if latest is None:
        log.warning("  ⚠ No rows in bronze_orders — watermark not updated")
    else:
        watermark["orders"]      = str(latest)
        watermark["order_items"] = str(latest)
        save_watermark(watermark)
        log.info(f"  📌 Watermark updated to: {latest}")

    conn.close()
    log.info("=" * 60)
    log.info(f"  ✅ Ingestion complete — {total_rows:,} total rows loaded")
    log.info("=" * 60)

if __name__ == "__main__":
    run()
