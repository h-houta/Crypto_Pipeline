"""
Crypto Streaming DAG
Manages continuous streaming of crypto data with producer and consumer services
"""

import json
import logging
import os
from datetime import datetime, timedelta
from airflow import DAG  # type: ignore[import-not-found]
from airflow.operators.python import PythonOperator  # type: ignore[import-not-found]
from airflow.sensors.python import PythonSensor  # type: ignore[import-not-found]
from airflow.utils.task_group import TaskGroup  # type: ignore[import-not-found]

try:
    from airflow.providers.postgres.hooks.postgres import PostgresHook  # type: ignore[import-not-found]
except Exception:
    PostgresHook = None


def get_pg_connection():
    """Get PostgreSQL connection - imports moved inside function"""
    try:
        if PostgresHook is not None:
            return PostgresHook(postgres_conn_id="postgres_crypto").get_conn()
    except Exception as e:
        logging.warning("PostgresHook failed; falling back to env: %s", e)

    # Import moved inside function to avoid module-level import issues
    try:
        import psycopg2  # type: ignore[import-not-found]
        from psycopg2 import Error as Psycopg2Error  # type: ignore[import-not-found, attr-defined]
    except ImportError:
        psycopg2 = None  # type: ignore[assignment]

        class _Psycopg2ErrorFallback(Exception):
            pass

        Psycopg2Error = _Psycopg2ErrorFallback

    host_candidates = []
    env_host = os.getenv("POSTGRES_HOST")
    if env_host:
        host_candidates.append(env_host)
    host_candidates += ["postgres", "host.docker.internal", "localhost", "127.0.0.1"]
    port = int(os.getenv("POSTGRES_PORT", "5434"))
    database = os.getenv("POSTGRES_DATABASE", "crypto_db")
    user = os.getenv("POSTGRES_USER", "crypto_user")
    password = os.getenv("POSTGRES_PASSWORD", "")

    # Ensure psycopg2 is available before attempting direct connection
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not available and PostgresHook failed; cannot connect to PostgreSQL"
        )

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


# Default arguments for the DAG
default_args = {
    "owner": "crypto-pipeline",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=240),
}

# Create the DAG
dag = DAG(
    "crypto_streaming_manager",
    default_args=default_args,
    description="Manages continuous crypto data streaming services",
    schedule_interval=timedelta(seconds=30),  # Check every 10 seconds
    catchup=False,
    tags=["crypto", "streaming", "monitoring"],
)


def check_service_status(service_name):
    """Check if a Docker service is running - imports moved inside function"""
    try:
        # Import moved inside function to avoid module-level import issues
        import subprocess

        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={service_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        status = result.stdout.strip()
        is_running = bool(status and "Up" in status)
        logging.info(
            "Service %s status: %s", service_name, "Running" if is_running else "Not running"
        )
        return is_running
    except subprocess.CalledProcessError as e:
        logging.error("Failed to check %s status: %s", service_name, e)
        return False


def start_service(service_name):
    """Start a Docker service"""
    try:
        # Check if already running
        if check_service_status(service_name):
            logging.info("Service %s is already running", service_name)
            return f"{service_name} already running"

        # Start the service
        if service_name == "crypto-producer":
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                "crypto-producer",
                "--network",
                "crypto-network",
                "-e",
                "KAFKA_BOOTSTRAP_SERVERS=redpanda:9092",
                "-e",
                "KAFKA_TOPIC=crypto_prices",
                "-e",
                "POLL_INTERVAL=10",
                "crypto-producer:latest",
            ]
        elif service_name == "crypto-consumer":
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                "crypto-consumer",
                "--network",
                "crypto-network",
                "-e",
                "KAFKA_BOOTSTRAP_SERVERS=redpanda:9092",
                "-e",
                "POSTGRES_HOST=postgres",
                "-e",
                "POSTGRES_PORT=5434",
                "-e",
                "POSTGRES_DATABASE=crypto_db",
                "-e",
                "POSTGRES_USER=crypto_user",
                "-e",
                "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}",
                "crypto-consumer:latest",
            ]
        else:
            raise ValueError(f"Unknown service: {service_name}")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info("Started %s: %s", service_name, result.stdout)
        return f"{service_name} started successfully"
    except subprocess.CalledProcessError as e:
        logging.error("Failed to start %s: %s", service_name, e)
        raise


def stop_service(service_name):
    """Stop a Docker service"""
    try:
        subprocess.run(["docker", "stop", service_name], capture_output=True, text=True, check=True)
        logging.info("Stopped %s", service_name)

        # Remove the container
        subprocess.run(["docker", "rm", service_name], capture_output=True, text=True, check=False)
        return f"{service_name} stopped"
    except subprocess.CalledProcessError as e:
        logging.warning("Service %s might not be running: %s", service_name, e)
        return f"{service_name} was not running"


def restart_service(service_name):
    """Restart a Docker service"""
    stop_service(service_name)
    return start_service(service_name)


