#!/usr/bin/env python3
"""
Kafka Consumer Pool with Round-Robin Load Balancing
Distributes message processing across multiple consumer instances
"""

import os
import sys
import time
import json
import logging
import signal
import threading
import multiprocessing
import argparse
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from queue import Queue, Empty
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from confluent_kafka import Consumer, KafkaError, TopicPartition
from prometheus_client import Counter, Gauge, Histogram, start_http_server

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(process)d - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ConsumerMetrics:
    """Metrics for consumer performance tracking"""

    messages_processed: int = 0
    bytes_processed: int = 0
    errors: int = 0
    start_time: float = 0
    last_commit_time: float = 0


class RoundRobinConsumer:
    """Single consumer instance with round-robin partition assignment"""

    def __init__(self, consumer_id: int, config: Dict, partition_queue: Queue):
        self.consumer_id = consumer_id
        self.config = config
        self.partition_queue = partition_queue
        self.running = True
        self.metrics = ConsumerMetrics(start_time=time.time())

        # Initialize Kafka consumer
        self._init_consumer()

        # Initialize database connection
        self._init_database()

        # Message batch
        self.batch = []
        self.batch_size = config.get("batch_size", 10)
        self.commit_interval = config.get("commit_interval", 5)

    def _init_consumer(self):
        """Initialize Kafka consumer with manual partition assignment"""
        kafka_config = {
            "bootstrap.servers": self.config.get("kafka_bootstrap_servers", "localhost:19092"),
            "group.id": f"{self.config.get('group_id', 'consumer-pool')}-{self.consumer_id}",
            "client.id": f"consumer-{self.consumer_id}",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "isolation.level": "read_committed",
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 60000,
            "heartbeat.interval.ms": 3000,
            "enable.partition.eof": False,
        }

        # Add SSL/TLS configuration if enabled
        if self.config.get("ssl_enabled"):
            kafka_config.update(
                {
                    "security.protocol": "SSL",
                    "ssl.ca.location": self.config.get("ssl_ca_location"),
                    "ssl.certificate.location": self.config.get("ssl_cert_location"),
                    "ssl.key.location": self.config.get("ssl_key_location"),
                    "ssl.key.password": self.config.get("ssl_key_password"),
                }
            )

        self.consumer = Consumer(kafka_config)
        logger.info(f"Consumer {self.consumer_id} initialized")

    def _init_database(self):
        """Initialize database connection with connection pooling"""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.db_conn = psycopg2.connect(
                    host=self.config.get("postgres_host", "localhost"),
                    port=self.config.get("postgres_port", 5432),
                    database=self.config.get("postgres_db", "crypto_db"),
                    user=self.config.get("postgres_user", "crypto_user"),
                    password=self.config.get("postgres_password", "cryptopass123"),
                    cursor_factory=RealDictCursor,
                    connect_timeout=10,
                )
                self.db_conn.autocommit = False
                logger.info(f"Consumer {self.consumer_id} connected to database")
                return
            except psycopg2.Error as e:
                logger.error(
                    f"Consumer {self.consumer_id} DB connection attempt {attempt + 1} failed: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2

        raise ConnectionError(f"Consumer {self.consumer_id} failed to connect to database")

    def assign_partitions(self, partitions: List[TopicPartition]):
        """Assign specific partitions to this consumer"""
        self.consumer.assign(partitions)
        logger.info(
            f"Consumer {self.consumer_id} assigned partitions: {[p.partition for p in partitions]}"
        )

    def process_message(self, message) -> bool:
        """Process a single message"""
        try:
            # Parse message
            data = json.loads(message.value().decode("utf-8"))

            # Add to batch
            self.batch.append(
                {
                    "timestamp": data.get("timestamp"),
                    "symbol": data.get("symbol"),
                    "price": data.get("price"),
                    "volume": data.get("volume", 0),
                    "bid": data.get("bid"),
                    "ask": data.get("ask"),
                    "exchange": data.get("source", "coinbase"),
                    "partition": message.partition(),
                    "offset": message.offset(),
                }
            )

            # Update metrics
            self.metrics.messages_processed += 1
            self.metrics.bytes_processed += len(message.value())

            # Check if batch should be flushed
            if (
                len(self.batch) >= self.batch_size
                or time.time() - self.metrics.last_commit_time > self.commit_interval
            ):
                self.flush_batch()

            return True

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Consumer {self.consumer_id} failed to process message: {e}")
            self.metrics.errors += 1
            return False

    def flush_batch(self):
        """Flush batch to database (APPEND-ONLY)"""
        if not self.batch:
            return

        try:
            with self.db_conn.cursor() as cursor:
                # APPEND-ONLY insert
                execute_values(
                    cursor,
                    """
                    INSERT INTO raw_crypto_prices_log
                    (time, symbol, price, volume, bid, ask, exchange)
                    VALUES %s
                    """,
                    [
                        (
                            item["timestamp"],
                            item["symbol"],
                            item["price"],
                            item["volume"],
                            item["bid"],
                            item["ask"],
                            item["exchange"],
                        )
                        for item in self.batch
                    ],
                    template="(%s::timestamptz, %s, %s, %s, %s, %s, %s)",
                )

                # Commit transaction
                self.db_conn.commit()

                # Commit Kafka offsets
                self.consumer.commit()

                batch_size = len(self.batch)
                logger.info(f"Consumer {self.consumer_id} flushed {batch_size} messages")

                # Clear batch
                self.batch = []
                self.metrics.last_commit_time = time.time()

        except psycopg2.Error as e:
            logger.error(f"Consumer {self.consumer_id} database error: {e}")
            self.db_conn.rollback()
            self.metrics.errors += 1
            # Reconnect if needed
            if self.db_conn.closed:
                self._init_database()

    def run(self):
        """Main consumer loop"""
        logger.info(f"Consumer {self.consumer_id} starting...")

        while self.running:
            try:
                # Check for new partition assignments
                try:
                    new_partitions = self.partition_queue.get_nowait()
                    if new_partitions:
                        self.assign_partitions(new_partitions)
                except Empty:
                    pass

                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    # Flush partial batch if needed
                    if (
                        self.batch
                        and time.time() - self.metrics.last_commit_time > self.commit_interval
                    ):
                        self.flush_batch()
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            f"Consumer {self.consumer_id} reached end of partition {msg.partition()}"
                        )
                    else:
                        logger.error(f"Consumer {self.consumer_id} error: {msg.error()}")
                        self.metrics.errors += 1
                    continue

                # Process message
                self.process_message(msg)

            except Exception as e:
                logger.error(f"Consumer {self.consumer_id} error: {e}")
                self.metrics.errors += 1
                time.sleep(1)

        # Final flush
        self.flush_batch()
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        logger.info(f"Consumer {self.consumer_id} cleaning up...")

        # Close Kafka consumer
        if self.consumer:
            self.consumer.close()

        # Close database connection
        if self.db_conn and not self.db_conn.closed:
            self.db_conn.close()

        # Log final metrics
        runtime = time.time() - self.metrics.start_time
        logger.info(
            f"Consumer {self.consumer_id} stopped. "
            f"Processed: {self.metrics.messages_processed} messages, "
            f"Throughput: {self.metrics.messages_processed / runtime:.2f} msg/s, "
            f"Errors: {self.metrics.errors}"
        )

    def stop(self):
        """Signal consumer to stop"""
        self.running = False


