"""
Configuration for Coinbase Producer
"""

import os
from typing import Dict, Any, List
from pydantic_settings import BaseSettings


class ProducerConfig(BaseSettings):
    """Producer configuration with environment variable support"""

    # Kafka Configuration
    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_topic: str = "crypto_prices"

    # Coinbase API Configuration
    coinbase_api_base: str = "https://api.coinbase.com/v2/prices"
    crypto_symbols: str = "BTC-USD,ETH-USD,SOL-USD,DOGE-USD"  # Changed to string
    poll_interval: int = 10  # seconds

    # Producer Settings
    batch_size: int = 16384
    linger_ms: int = 5
    compression_type: str = "lz4"

    # Retry Configuration
    max_retries: int = 3
    retry_backoff_ms: int = 1000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra fields from .env file
        case_sensitive = False

    def get_crypto_symbols_list(self) -> List[str]:
        """Parse crypto_symbols string into a list"""
        return [s.strip() for s in self.crypto_symbols.split(",")]

    def get_kafka_config(self) -> Dict[str, Any]:
        """Get Kafka producer configuration"""
        return {
            "bootstrap.servers": self.kafka_bootstrap_servers,
            "client.id": "coinbase-producer",
            # Idempotent producer settings for exactly-once semantics
            "enable.idempotence": True,
            "acks": "all",
            "retries": 2147483647,  # Max retries
            "max.in.flight.requests.per.connection": 5,
            # Performance optimizations
            "compression.type": self.compression_type,
            "batch.size": self.batch_size,
            "linger.ms": self.linger_ms,
            # Timeouts
            "delivery.timeout.ms": 120000,
            "request.timeout.ms": 30000,
            "retry.backoff.ms": self.retry_backoff_ms,
        }


# Create global config instance
config = ProducerConfig()