def check_service_health(service_name):
    """Check if a service is healthy by examining logs"""
    try:
        # Get last 50 lines of logs
        result = subprocess.run(
            ["docker", "logs", "--tail", "50", service_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        logs = result.stdout + result.stderr

        # Check for error patterns
        error_patterns = ["ERROR", "FATAL", "Exception", "Failed to connect"]
        errors_found = [p for p in error_patterns if p in logs]

        if errors_found:
            logging.warning("Potential issues in %s: %s", service_name, errors_found)
            return False

        # Check for recent activity (logs should have timestamps)
        if not logs.strip():
            logging.warning("No recent logs from %s", service_name)
            return False

        logging.info("Service %s appears healthy", service_name)
        return True
    except (subprocess.TimeoutExpired, OSError) as e:
        logging.error("Failed to check %s health: %s", service_name, e)
        return False


def monitor_metrics(**context):
    """Monitor key metrics from the pipeline"""
    if psycopg2 is None and PostgresHook is None:
        logging.error("No Postgres client available; install psycopg2 or Postgres provider.")
        return None

    metrics = {}
    conn = None
    try:
        conn = get_pg_connection()
        with conn.cursor() as cur:
            # Get message count in last 10 seconds
            cur.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT symbol)
                FROM public.raw_crypto_prices_log
                WHERE time > NOW() - INTERVAL '10 seconds'
                """
            )
            row = cur.fetchone()
            if row is not None and len(row) >= 2:
                count, symbols = row
            else:
                count, symbols = 0, None
            metrics["messages_last_hour"] = count
            metrics["unique_symbols"] = symbols

            # Get lag (time since last message)
            cur.execute(
                """
                SELECT EXTRACT(EPOCH FROM (NOW() - MAX(time)))::INT as lag_seconds
                FROM public.raw_crypto_prices_log
                """
            )
            row = cur.fetchone()
            lag = row[0] if row and row[0] is not None else 0
            metrics["lag_seconds"] = lag

            # Check for data gaps
            cur.execute(
                """
                WITH time_diffs AS (
                    SELECT
                        time,
                        LAG(time) OVER (ORDER BY time) as prev_time,
                        EXTRACT(EPOCH FROM (time - LAG(time)
                        OVER (ORDER BY time))) as diff_seconds
                    FROM public.raw_crypto_prices_log
                    WHERE time > NOW() - INTERVAL '60 seconds'
                )
                SELECT COUNT(*)
                FROM time_diffs
                WHERE diff_seconds > 60
                """
            )
            row = cur.fetchone()
            gaps = row[0] if row and row[0] is not None else 0
            metrics["data_gaps"] = gaps

        logging.info("Pipeline metrics: %s", json.dumps(metrics, indent=2))

        if metrics["lag_seconds"] and metrics["lag_seconds"] > 60:
            logging.warning("High lag detected: %s seconds", metrics["lag_seconds"])
            context["task_instance"].xcom_push(key="alert", value="high_lag")

        if metrics["messages_last_hour"] < 10:
            logging.warning("Low message count: %s", metrics["messages_last_hour"])
            context["task_instance"].xcom_push(key="alert", value="low_throughput")

        return metrics
    except (ConnectionError, ValueError) as e:
        logging.error("Error while monitoring metrics: %s", e)
        return None
    except Psycopg2Error as e:
        logging.error("Database error while monitoring metrics: %s", e)
        return None
    finally:
        if conn:
            conn.close()


# Define tasks
with dag:
    # Check service status
    with TaskGroup("service_status") as service_status:
        producer_status = PythonSensor(
            task_id="check_producer_status",
            python_callable=lambda: check_service_status("crypto-producer"),
            mode="poke",
            poke_interval=10,
            timeout=60,
            soft_fail=True,
        )

        consumer_status = PythonSensor(
            task_id="check_consumer_status",
            python_callable=lambda: check_service_status("crypto-consumer"),
            mode="poke",
            poke_interval=10,
            timeout=60,
            soft_fail=True,
        )

    # Service health checks
    with TaskGroup("health_checks") as health_checks:
        producer_health = PythonOperator(
            task_id="check_producer_health",
            python_callable=check_service_health,
            op_args=["crypto-producer"],
            trigger_rule="none_failed",
        )

        consumer_health = PythonOperator(
            task_id="check_consumer_health",
            python_callable=check_service_health,
            op_args=["crypto-consumer"],
            trigger_rule="none_failed",
        )

    # Restart services if unhealthy
    restart_producer = PythonOperator(
        task_id="restart_producer_if_needed",
        python_callable=restart_service,
        op_args=["crypto-producer"],
        trigger_rule="one_failed",
    )

    restart_consumer = PythonOperator(
        task_id="restart_consumer_if_needed",
        python_callable=restart_service,
        op_args=["crypto-consumer"],
        trigger_rule="one_failed",
    )

    # Monitor metrics
    monitor = PythonOperator(
        task_id="monitor_pipeline_metrics",
        python_callable=monitor_metrics,
        provide_context=True,
        trigger_rule="none_failed",
    )

    # Define dependencies
    _ = service_status >> health_checks
    _ = producer_health >> restart_producer
    _ = consumer_health >> restart_consumer
    _ = [restart_producer, restart_consumer, health_checks] >> monitor