class ConsumerPool:
    """Manages a pool of consumers with round-robin load balancing"""

    def __init__(self, config: Dict):
        self.config = config
        self.num_consumers = config.get("num_consumers", multiprocessing.cpu_count())
        self.topic = config.get("topic", "crypto_prices")
        self.consumers: List[RoundRobinConsumer] = []
        self.partition_queues: List[Queue] = []
        self.running = True

        # Metrics
        self._init_metrics()

        # Thread pool for consumer management
        self.executor = ThreadPoolExecutor(max_workers=self.num_consumers)

        logger.info(f"Initializing consumer pool with {self.num_consumers} consumers")

    def _init_metrics(self):
        """Initialize Prometheus metrics"""
        self.messages_counter = Counter(
            "consumer_pool_messages_total",
            "Total messages processed by consumer pool",
            ["consumer_id"],
        )
        self.errors_counter = Counter(
            "consumer_pool_errors_total", "Total errors in consumer pool", ["consumer_id"]
        )
        self.active_consumers_gauge = Gauge(
            "consumer_pool_active_consumers", "Number of active consumers"
        )
        self.partition_lag_gauge = Gauge(
            "consumer_pool_partition_lag", "Consumer lag per partition", ["partition"]
        )

    def get_partition_assignment(self) -> Dict[int, List[TopicPartition]]:
        """Get round-robin partition assignment for consumers"""
        # Get topic metadata
        admin_consumer = Consumer(
            {
                "bootstrap.servers": self.config.get("kafka_bootstrap_servers", "localhost:19092"),
                "group.id": "admin-temp",
            }
        )

        metadata = admin_consumer.list_topics(topic=self.topic)
        topic_metadata = metadata.topics[self.topic]
        partitions = list(topic_metadata.partitions.keys())
        admin_consumer.close()

        logger.info(f"Topic {self.topic} has {len(partitions)} partitions")

        # Round-robin assignment
        assignments = {i: [] for i in range(self.num_consumers)}
        for idx, partition in enumerate(partitions):
            consumer_id = idx % self.num_consumers
            assignments[consumer_id].append(TopicPartition(self.topic, partition))

        # Log assignment
        for consumer_id, parts in assignments.items():
            logger.info(
                f"Consumer {consumer_id} assigned {len(parts)} partitions: {[p.partition for p in parts]}"
            )

        return assignments

    def rebalance_partitions(self):
        """Rebalance partitions across consumers"""
        logger.info("Rebalancing partitions...")

        assignments = self.get_partition_assignment()

        # Send new assignments to consumers
        for consumer_id, partitions in assignments.items():
            if consumer_id < len(self.partition_queues):
                self.partition_queues[consumer_id].put(partitions)

        logger.info("Partition rebalancing complete")

    def monitor_consumers(self):
        """Monitor consumer health and performance"""
        while self.running:
            try:
                time.sleep(15)  # Check every 30 seconds

                active_count = sum(1 for c in self.consumers if c.running)
                self.active_consumers_gauge.set(active_count)

                # Check for failed consumers
                if active_count < self.num_consumers:
                    logger.warning(f"Only {active_count}/{self.num_consumers} consumers active")
                    # Trigger rebalancing
                    self.rebalance_partitions()

                # Log aggregate metrics
                total_messages = sum(c.metrics.messages_processed for c in self.consumers)
                total_errors = sum(c.metrics.errors for c in self.consumers)

                logger.info(
                    f"Consumer Pool Status - Active: {active_count}, "
                    f"Messages: {total_messages}, Errors: {total_errors}"
                )

            except Exception as e:
                logger.error(f"Monitor error: {e}")

    def start(self):
        """Start the consumer pool"""
        # Start Prometheus metrics server
        start_http_server(9092)
        logger.info("Prometheus metrics server started on port 9092")

        # Get initial partition assignment
        assignments = self.get_partition_assignment()

        # Create and start consumers
        futures = []
        for consumer_id in range(self.num_consumers):
            # Create partition queue for this consumer
            partition_queue = Queue()
            partition_queue.put(assignments[consumer_id])
            self.partition_queues.append(partition_queue)

            # Create consumer
            consumer = RoundRobinConsumer(consumer_id, self.config, partition_queue)
            self.consumers.append(consumer)

            # Start consumer in thread pool
            future = self.executor.submit(consumer.run)
            futures.append(future)

        # Update metrics
        self.active_consumers_gauge.set(self.num_consumers)

        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_consumers)
        monitor_thread.daemon = True
        monitor_thread.start()

        logger.info(f"Consumer pool started with {self.num_consumers} consumers")

        # Wait for consumers
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down consumer pool...")
            self.stop()

    def stop(self):
        """Stop all consumers"""
        self.running = False

        # Stop all consumers
        for consumer in self.consumers:
            consumer.stop()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        logger.info("Consumer pool stopped")


