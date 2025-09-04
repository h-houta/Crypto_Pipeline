"""
Test script to verify producer functionality
"""

import asyncio
import httpx


async def test_coinbase_api():
    """Test that we can fetch from Coinbase API"""
    print("Testing Coinbase API connectivity...")

    symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]

    async with httpx.AsyncClient() as client:
        for symbol in symbols:
            try:
                url = f"https://api.coinbase.com/v2/prices/{symbol}/spot"
                response = await client.get(url, timeout=5.0)

                if response.status_code == 200:
                    data = response.json()
                    price = float(data["data"]["amount"])
                    print(f"✅ {symbol}: ${price:,.2f}")
                else:
                    print(f"❌ {symbol}: HTTP {response.status_code}")

            except httpx.TimeoutException as e:
                print(f"❌ {symbol}: request timed out: {e}")
            except httpx.RequestError as e:
                print(f"❌ {symbol}: request error: {e}")
            except (KeyError, TypeError, ValueError) as e:
                print(f"❌ {symbol}: parse error: {e}")

    print("\nAPI test complete!")


def test_kafka_connection():
    """Test Kafka connectivity"""
    print("\nTesting Kafka connectivity...")

    try:
        from confluent_kafka import (  # pylint: disable=import-outside-toplevel
            Producer,
            KafkaException,
        )
    except ModuleNotFoundError as e:
        print(f"❌ Kafka client not installed: {e}")
        return

    config = {"bootstrap.servers": "localhost:19092", "client.id": "test-producer"}

    try:
        producer = Producer(config)

        # Try to get metadata
        metadata = producer.list_topics(timeout=5)

        print("✅ Connected to Kafka")
        print(f"   Brokers: {len(metadata.brokers)}")
        print(f"   Topics: {len(metadata.topics)}")

        for topic in metadata.topics:
            print(f"   - {topic}")

    except KafkaException as e:
        print(f"❌ Kafka connection failed: {e}")
    except OSError as e:
        print(f"❌ Kafka OS/network error: {e}")


async def main():
    """Run all tests"""
    print("=" * 50)
    print("Producer Test Suite")
    print("=" * 50)

    # Test Coinbase API
    await test_coinbase_api()

    # Test Kafka
    test_kafka_connection()

    print("\n" + "=" * 50)
    print("Tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
