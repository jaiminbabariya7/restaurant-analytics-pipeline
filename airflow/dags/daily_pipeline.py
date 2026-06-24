"""
Restaurant Co. — Daily Menu Performance Pipeline
Runs every morning at 6:00 AM EST
Orchestrates: Ingest → Validate → dbt Bronze → dbt Silver → dbt Tests → dbt Gold → Report
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.email import EmailOperator
from airflow.utils.trigger_rule import TriggerRule
import os

BASE = os.environ.get("PIPELINE_HOME", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ALERT_EMAIL  = os.environ.get("PIPELINE_ALERT_EMAIL", "")
OWNER_EMAIL  = os.environ.get("PIPELINE_OWNER_EMAIL", "")

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 2),
    "email": [ALERT_EMAIL] if ALERT_EMAIL else [],
    "email_on_failure": bool(ALERT_EMAIL),
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="restaurant_daily_menu_pipeline",
    default_args=default_args,
    description="Daily batch pipeline: POS → Bronze → Silver → Gold → Report",
    schedule_interval="0 6 * * *",   # 6:00 AM daily
    catchup=False,
    max_active_runs=1,
    tags=["restaurant", "restaurant", "dbt", "daily"],
) as dag:

    # ── TASK 1: Check source files arrived ─────────────────────────────────────
    def check_source_files(**ctx):
        import glob
        raw_dir = f"{BASE}/data/raw"
        expected = ["orders.csv", "order_items.csv", "menu.csv",
                    "locations.csv", "promotions.csv", "menu_price_history.csv"]
        missing = [f for f in expected if not os.path.exists(f"{raw_dir}/{f}")]
        if missing:
            raise FileNotFoundError(f"Missing source files: {missing}")
        print(f"✓ All {len(expected)} source files present")

    t1_check_files = PythonOperator(
        task_id="check_source_files_arrived",
        python_callable=check_source_files,
    )

    # ── TASK 2: Ingest Bronze ──────────────────────────────────────────────────
    t2_ingest = BashOperator(
        task_id="ingest_bronze_layer",
        bash_command=f"cd {BASE} && python3 code/ingestion/ingest.py",
    )

    # ── TASK 3: Data Quality Checks ───────────────────────────────────────────
    t3_quality = BashOperator(
        task_id="validate_data_quality",
        bash_command=f"cd {BASE} && python3 code/validation/quality_checks.py",
    )

    # ── TASK 4: dbt Bronze models ─────────────────────────────────────────────
    t4_dbt_bronze = BashOperator(
        task_id="run_dbt_bronze_models",
        bash_command=f"cd {BASE}/dbt_restaurant && dbt run --select bronze --profiles-dir .",
    )

    # ── TASK 5: dbt Silver models ─────────────────────────────────────────────
    t5_dbt_silver = BashOperator(
        task_id="run_dbt_silver_models",
        bash_command=f"cd {BASE}/dbt_restaurant && dbt run --select silver --profiles-dir .",
    )

    # ── TASK 6: dbt Tests ─────────────────────────────────────────────────────
    t6_dbt_tests = BashOperator(
        task_id="run_dbt_tests",
        bash_command=f"cd {BASE}/dbt_restaurant && dbt test --profiles-dir .",
    )

    # ── TASK 7: dbt Gold models ───────────────────────────────────────────────
    t7_dbt_gold = BashOperator(
        task_id="run_dbt_gold_models",
        bash_command=f"cd {BASE}/dbt_restaurant && dbt run --select gold --profiles-dir .",
    )

    # ── TASK 8: Generate Reports ──────────────────────────────────────────────
    t8_reports = BashOperator(
        task_id="generate_daily_reports",
        bash_command=f"cd {BASE} && python3 code/transformation/generate_reports.py",
    )

    # ── TASK 9: Email Owner Summary ───────────────────────────────────────────
    t9_email = EmailOperator(
        task_id="send_owner_summary_email",
        to=[OWNER_EMAIL] if OWNER_EMAIL else [ALERT_EMAIL],
        subject="[Restaurant Co.] Daily Menu Performance Report — {{ ds }}",
        html_content="""
        <h2>Good Morning!</h2>
        <p>Your daily Restaurant franchise report for <b>{{ ds }}</b> is ready.</p>
        <ul>
            <li>Pipeline completed successfully at {{ ts }}</li>
            <li>Check your Power BI dashboard for full details</li>
        </ul>
        <p>— Automated Data Pipeline</p>
        """,
    )

    # ── DAG DEPENDENCY CHAIN ──────────────────────────────────────────────────
    t1_check_files >> t2_ingest >> t3_quality >> t4_dbt_bronze >> t5_dbt_silver >> t6_dbt_tests >> t7_dbt_gold >> t8_reports >> t9_email
