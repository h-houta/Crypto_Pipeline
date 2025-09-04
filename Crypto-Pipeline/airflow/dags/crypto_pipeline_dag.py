"""
Crypto Pipeline DAG
Orchestrates the crypto data pipeline with producer and consumer tasks
"""

import logging
import os
from datetime import datetime, timedelta

try:
    from airflow import DAG  # type: ignore
    from airflow.operators.python import PythonOperator  # type: ignore
    from airflow.providers.docker.operators.docker import DockerOperator  # type: ignore
    from airflow.utils.task_group import TaskGroup  # type: ignore
except ImportError:
    # Stub classes for local development
    class DAG:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __rshift__(self, other):
            return other

    class PythonOperator:
        def __init__(self, *args, **kwargs):
            pass

    class DockerOperator:
        def __init__(self, *args, **kwargs):
            pass

    class TaskGroup:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False


# Default arguments for the DAG
default_args = {
    "owner": "crypto-pipeline",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(seconds=70),
}

# Create the DAG
dag = DAG(
    "crypto_pipeline",
    default_args=default_args,
    description="Orchestrates crypto data collection and processing",
    schedule_interval=timedelta(seconds=30),  # Run every 30 seconds
    catchup=False,
    tags=["crypto", "streaming", "etl"],
)


def check_kafka_health(**context):
    """Check Kafka connectivity - imports moved inside function"""
    try:
        import socket

        host = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "host.docker.internal:19092").split(",")[0]
        target_host, target_port = host.split(":")
        with socket.create_connection((target_host, int(target_port)), timeout=5):
            logging.info("Kafka broker %s is reachable", host)
            return True
    except Exception as e:
        logging.error("Kafka health check failed: %s", e)
        raise


def check_postgres_health(**context):
    """Check PostgreSQL connectivity - imports moved inside function"""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=os.environ.get("POSTGRES_PORT", 5434),
            database=os.environ.get("POSTGRES_DATABASE", "crypto_db"),
            user=os.environ.get("POSTGRES_USER", "crypto_user"),
            password=os.environ.get("POSTGRES_PASSWORD", "cryptopass123"),
        )
        conn.close()
        logging.info("PostgreSQL is reachable")
        return True
    except Exception as e:
        logging.error("PostgreSQL health check failed: %s", e)
        raise


def run_producer_batch(**context):
    """Run the Coinbase producer for a batch of data"""
    _ = context and None

    # Import moved inside function to avoid module-level import issues
    try:
        import sys
        import importlib
        import asyncio

        # Add producer directory to path
        sys.path.insert(0, "/opt/airflow/producer")

        # Import and run the producer
        module = importlib.import_module("coinbase_producer")
        coinbase_producer_cls = getattr(module, "CoinbaseProducer")
    except (ImportError, AttributeError) as e:
        logging.error("Failed to import CoinbaseProducer: %s", e)
        return "Producer module not available"

    async def run_producer():
        producer = coinbase_producer_cls(max_duration=20)
        try:
            await producer.produce_prices()
        finally:
            producer.shutdown()

    asyncio.run(run_producer())
    return "Producer batch completed"


def run_consumer_batch(**context):
    """Run the PostgreSQL consumer for a batch of data"""
    _ = context and None

    # Import moved inside function to avoid module-level import issues
    try:
        import sys
        import importlib

        # Add consumer directory to path
        sys.path.insert(0, "/opt/airflow/consumer")

        # Import and run the consumer
        module = importlib.import_module("postgres_consumer")
        postgres_consumer_cls = getattr(module, "PostgresConsumer")
    except (ImportError, AttributeError) as e:
        logging.error("Failed to import PostgresConsumer: %s", e)
        return "Consumer module not available"

    def run_consumer_sync():
        consumer = postgres_consumer_cls(max_duration=20)
        try:
            consumer.consume()
        finally:
            consumer.shutdown()

    run_consumer_sync()
    return "Consumer batch completed"


def validate_data_quality(**context):
    """Validate data quality in PostgreSQL - imports moved inside function"""
    _ = context and None

    # Import moved inside function
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "host.docker.internal"),
        port=os.environ.get("POSTGRES_PORT", 5434),
        database=os.environ.get("POSTGRES_DATABASE", "crypto_db"),
        user=os.environ.get("POSTGRES_USER", "crypto_user"),
        password=os.environ.get("POSTGRES_PASSWORD", "cryptopass123"),
    )

    try:
        with conn.cursor() as cur:
            # Check for recent data
            cur.execute(
                """
                SELECT COUNT(*), MAX(time)
                FROM public.raw_crypto_prices_log
                WHERE time > NOW() - INTERVAL '10 seconds'
            """
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("No result returned for recent data check")
            count, max_timestamp = row

            if count == 0:
                raise ValueError("No recent data found in the last 10 seconds")

            logging.info(
                "Found %s records in the last 10 seconds. Latest: %s", count, max_timestamp
            )

            # Check for data anomalies
            cur.execute(
                """
                SELECT symbol, COUNT(*) as null_count
                FROM public.raw_crypto_prices_log
                WHERE time > NOW() - INTERVAL '60 seconds'
                  AND (price IS NULL OR volume IS NULL)
                GROUP BY symbol
            """
            )

            anomalies = cur.fetchall()
            if anomalies:
                logging.warning("Data quality issues found: %s", anomalies)

            return {"record_count": count, "latest_timestamp": str(max_timestamp)}
    finally:
        conn.close()


# Define tasks
with dag:
    # Health checks task group
    with TaskGroup("health_checks") as health_checks:
        kafka_health = PythonOperator(
            task_id="check_kafka_health",
            python_callable=check_kafka_health,
        )

        postgres_health = PythonOperator(
            task_id="check_postgres_health",
            python_callable=check_postgres_health,
        )

    # Producer task using DockerOperator
    producer_task = DockerOperator(
        task_id="run_producer_docker",
        image="crypto-producer:latest",
        api_version="auto",
        auto_remove=True,
        command="python coinbase_producer.py --duration 20",
        docker_url="unix://var/run/docker.sock",
        network_mode="crypto-network",
        environment={
            "KAFKA_BOOTSTRAP_SERVERS": "redpanda:9092",
            "KAFKA_TOPIC": "crypto_prices",
            "POLL_INTERVAL": "10",
        },
        mount_tmp_dir=False,
    )

    # Consumer task using DockerOperator
    consumer_task = DockerOperator(
        task_id="run_consumer_docker",
        image="crypto-consumer:latest",
        api_version="auto",
        auto_remove=True,
        command="python postgres_consumer.py --duration 20",
        docker_url="unix://var/run/docker.sock",
        network_mode="crypto-network",
        environment={
            "KAFKA_BOOTSTRAP_SERVERS": "redpanda:9092",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5434",
            "POSTGRES_DATABASE": "crypto_db",
            "POSTGRES_USER": "crypto_user",
            "POSTGRES_PASSWORD": "cryptopass123",
        },
        mount_tmp_dir=False,
    )

    # Data quality validation
    validate_data = PythonOperator(
        task_id="validate_data_quality",
        python_callable=validate_data_quality,
    )

    # Define task dependencies
    _ = health_checks >> producer_task >> consumer_task >> validate_data
