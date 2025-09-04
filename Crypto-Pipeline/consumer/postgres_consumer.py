"""
Kafka to PostgreSQL Consumer with exactly-once semantics
"""

import argparse
import json
import logging
import signal
import sys
import time

import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from confluent_kafka import Consumer, KafkaError
from config import config  # Import our configuration
from prometheus_client import start_http_server, Counter

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Prefer public constant if available; fallback to private without direct attribute access
PARTITION_EOF = getattr(KafkaError, "PARTITION_EOF", getattr(KafkaError, "_PARTITION_EOF", None))


def is_partition_eof_error(error) -> bool:
    """Return True if the given Kafka error represents end-of-partition.

    This avoids direct access to protected members by preferring a public
    constant when available and falling back to error name/string matching.
    """
    if PARTITION_EOF is not None:
        code_func = getattr(error, "code", None)
        if callable(code_func):
            return code_func() == PARTITION_EOF

    # Fallbacks without touching protected members
    name_func = getattr(error, "name", None)
    if callable(name_func):
        return name_func() == "PARTITION_EOF"

    return "PARTITION_EOF" in str(error)


class PostgresConsumer:
    """
    Consumer with exactly-once delivery to PostgreSQL
    ENFORCES APPEND-ONLY PATTERN - No updates or deletes allowed
    """

    def __init__(self, max_duration=None):
        """Initialize consumer with transaction isolation

        Args:
            max_duration: Maximum duration to run in seconds (None for unlimited)
        """
        self.kafka_config = config.get_kafka_config()
        self.consumer = Consumer(self.kafka_config)
        self.consumer.subscribe([config.kafka_topic])

        # Database connection
        self.conn = None
        self.connect_db()

        self.running = True
        self.processed_count = 0
        self.batch = []
        self.last_commit_time = time.time()
        self.max_duration = max_duration
        self.start_time = time.time()

        # Throughput tracking
        self.throughput_stats = {
            "total_bytes": 0,
            "total_messages": 0,
            "start_time": time.time(),
            "last_report_time": time.time(),
        }

        # Prometheus metrics
        self.messages_consumed_total = Counter(
            "messages_consumed_total", "Total number of messages consumed"
        )
        self.consumer_errors_total = Counter(
            "consumer_errors_total", "Total number of consumer errors"
        )
        self.batches_flushed_total = Counter(
            "batches_flushed_total", "Total number of batches flushed to PostgreSQL"
        )

    def connect_db(self):
        """Establish database connection with retry logic"""
        max_retries = 5
        for i in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=config.postgres_host,
                    port=config.postgres_port,
                    database=config.postgres_database,
                    user=config.postgres_user,
                    password=config.postgres_password,
                    cursor_factory=RealDictCursor,
                )
                self.conn.autocommit = False
                logger.info("Connected to PostgreSQL")
                self._ensure_table_exists()
                return
            except psycopg2.Error as e:
                logger.error("DB connection attempt %d failed: %s", i + 1, e)
                if i < max_retries - 1:
                    time.sleep(5)

        raise ConnectionError("Failed to connect to database")

    def _ensure_table_exists(self):
        """Ensure the raw_crypto_prices_log table exists"""
        if not self.conn:
            raise ConnectionError("No database connection")
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_crypto_prices_log (
                    id BIGSERIAL PRIMARY KEY,
                    time TIMESTAMPTZ NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    price DECIMAL(20,8) NOT NULL,
                    volume DECIMAL(30,8) DEFAULT 0,
                    exchange VARCHAR(50) DEFAULT 'coinbase',
                    inserted_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_crypto_time
                ON raw_crypto_prices_log(time DESC);

                CREATE INDEX IF NOT EXISTS idx_crypto_symbol
                ON raw_crypto_prices_log(symbol, time DESC);
            """
            )
            self.conn.commit()
            logger.info("Database schema verified")

    def process_message(self, msg) -> bool:
        """
        Add message to batch for processing
        APPEND-ONLY: Messages are never modified after receipt
        """
        try:
            # Parse message
            message_bytes = msg.value()
            price_data = json.loads(message_bytes.decode("utf-8"))

            # Track message size for throughput monitoring
            self.throughput_stats["total_bytes"] += len(message_bytes)
            self.throughput_stats["total_messages"] += 1

            # Count successfully parsed message
            self.messages_consumed_total.inc()

            # Add to batch (APPEND-ONLY - no modification of existing records)
            self.batch.append(
                {
                    "timestamp": price_data.get("timestamp"),
                    "symbol": price_data.get("symbol"),
                    "price": price_data.get("price"),
                    "volume": price_data.get("volume", 0),
                    "source": price_data.get("source", "coinbase"),
                    "offset": msg.offset(),
                    "partition": msg.partition(),
                }
            )

            # Process batch if it's full or time to commit
            if (
                len(self.batch) >= config.batch_size
                or time.time() - self.last_commit_time > config.commit_interval
            ):
                self.flush_batch()

            return True

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to process message: %s", e)
            self.consumer_errors_total.inc()
            return False

    def flush_batch(self):
        """
        Write batch to database and commit offsets
        IMPORTANT: This method enforces APPEND-ONLY pattern
        No UPDATE or DELETE operations are allowed
        """
        if not self.batch:
            return

        try:
            if not self.conn:
                raise ConnectionError("No database connection")
            with self.conn.cursor() as cursor:
                # APPEND-ONLY: Using INSERT only, no UPSERT/UPDATE/DELETE
                # Batch insert using execute_values for better performance
                execute_values(
                    cursor,
                    """
                    INSERT INTO raw_crypto_prices_log (time, symbol, price, volume, exchange)
                    VALUES %s
                    -- APPEND-ONLY: No ON CONFLICT clause to prevent updates
                    -- All records are immutable once written
                    """,
                    [
                        (
                            item["timestamp"],
                            item["symbol"],
                            item["price"],
                            item["volume"],
                            item["source"],
                        )
                        for item in self.batch
                    ],
                    template="(%s::timestamptz, %s, %s, %s, %s)",
                )

                # Track throughput metrics
                batch_size = len(self.batch)
                current_time = time.time()
                elapsed = current_time - self.last_commit_time
                throughput = batch_size / elapsed if elapsed > 0 else 0

                # Commit database transaction
                self.conn.commit()

                # Commit Kafka offsets
                self.consumer.commit()

                self.processed_count += batch_size
                self.batches_flushed_total.inc()

                # Log with throughput metrics
                logger.info(
                    "Flushed batch of %d messages. Total processed: %d, Throughput: %.2f msg/s",
                    batch_size,
                    self.processed_count,
                    throughput,
                )

                # Clear batch and reset timer
                self.batch = []
                self.last_commit_time = time.time()

        except psycopg2.Error as e:
            logger.error("Failed to flush batch: %s", e)
            self.consumer_errors_total.inc()
            if self.conn:
                self.conn.rollback()
            # Keep messages in batch for retry

    def consume(self):
        """Main consumption loop"""
        logger.info("Starting consumer for topic: %s", config.kafka_topic)
        if self.max_duration:
            logger.info("Max duration: %d seconds", self.max_duration)

        while self.running:
            # Check if max duration reached
            if self.max_duration and (time.time() - self.start_time) >= self.max_duration:
                logger.info("Max duration of %ds reached, stopping...", self.max_duration)
                self.running = False
                break
            try:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    # Check if we need to flush partial batch
                    if self.batch and time.time() - self.last_commit_time > config.commit_interval:
                        self.flush_batch()
                    continue

                if msg.error():
                    # Detect end-of-partition without referencing protected members
                    err = msg.error()
                    if is_partition_eof_error(err):
                        logger.debug("Reached end of partition %d", msg.partition())
                    else:
                        logger.error("Consumer error: %s", err)
                        self.consumer_errors_total.inc()
                    continue

                # Process message
                self.process_message(msg)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except (psycopg2.Error, ConnectionError) as e:
                logger.error("Consumption error: %s", e)
                self.consumer_errors_total.inc()
                time.sleep(1)

            # Report throughput metrics periodically
            if self.processed_count > 0 and self.processed_count % 1000 == 0:
                metrics = self.get_throughput_metrics()
                logger.info(
                    "Throughput Report - Messages: %d, Avg: %.2f msg/s, %.2f MB/s",
                    metrics["total_messages"],
                    metrics["avg_messages_per_sec"],
                    metrics["avg_mb_per_sec"],
                )

        # Final flush before shutdown
        self.flush_batch()

    def get_throughput_metrics(self) -> dict:
        """Calculate and return throughput metrics"""
        current_time = time.time()
        elapsed_total = current_time - self.throughput_stats["start_time"]

        metrics = {
            "total_messages": self.throughput_stats["total_messages"],
            "total_bytes": self.throughput_stats["total_bytes"],
            "avg_messages_per_sec": (
                self.throughput_stats["total_messages"] / elapsed_total if elapsed_total > 0 else 0
            ),
            "avg_bytes_per_sec": (
                self.throughput_stats["total_bytes"] / elapsed_total if elapsed_total > 0 else 0
            ),
            "avg_mb_per_sec": (
                (self.throughput_stats["total_bytes"] / 1024 / 1024) / elapsed_total
                if elapsed_total > 0
                else 0
            ),
            "runtime_seconds": elapsed_total,
        }

        self.throughput_stats["last_report_time"] = current_time
        return metrics

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down consumer...")
        self.running = False

        # Flush any remaining messages
        if self.batch:
            self.flush_batch()

        # Close connections
        self.consumer.close()
        if self.conn:
            self.conn.close()

        # Final throughput report
        metrics = self.get_throughput_metrics()
        logger.info(
            "Shutdown complete. Total processed: %d messages, "
            "Avg throughput: %.2f msg/s, %.2f MB/s",
            self.processed_count,
            metrics["avg_messages_per_sec"],
            metrics["avg_mb_per_sec"],
        )


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PostgreSQL Crypto Consumer")
    parser.add_argument(
        "--duration",
        type=int,
        help="Maximum duration to run in seconds (default: unlimited)",
        default=None,
    )
    args = parser.parse_args()

    # Create consumer
    consumer = PostgresConsumer(max_duration=args.duration)

    # Handle shutdown signals
    def signal_handler(sig, _frame):
        logger.info("Received signal %s", sig)
        consumer.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start Prometheus metrics server for consumer on :8001
    try:
        start_http_server(8001)
        logger.info("Consumer metrics server started on :8001")
    except Exception as e:
        logger.error("Failed to start metrics server: %s", e)

    # Run consumer
    try:
        consumer.consume()
    except (ConnectionError, psycopg2.Error) as e:
        logger.error("Fatal error: %s", e)
        consumer.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
