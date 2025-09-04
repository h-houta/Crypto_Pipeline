#!/usr/bin/env python3
"""
Throughput monitoring for Kafka to PostgreSQL pipeline
Tracks data flow, latency, and performance metrics
"""

import os
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict
from collections.abc import Mapping
import psycopg2
from psycopg2.extras import RealDictCursor
from confluent_kafka import Consumer, KafkaException
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ThroughputMonitor:
    """Monitor throughput between Kafka and PostgreSQL"""

    def __init__(self, config: Dict):
        self.config = config
        self.running = True
        self.metrics = {
            "kafka_messages": 0,
            "kafka_bytes": 0,
            "postgres_records": 0,
            "postgres_bytes": 0,
            "lag": 0,
            "errors": 0,
            "start_time": time.time(),
        }

        # Initialize connections
        self._init_connections()

        # Initialize Prometheus metrics
        self._init_prometheus_metrics()

    def _init_connections(self):
        """Initialize database and Kafka connections"""
        # PostgreSQL connection
        try:
            self.pg_conn = psycopg2.connect(
                host=self.config.get("postgres_host", "localhost"),
                port=self.config.get("postgres_port", 5432),
                database=self.config.get("postgres_db", "crypto_db"),
                user=self.config.get("postgres_user", "crypto_user"),
                password=self.config.get("postgres_password", "cryptopass123"),
                cursor_factory=RealDictCursor,
            )
            # Avoid transaction-aborted states on read-only metrics queries
            self.pg_conn.autocommit = True
            logger.info("Connected to PostgreSQL")
        except psycopg2.Error as e:
            logger.error("Failed to connect to PostgreSQL: %s", e)
            raise

        # Kafka consumer for monitoring
        try:
            kafka_config = {
                "bootstrap.servers": self.config.get("kafka_bootstrap_servers", "localhost:19092"),
                "group.id": "throughput-monitor",
                "enable.auto.commit": False,
                "auto.offset.reset": "latest",
            }
            self.kafka_consumer = Consumer(kafka_config)
            self.kafka_consumer.subscribe([self.config.get("kafka_topic", "crypto_prices")])
            logger.info("Connected to Kafka")
        except KafkaException as e:
            logger.error("Failed to connect to Kafka: %s", e)
            raise

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        # Counters
        self.kafka_messages_total = Counter(
            "kafka_messages_total", "Total number of messages consumed from Kafka"
        )
        self.kafka_bytes_total = Counter("kafka_bytes_total", "Total bytes consumed from Kafka")
        self.postgres_records_total = Counter(
            "postgres_records_total", "Total records written to PostgreSQL"
        )
        self.postgres_bytes_total = Counter(
            "postgres_bytes_total", "Total bytes written to PostgreSQL"
        )

        # Gauges
        self.kafka_lag_gauge = Gauge("kafka_consumer_lag", "Current Kafka consumer lag in messages")
        self.throughput_messages_gauge = Gauge(
            "throughput_messages_per_second", "Current throughput in messages per second"
        )
        self.throughput_bytes_gauge = Gauge(
            "throughput_mbytes_per_second", "Current throughput in MB per second"
        )
        self.postgres_connections_gauge = Gauge(
            "postgres_active_connections", "Number of active PostgreSQL connections"
        )

        # Histograms
        self.processing_latency = Histogram(
            "processing_latency_seconds",
            "Message processing latency",
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        )
        self.batch_size_histogram = Histogram(
            "batch_size",
            "Batch sizes for database writes",
            buckets=(1, 10, 25, 50, 100, 250, 500, 1000),
        )

    def calculate_kafka_lag(self) -> int:
        """Calculate current Kafka consumer lag"""
        try:
            # Get assigned partitions
            partitions = self.kafka_consumer.assignment()
            if not partitions:
                return 0

            total_lag = 0
            for partition in partitions:
                # Get current position
                committed = self.kafka_consumer.committed([partition])[0]
                if committed:
                    current_offset = committed.offset
                else:
                    current_offset = 0

                # Get high water mark
                _low, high = self.kafka_consumer.get_watermark_offsets(partition)
                lag = high - current_offset if high > current_offset else 0
                total_lag += lag

            return total_lag
        except KafkaException as e:
            logger.error("Error calculating Kafka lag: %s", e)
            return 0

    def get_postgres_metrics(self) -> Dict:
        """Get PostgreSQL performance metrics"""
        metrics = {}

        try:
            with self.pg_conn.cursor() as cursor:
                # Get table statistics
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_records,
                        pg_size_pretty(pg_total_relation_size('raw_crypto_prices_log'))
                        as table_size,
                        MAX(inserted_at) as last_insert,
                        COUNT(DISTINCT symbol) as unique_symbols
                    FROM raw_crypto_prices_log
                    WHERE inserted_at > NOW() - INTERVAL '5 minutes'
                """
                )
                metrics["table_stats"] = cursor.fetchone()

                # Get write throughput
                cursor.execute(
                    """
                    SELECT
                        date_trunc('minute', inserted_at) as minute,
                        COUNT(*) as records,
                        COUNT(DISTINCT symbol) as symbols,
                        AVG(pg_column_size(raw_crypto_prices_log.*)) as avg_row_size
                    FROM raw_crypto_prices_log
                    WHERE inserted_at > NOW() - INTERVAL '10 minutes'
                    GROUP BY minute
                    ORDER BY minute DESC
                    LIMIT 10
                """
                )
                metrics["write_throughput"] = cursor.fetchall()

                # Get connection stats
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_connections,
                        COUNT(*) FILTER (WHERE state = 'active') as active,
                        COUNT(*) FILTER (WHERE state = 'idle') as idle,
                        COUNT(*) FILTER (WHERE wait_event_type IS NOT NULL) as waiting
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """
                )
                metrics["connections"] = cursor.fetchone()

                # Get TimescaleDB chunk info (skip if extension not installed)
                try:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) as chunk_count,
                            pg_size_pretty(SUM(total_bytes)) as total_size,
                            pg_size_pretty(AVG(total_bytes)) as avg_chunk_size,
                            MIN(range_start) as oldest_chunk,
                            MAX(range_end) as newest_chunk
                        FROM timescaledb_information.chunks
                        WHERE hypertable_name = 'raw_crypto_prices_log'
                    """
                    )
                    metrics["chunks"] = cursor.fetchone()
                except psycopg2.Error:
                    metrics["chunks"] = None

                # Get compression stats if available
                try:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) as compressed_chunks,
                            pg_size_pretty(SUM(compressed_total_bytes)) as compressed_size,
                            pg_size_pretty(SUM(uncompressed_total_bytes)) as uncompressed_size,
                            AVG(compression_ratio)::numeric(5,2) as avg_compression_ratio
                        FROM timescaledb_information.compression_chunk_stats
                        WHERE hypertable_name = 'raw_crypto_prices_log'
                    """
                    )
                    metrics["compression"] = cursor.fetchone()
                except psycopg2.Error:
                    metrics["compression"] = None

        except psycopg2.Error as e:
            logger.error("Error getting PostgreSQL metrics: %s", e)

        return metrics

    def monitor_kafka_throughput(self):
        """Monitor Kafka message throughput"""
        message_count = 0
        byte_count = 0
        start_time = time.time()

        while self.running:
            try:
                msg = self.kafka_consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    logger.error("Kafka error: %s", msg.error())
                    self.metrics["errors"] += 1
                    continue

                # Update counters
                value = msg.value() or b""
                message_bytes = len(value)
                message_count += 1
                byte_count += message_bytes

                self.kafka_messages_total.inc()
                self.kafka_bytes_total.inc(message_bytes)

                # Calculate throughput every 100 messages
                if message_count % 100 == 0:
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        msg_per_sec = message_count / elapsed
                        mb_per_sec = (byte_count / 1024 / 1024) / elapsed

                        self.throughput_messages_gauge.set(msg_per_sec)
                        self.throughput_bytes_gauge.set(mb_per_sec)

                        logger.info(
                            "Kafka throughput: %.2f msg/s, %.2f MB/s", msg_per_sec, mb_per_sec
                        )

            except KafkaException as e:
                logger.error("Kafka monitoring error: %s", e)
                time.sleep(1)

    def monitor_postgres_throughput(self):
        """Monitor PostgreSQL write throughput"""
        last_count = 0
        last_check = time.time()

        while self.running:
            try:
                time.sleep(10)  # Check every 10 seconds

                with self.pg_conn.cursor() as cursor:
                    # Get current record count
                    cursor.execute(
                        """
                        SELECT COUNT(*) as count,
                               SUM(pg_column_size(raw_crypto_prices_log.*)) as total_bytes
                        FROM raw_crypto_prices_log
                        WHERE inserted_at > NOW() - INTERVAL '1 minute'
                    """
                    )
                    row = cursor.fetchone()

                    current_count = 0
                    current_bytes = 0
                    if row:
                        if isinstance(row, Mapping):
                            current_count = int(row.get("count") or 0)
                            current_bytes = int(row.get("total_bytes") or 0)
                        elif isinstance(row, (tuple, list)) and len(row) >= 2:
                            current_count = int(row[0] or 0)
                            current_bytes = int(row[1] or 0)

                    # Calculate throughput
                    elapsed = time.time() - last_check
                    if elapsed > 0:
                        delta_records = current_count - last_count
                        # Guard against negative deltas due to windowing or truncation
                        if delta_records < 0:
                            delta_records = 0
                        records_per_sec = delta_records / elapsed
                        mb_per_sec = (current_bytes / 1024 / 1024) / 60  # Last minute avg

                        if delta_records > 0:
                            self.postgres_records_total.inc(delta_records)
                        if current_bytes > 0:
                            self.postgres_bytes_total.inc(current_bytes)

                        logger.info(
                            "PostgreSQL throughput: %.2f rec/s, %.2f MB/s",
                            records_per_sec,
                            mb_per_sec,
                        )

                    last_count = current_count
                    last_check = time.time()

                    # Update connection gauge
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM pg_stat_activity
                        WHERE datname = current_database() AND state = 'active'
                    """
                    )
                    row = cursor.fetchone()
                    active_connections = 0
                    if row:
                        if isinstance(row, Mapping):
                            active_connections = int(row.get("count") or 0)
                        elif isinstance(row, (tuple, list)) and len(row) >= 1:
                            active_connections = int(row[0] or 0)
                    self.postgres_connections_gauge.set(active_connections)

            except psycopg2.Error as e:
                logger.error("PostgreSQL monitoring error: %s", e)
                # Attempt rollback; on failure, reinitialize connections
                try:
                    self.pg_conn.rollback()
                except psycopg2.Error as rollback_error:
                    logger.debug("Error during PostgreSQL rollback: %s", rollback_error)
                    self._init_connections()
                time.sleep(5)

    def monitor_lag(self):
        """Monitor end-to-end lag"""
        while self.running:
            try:
                time.sleep(30)  # Check every 30 seconds

                # Calculate Kafka lag
                kafka_lag = self.calculate_kafka_lag()
                self.kafka_lag_gauge.set(kafka_lag)

                # Get PostgreSQL lag (time since last insert)
                with self.pg_conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(inserted_at))) as lag_seconds
                        FROM raw_crypto_prices_log
                    """
                    )
                    row = cursor.fetchone()
                    pg_lag = 0.0
                    if row:
                        if isinstance(row, Mapping):
                            val = row.get("lag_seconds")
                            pg_lag = float(val) if val is not None else 0.0
                        elif isinstance(row, (tuple, list)) and len(row) >= 1:
                            val = row[0]
                            pg_lag = float(val) if val is not None else 0.0

                logger.info("Lag - Kafka: %d messages, PostgreSQL: %.2fs", kafka_lag, pg_lag)

                # Alert if lag is too high
                if kafka_lag > 10000:
                    logger.warning("High Kafka lag detected: %d messages", kafka_lag)
                if pg_lag > 60:
                    logger.warning("High PostgreSQL lag detected: %.2f seconds", pg_lag)

            except (psycopg2.Error, KafkaException) as e:
                logger.error("Lag monitoring error: %s", e)
                time.sleep(5)

    def generate_report(self) -> Dict:
        """Generate comprehensive throughput report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "runtime_seconds": time.time() - self.metrics["start_time"],
        }

        # Get PostgreSQL metrics
        pg_metrics = self.get_postgres_metrics()
        report["postgres"] = pg_metrics

        # Calculate Kafka metrics
        kafka_lag = self.calculate_kafka_lag()
        report["kafka"] = {
            "lag_messages": kafka_lag,
            "total_messages": self.metrics.get("kafka_messages", 0),
            "total_bytes": self.metrics.get("kafka_bytes", 0),
        }

        # Calculate throughput
        elapsed = time.time() - self.metrics["start_time"]
        if elapsed > 0:
            report["throughput"] = {
                "kafka_msg_per_sec": self.metrics.get("kafka_messages", 0) / elapsed,
                "kafka_mb_per_sec": (self.metrics.get("kafka_bytes", 0) / 1024 / 1024) / elapsed,
                "postgres_rec_per_sec": self.metrics.get("postgres_records", 0) / elapsed,
                "postgres_mb_per_sec": (self.metrics.get("postgres_bytes", 0) / 1024 / 1024)
                / elapsed,
            }

        return report

    def start(self):
        """Start monitoring threads"""
        # Start Prometheus metrics server
        start_http_server(9091)
        logger.info("Prometheus metrics server started on port 9091")

        # Start monitoring threads
        threads = [
            threading.Thread(target=self.monitor_kafka_throughput, name="kafka-monitor"),
            threading.Thread(target=self.monitor_postgres_throughput, name="postgres-monitor"),
            threading.Thread(target=self.monitor_lag, name="lag-monitor"),
        ]

        for thread in threads:
            thread.daemon = True
            thread.start()
            logger.info("Started %s", thread.name)

        # Main loop - generate reports
        try:
            while self.running:
                time.sleep(60)  # Generate report every minute
                report = self.generate_report()
                logger.info("Throughput Report: %s", json.dumps(report, indent=2, default=str))

                # Optionally send to monitoring system
                if self.config.get("grafana_webhook"):
                    self._send_to_grafana(report)

        except KeyboardInterrupt:
            logger.info("Shutting down monitor...")
            self.running = False

    def _send_to_grafana(self, report: Dict):
        """Send metrics to Grafana via webhook"""
        webhook_url = self.config.get("grafana_webhook")
        if not webhook_url:
            return

        try:
            response = requests.post(
                webhook_url, json=report, headers={"Content-Type": "application/json"}, timeout=5
            )
            if response.status_code != 200:
                logger.error("Failed to send to Grafana: %s", response.status_code)
        except requests.RequestException as e:
            logger.error("Error sending to Grafana: %s", e)


def main():
    """Main entry point"""
    config = {
        "postgres_host": os.getenv("POSTGRES_HOST", "localhost"),
        "postgres_port": int(os.getenv("POSTGRES_PORT", "5434")),
        "postgres_db": os.getenv("POSTGRES_DB", "crypto_db"),
        "postgres_user": os.getenv("POSTGRES_USER", "crypto_user"),
        "postgres_password": os.getenv("POSTGRES_PASSWORD", "cryptopass123"),
        "kafka_bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"),
        "kafka_topic": os.getenv("KAFKA_TOPIC", "crypto_prices"),
        "grafana_webhook": os.getenv("GRAFANA_WEBHOOK_URL"),
    }

    monitor = ThroughputMonitor(config)
    monitor.start()


if __name__ == "__main__":
    main()
