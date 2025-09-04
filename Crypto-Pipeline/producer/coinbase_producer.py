"""
Coinbase API Producer for Kafka
Optimized for ARM64 Mac
"""

import asyncio
import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx
from prometheus_client import start_http_server, Counter
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

# Prefer absolute import; if running as a script, adjust sys.path and retry
try:
    from producer.config import config  # pyright-friendly in package/module contexts
except Exception:  # pragma: no cover - setup fallback for script execution
    import os
    import sys as _sys

    _sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from producer.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CoinbaseProducer:
    """
    High-performance Coinbase price producer with idempotent guarantees
    """

    def __init__(self, max_duration=None):
        """Initialize producer with idempotent configuration

        Args:
            max_duration: Maximum duration to run in seconds (None for unlimited)
        """
        self.kafka_config = config.get_kafka_config()
        self.producer = Producer(self.kafka_config)
        self.http_client = None
        self.running = True
        self.delivered_count = 0
        self.error_count = 0
        self.max_duration = max_duration

        # Create topics if they don't exist
        self._ensure_topics_exist()

        # Statistics
        self.start_time = time.time()

        # Prometheus metrics
        self.messages_produced_total = Counter(
            "messages_produced_total", "Total number of messages produced"
        )
        self.producer_errors_total = Counter(
            "producer_errors_total", "Total number of producer errors"
        )

    def _ensure_topics_exist(self):
        """Create Kafka topics with proper configuration"""
        admin = AdminClient({"bootstrap.servers": config.kafka_bootstrap_servers})

        topics = [
            NewTopic(
                topic=config.kafka_topic,
                num_partitions=6,
                replication_factor=1,
                config={
                    "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days
                    "compression.type": config.compression_type,
                    "cleanup.policy": "delete",
                    "segment.ms": str(60 * 60 * 1000),  # 1 hour
                    "min.insync.replicas": "1",
                },
            )
        ]

        # Create topics, ignore if already exist
        fs = admin.create_topics(topics)
        for topic, f in fs.items():
            try:
                f.result()
                logger.info(f"Topic {topic} created successfully")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.error(f"Failed to create topic {topic}: {e}")
                else:
                    logger.info(f"Topic {topic} already exists")

    async def fetch_price(
        self, session: httpx.AsyncClient, symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch current price from Coinbase API"""
        max_retries = config.max_retries
        retry_count = 0

        while retry_count < max_retries:
            try:
                url = f"{config.coinbase_api_base}/{symbol}/spot"
                response = await session.get(url, timeout=5.0)

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "symbol": symbol,
                        "price": float(data["data"]["amount"]),
                        "currency": data["data"]["currency"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "coinbase_spot",
                        "fetch_latency_ms": int(response.elapsed.total_seconds() * 1000),
                    }
                elif response.status_code == 429:  # Rate limited
                    logger.warning(f"Rate limited for {symbol}, backing off...")
                    await asyncio.sleep(2**retry_count)
                    retry_count += 1
                else:
                    logger.error(f"API error for {symbol}: {response.status_code}")
                    return None

            except httpx.TimeoutException:
                logger.error(f"Timeout fetching {symbol} (attempt {retry_count + 1})")
                retry_count += 1
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                return None

        return None

    def delivery_callback(self, err, msg):
        """Callback for message delivery confirmation"""
        if err:
            self.producer_errors_total.inc()
            self.error_count += 1
            logger.error(f"Message delivery failed: {err}")
        else:
            self.messages_produced_total.inc()
            self.delivered_count += 1
            if self.delivered_count % 100 == 0:
                elapsed = time.time() - self.start_time
                rate = self.delivered_count / elapsed
                logger.info(
                    f"Delivered: {self.delivered_count} messages "
                    f"({rate:.2f} msg/sec, {self.error_count} errors)"
                )

    async def produce_prices(self):
        """Main production loop"""
        logger.info(f"Starting producer for symbols: {config.get_crypto_symbols_list()}")
        logger.info(f"Polling interval: {config.poll_interval} seconds")
        if self.max_duration:
            logger.info(f"Max duration: {self.max_duration} seconds")

        async with httpx.AsyncClient() as session:
            self.http_client = session

            while self.running:
                # Check if max duration reached
                if self.max_duration and (time.time() - self.start_time) >= self.max_duration:
                    logger.info(f"Max duration of {self.max_duration}s reached, stopping...")
                    self.running = False
                    break

                try:
                    start_time = time.time()

                    # Fetch all prices concurrently
                    tasks = [
                        self.fetch_price(session, symbol)
                        for symbol in config.get_crypto_symbols_list()
                    ]
                    prices = await asyncio.gather(*tasks, return_exceptions=True)

                    # Send to Kafka
                    successful_fetches = 0
                    for i, price_data in enumerate(prices):
                        if isinstance(price_data, Exception):
                            logger.error(
                                f"Error fetching {config.get_crypto_symbols_list()[i]}: {price_data}"
                            )
                            continue

                        if not isinstance(price_data, dict):
                            # Skip None or any unexpected type
                            continue

                        successful_fetches += 1

                        # Create idempotent key (unique per symbol and timestamp)
                        key = f"{price_data['symbol']}_{price_data['timestamp']}"

                        # Produce message
                        self.producer.produce(
                            topic=config.kafka_topic,
                            key=key.encode("utf-8"),
                            value=json.dumps(price_data).encode("utf-8"),
                            callback=self.delivery_callback,
                            timestamp=int(time.time() * 1000),  # Add Kafka timestamp
                        )

                    # Trigger any queued messages
                    self.producer.poll(0)

                    # Log batch statistics
                    fetch_time = time.time() - start_time
                    logger.info(
                        "Produced %d/%d price updates in %.2fs",
                        successful_fetches,
                        len(config.get_crypto_symbols_list()),
                        fetch_time,
                    )

                    # Calculate sleep time to maintain consistent interval
                    sleep_time = max(0, config.poll_interval - fetch_time)
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

                except asyncio.CancelledError:
                    logger.info("Producer task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Production cycle failed: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Brief pause before retry

    def flush_and_close(self):
        """Flush pending messages and close producer"""
        logger.info("Flushing pending messages...")

        # Flush with 10 second timeout
        remaining = self.producer.flush(10)

        if remaining > 0:
            logger.warning(f"Failed to deliver {remaining} messages")
        else:
            logger.info("All messages delivered successfully")

        # Log final statistics
        elapsed = time.time() - self.start_time
        logger.info(
            f"Final stats: {self.delivered_count} delivered, "
            f"{self.error_count} errors in {elapsed:.1f}s "
            f"({self.delivered_count/elapsed:.2f} msg/sec average)"
        )

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down producer...")
        self.running = False
        self.flush_and_close()


async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Coinbase Crypto Price Producer")
    parser.add_argument(
        "--duration",
        type=int,
        help="Maximum duration to run in seconds (default: unlimited)",
        default=None,
    )
    args = parser.parse_args()

    producer = CoinbaseProducer(max_duration=args.duration)

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        producer.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run producer
    try:
        await producer.produce_prices()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        producer.shutdown()


if __name__ == "__main__":
    # Start Prometheus metrics server for producer on :8000
    try:
        start_http_server(8000)
        logger.info("Producer metrics server started on :8000")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")

    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