class ConsumerPoolManager:
    """Manages multiple consumer pools for different topics"""

    def __init__(self, config: Dict):
        self.config = config
        self.pools: Dict[str, ConsumerPool] = {}

    def create_pool(self, topic: str, num_consumers: Optional[int] = None) -> ConsumerPool:
        """Create a consumer pool for a topic"""
        pool_config = self.config.copy()
        pool_config["topic"] = topic
        if num_consumers:
            pool_config["num_consumers"] = num_consumers

        pool = ConsumerPool(pool_config)
        self.pools[topic] = pool

        logger.info(f"Created consumer pool for topic: {topic}")
        return pool

    def start_all(self):
        """Start all consumer pools"""
        for topic, pool in self.pools.items():
            thread = threading.Thread(target=pool.start, name=f"pool-{topic}")
            thread.start()
            logger.info(f"Started pool for topic: {topic}")

    def stop_all(self):
        """Stop all consumer pools"""
        for topic, pool in self.pools.items():
            pool.stop()
            logger.info(f"Stopped pool for topic: {topic}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Kafka Consumer Pool with Round-Robin Load Balancing"
    )
    parser.add_argument(
        "--consumers", type=int, help="Number of consumers", default=multiprocessing.cpu_count()
    )
    parser.add_argument("--topic", help="Kafka topic", default="crypto_prices")
    parser.add_argument("--batch-size", type=int, help="Batch size", default=15)
    parser.add_argument("--ssl", action="store_true", help="Enable SSL/TLS")

    args = parser.parse_args()

    # Configuration
    config = {
        "num_consumers": args.consumers,
        "topic": args.topic,
        "batch_size": args.batch_size,
        "commit_interval": 5,
        "kafka_bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"),
        "group_id": os.getenv("KAFKA_GROUP_ID", "consumer-pool"),
        "postgres_host": os.getenv("POSTGRES_HOST", "localhost"),
        "postgres_port": int(os.getenv("POSTGRES_PORT", 5434)),
        "postgres_db": os.getenv("POSTGRES_DB", "crypto_db"),
        "postgres_user": os.getenv("POSTGRES_USER", "crypto_user"),
        "postgres_password": os.getenv("POSTGRES_PASSWORD", "cryptopass123"),
        "ssl_enabled": args.ssl,
    }

    if args.ssl:
        config.update(
            {
                "ssl_ca_location": os.getenv("SSL_CA_LOCATION", "./certs/ca-cert.pem"),
                "ssl_cert_location": os.getenv("SSL_CERT_LOCATION", "./certs/client-cert.pem"),
                "ssl_key_location": os.getenv("SSL_KEY_LOCATION", "./certs/client-key.pem"),
                "ssl_key_password": os.getenv("SSL_KEY_PASSWORD"),
            }
        )

    # Signal handler
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        pool.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start consumer pool
    pool = ConsumerPool(config)
    pool.start()


if __name__ == "__main__":
    main()
