"""
###################################################################################################
#  Version History
###################################################################################################
#  	Version 	| Date        	         | 	    Author			  |	Comments
#  	1.0      	| 16 AUG, 2025 	         | 	    HASSAN HOUTA	  |	Initial.
###################################################################################################
# Crypto DBT DAG / This file is to orchestrate the DBT transformations and data quality checks.
###################################################################################################
"""

import json
import logging
from typing import Any, cast
from datetime import datetime, timedelta
import os

try:
    from airflow import DAG  # type: ignore[import-not-found]
    from airflow.operators.python import PythonOperator  # type: ignore[import-not-found]
    from airflow.sensors.python import PythonSensor  # type: ignore[import-not-found]
    from airflow.operators.bash import BashOperator  # type: ignore[import-not-found]
    from airflow.utils.task_group import TaskGroup  # type: ignore[import-not-found]
    from airflow.providers.postgres.hooks.postgres import PostgresHook  # type: ignore[import-not-found]
except ImportError as e:
    print(f"Warning: Airflow not available: {e}")
    DAG = cast(Any, object)
    PythonOperator = cast(Any, object)
    BashOperator = cast(Any, object)
    TaskGroup = cast(Any, object)
    PostgresHook = None  # added

# Default arguments for the DAG
default_args = {
    "owner": "crypto-pipeline",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


def get_pg_connection():
    """Get PostgreSQL connection - imports moved inside function"""
    try:
        if PostgresHook is not None:
            return PostgresHook(postgres_conn_id="postgres_crypto").get_conn()
    except Exception as e:
        logging.warning("PostgresHook failed; falling back to env: %s", e)

    # Import moved inside function to avoid module-level import issues
    import psycopg2

    host_candidates = []
    env_host = os.getenv("POSTGRES_HOST")
    if env_host:
        host_candidates.append(env_host)
    host_candidates += ["postgres", "host.docker.internal", "localhost", "127.0.0.1"]
    port = int(os.getenv("POSTGRES_PORT", "5434"))
    database = os.getenv("POSTGRES_DATABASE", "crypto_db")
    user = os.getenv("POSTGRES_USER", "crypto_user")
    password = os.getenv("POSTGRES_PASSWORD", "cryptopass123")

    last_err = None
    for host in host_candidates:
        try:
            logging.info("Trying PostgreSQL host: %s", host)
            return psycopg2.connect(
                host=host, port=port, database=database, user=user, password=password
            )
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("Could not connect to PostgreSQL")


# Create the DAG
dag = DAG(
    "crypto_dbt_transformations",
    default_args=default_args,
    description="Run DBT transformations and data quality checks",
    schedule_interval=timedelta(seconds=120),  # Every 30 seconds
    catchup=False,
    tags=["crypto", "dbt", "analytics"],
)


def run_dbt_models(**context):
    """Run DBT models - imports moved inside function"""
    _ = context

    dbt_dir = "/opt/airflow/dbt_crypto"

    try:
        # Import moved inside function to avoid module-level import issues
        import subprocess

        result = subprocess.run(
            ["dbt", "deps"], cwd=dbt_dir, capture_output=True, text=True, check=True
        )
        logging.info("DBT deps output: %s", result.stdout)

        result = subprocess.run(
            [
                "dbt",
                "run",
                "--target",
                "prod",
                "--select",
                "stg_crypto_prices+ crypto_ohlcv_15min+",
            ],
            cwd=dbt_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        logging.info("DBT run output: %s", result.stdout)

        if "Completed successfully" in result.stdout:
            return "DBT models executed successfully"
        else:
            logging.warning("DBT run completed with warnings")
            return "DBT models executed with warnings"
    except subprocess.CalledProcessError as e:
        logging.error("DBT run failed: %s", e.stderr)
        raise


def validate_transformed_data(**context):
    """Validate the transformed data"""
    _ = context

    conn = get_pg_connection()
    validations = {"passed": [], "failed": []}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) as period_count,
                    COUNT(DISTINCT symbol) as symbol_count,
                    MIN(period_start) as earliest,
                    MAX(period_start) as latest
                FROM public.crypto_ohlcv_15min_tbl
                WHERE period_start > NOW() - INTERVAL '24 hours'
            """
            )
            result = cur.fetchone()
            if result is None:
                validations["failed"].append("No OHLCV data found")
            else:
                period_count, symbol_count, earliest, latest = result
                if not period_count:
                    validations["failed"].append("No OHLCV data found")
                else:
                    validations["passed"].append("OHLCV data exists")
                    logging.info(
                        "Found %s OHLCV periods for %s symbols from %s to %s",
                        period_count,
                        symbol_count,
                        earliest,
                        latest,
                    )

            cur.execute(
                """
                SELECT symbol, COUNT(*) as anomaly_count
                FROM public.crypto_ohlcv_15min_tbl
                WHERE period_start > NOW() - INTERVAL '24 hours'
                  AND (high < low OR close < 0 OR total_volume < 0)
                GROUP BY symbol
            """
            )
            anomalies = cur.fetchall()
            if not anomalies:
                validations["passed"].append("No data anomalies detected")
            else:
                validations["failed"].append(
                    f"Data anomalies found: {[anomaly[0] for anomaly in anomalies]}"
                )

            cur.execute(
                """
                WITH expected_periods AS (
                    SELECT generate_series(
                        date_trunc('second', NOW() - INTERVAL '15 seconds'),
                        date_trunc('second', NOW()),
                        INTERVAL '15 seconds'
                    ) as period
                ),
                actual_periods AS (
                    SELECT DISTINCT period_start
                    FROM public.crypto_ohlcv_15min_tbl
                    WHERE period_start > NOW() - INTERVAL '15 seconds'
                )
                SELECT COUNT(*)
                FROM expected_periods ep
                LEFT JOIN actual_periods ap ON ep.period = ap.period_start
                WHERE ap.period_start IS NULL
            """
            )
            result = cur.fetchone()
            missing_periods = result[0] if result and result[0] is not None else 0
            if missing_periods == 0:
                validations["passed"].append("No missing periods")
            else:
                validations["failed"].append(f"{missing_periods} missing periods detected")

        logging.info("Validation results: %s", json.dumps(validations, indent=2))
        context["task_instance"].xcom_push(key="validation_results", value=validations)
        if validations["failed"]:
            logging.warning("Some validations failed: %s", validations["failed"])
        return validations
    finally:
        conn.close()


def _raw_data_exists() -> bool:
    try:
        conn = get_pg_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.raw_crypto_prices_log")
            row = cur.fetchone()
            n = row[0] if row and row[0] is not None else 0
            logging.info("raw_crypto_prices_log count=%s", n)
            return bool(n and n > 0)
    except Exception as e:
        logging.warning("raw data existence check failed: %s", e)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def generate_data_quality_report(**context):
    """Generate a comprehensive data quality report"""

    conn = get_pg_connection()
    report = {
        "timestamp": datetime.now().isoformat(),
        "source_metrics": context["task_instance"].xcom_pull(key="source_metrics"),
        "validation_results": context["task_instance"].xcom_pull(key="validation_results"),
        "statistics": {},
    }

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    symbol,
                    COUNT(*) as data_points,
                    AVG(close) as avg_price,
                    STDDEV(close) as price_stddev,
                    MIN(close) as min_price,
                    MAX(close) as max_price,
                    SUM(total_volume) as total_volume
                FROM public.crypto_ohlcv_15min
                WHERE period_start > NOW() - INTERVAL '15 seconds'
                GROUP BY symbol
                ORDER BY total_volume DESC
            """
            )
            stats = cur.fetchall()
            report["statistics"] = {
                row[0]: {
                    "data_points": row[1],
                    "avg_price": float(row[2]) if row[2] else None,
                    "price_stddev": float(row[3]) if row[3] else None,
                    "min_price": float(row[4]) if row[4] else None,
                    "max_price": float(row[5]) if row[5] else None,
                    "total_volume": float(row[6]) if row[6] else None,
                }
                for row in stats
            }

        logging.info("Data Quality Report Generated: %s", json.dumps(report, indent=2))
        context["task_instance"].xcom_push(key="quality_report", value=report)
        return "Report generated successfully"
    finally:
        conn.close()


