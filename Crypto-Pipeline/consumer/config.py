"""
Configuration for PostgreSQL Consumer
"""

import os
from typing import Dict, Any
from pydantic_settings import BaseSettings


class ConsumerConfig(BaseSettings):
    """Consumer configuration with environment variable support"""

    # Kafka Configuration
    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_group_id: str = "postgres-writer"
    kafka_topic: str = "crypto_prices"
    kafka_auto_offset_reset: str = "earliest"

    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5434
    postgres_database: str = "crypto_db"
    postgres_user: str = "crypto_user"
    # Never hardcode secrets; expect from environment/.env
    postgres_password: str = ""

    # Consumer Settings
    batch_size: int = 100
    commit_interval: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra fields from .env file
        case_sensitive = False

    def get_kafka_config(self) -> Dict[str, Any]:
        """Get Kafka consumer configuration"""
        return {
            "bootstrap.servers": self.kafka_bootstrap_servers,
            "group.id": self.kafka_group_id,
            "client.id": f"{self.kafka_group_id}-consumer",
            "isolation.level": "read_committed",
            "enable.auto.commit": False,
            "auto.offset.reset": self.kafka_auto_offset_reset,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 60000,
        }

    def get_postgres_dsn(self) -> str:
        """Get PostgreSQL connection string"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )


# Create global config instance
config = ConsumerConfig()