with TaskGroup("dbt_operations", dag=dag) as dbt_operations:
    dbt_env = {
        "DBT_PROFILES_DIR": "/opt/airflow/dbt_crypto",
        "DBT_POSTGRES_HOST": os.getenv("POSTGRES_HOST", "postgres"),
        "DBT_POSTGRES_USER": os.getenv("POSTGRES_USER", "crypto_user"),
        "DBT_POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "cryptopass123"),
        "DBT_POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5434"),
        "DBT_POSTGRES_DB": os.getenv("POSTGRES_DATABASE", "crypto_db"),
        "DBT_POSTGRES_SCHEMA": os.getenv("POSTGRES_SCHEMA", "public"),
    }
    dbt_run = BashOperator(
        task_id="dbt_run_models",
        bash_command="cd /opt/airflow/dbt_crypto && /home/airflow/.local/bin/dbt deps && /home/airflow/.local/bin/dbt run --target prod --select 'stg_crypto_prices+ crypto_ohlcv_15min+'",
        env=dbt_env,
        dag=dag,
    )
    dbt_test = BashOperator(
        task_id="dbt_run_tests",
        bash_command="cd /opt/airflow/dbt_crypto && /home/airflow/.local/bin/dbt test --target prod --select +crypto_ohlcv_15min",
        env=dbt_env,
        dag=dag,
    )
    dbt_docs = BashOperator(
        task_id="dbt_generate_docs",
        bash_command="cd /opt/airflow/dbt_crypto && /home/airflow/.local/bin/dbt docs generate --target prod",
        env=dbt_env,
        trigger_rule="none_failed",
        dag=dag,
    )
    dbt_run.set_downstream(dbt_test)
    dbt_test.set_downstream(dbt_docs)

wait_for_raw = PythonSensor(
    task_id="wait_for_raw_data",
    python_callable=_raw_data_exists,
    poke_interval=10,
    timeout=300,
    mode="poke",
    dag=dag,
)

validate_data = PythonOperator(
    task_id="validate_transformed_data",
    python_callable=validate_transformed_data,
    dag=dag,
)

generate_report = PythonOperator(
    task_id="generate_data_quality_report",
    python_callable=generate_data_quality_report,
    dag=dag,
)

# Wiring
# 1) Run dbt, 2) wait until raw data exists, 3) validate, 4) report
# (raw data sensor mainly safeguards first runs)

dbt_operations.set_downstream(wait_for_raw)
wait_for_raw.set_downstream(validate_data)
validate_data.set_downstream(generate_report)
