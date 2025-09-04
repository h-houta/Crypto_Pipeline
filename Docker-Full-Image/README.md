# Docker Full Image - Crypto Pipeline

Build a single image that can run the producer, consumer, alerting, and throughput monitor together (or individually). This image still relies on external Redpanda and PostgreSQL.

## Features

- **Producer**: Fetches real-time cryptocurrency prices from Coinbase
- **Consumer**: Processes Kafka messages and stores data in PostgreSQL
- **Alert Consumer**: Monitors price movements and sends alerts
- **Throughput Monitor**: Tracks pipeline performance metrics
- **Supervisor**: Manages all services with automatic restart and monitoring

## Build

```bash
docker build -t crypto-full:latest \
 --build-arg GIT_REPO_URL="https://github.com/h-houta/Crypto_Pipeline.git" \
 --build-arg GIT_REF="main" \
 --build-arg APP_SRC="crypto-pipeline" \
 -f Dockerfile \
 .
```

## Prerequisites

1. **Docker Network**: Ensure `crypto-network` exists
2. **Redpanda**: Kafka-compatible message broker
3. **PostgreSQL**: Database for storing crypto data

### Setup Infrastructure

```bash
# Create network if missing
docker network create crypto-network || true

# Run Redpanda (single node)
docker run -d --name redpanda --network crypto-network -p 9092:9092 \
  docker.redpanda.com/redpandadata/redpanda:latest \
  redpanda start --overprovisioned --smp 1 --memory 1G --reserve-memory 0M \
  --check=false --node-id 0 --kafka-addr "PLAINTEXT://0.0.0.0:9092" \
  --advertise-kafka-addr "PLAINTEXT://redpanda:9092"

# Run PostgreSQL with TimescaleDB
docker run -d --name postgres --network crypto-network \
  -e POSTGRES_DB=crypto_db \
  -e POSTGRES_USER=crypto_user \
  -e POSTGRES_PASSWORD=cryptopass123 \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg15
```

## Run

### All Services (via Supervisor)

```bash
docker run --rm --name crypto-full \
 --network crypto-network \
 -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
 -e POSTGRES_HOST=postgres \
 -e POSTGRES_PORT=5432 \
 -e POSTGRES_DB=crypto_db \
 -e POSTGRES_USER=crypto_user \
 -e POSTGRES_PASSWORD=cryptopass123 \
 -e ALERT_RECIPIENTS="you@example.com" \
 -v "$(pwd)/logs:/logs" \
 crypto-full:latest
```

### Individual Services

#### Producer Only

```bash
docker run --rm --network crypto-network \
  -e MODE=producer \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  crypto-full:latest
```

#### Consumer Only

```bash
docker run --rm --network crypto-network \
  -e MODE=consumer \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=crypto_db \
  -e POSTGRES_USER=crypto_user \
  -e POSTGRES_PASSWORD=cryptopass123 \
  crypto-full:latest
```

#### Alert Consumer Only

```bash
docker run --rm --network crypto-network \
  -e MODE=alert \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  -e ALERT_RECIPIENTS="you@example.com" \
  -v "$(pwd)/logs:/logs" \
  crypto-full:latest
```

#### Throughput Monitor Only

```bash
docker run --rm --network crypto-network \
  -e MODE=monitor \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  crypto-full:latest
```

### Health Check

```bash
docker run --rm --network crypto-network \
  -e MODE=health \
  crypto-full:latest
```

## Environment Variables

| Variable                  | Required | Default | Description                                                               |
| ------------------------- | -------- | ------- | ------------------------------------------------------------------------- |
| `MODE`                    | No       | `all`   | Service mode: `all`, `producer`, `consumer`, `alert`, `monitor`, `health` |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes      | -       | Kafka bootstrap servers (e.g., `redpanda:9092`)                           |
| `POSTGRES_HOST`           | Yes\*    | -       | PostgreSQL host (required for consumer/monitor)                           |
| `POSTGRES_PORT`           | Yes\*    | `5432`  | PostgreSQL port                                                           |
| `POSTGRES_DB`             | Yes\*    | -       | PostgreSQL database name                                                  |
| `POSTGRES_USER`           | Yes\*    | -       | PostgreSQL username                                                       |
| `POSTGRES_PASSWORD`       | Yes\*    | -       | PostgreSQL password                                                       |
| `ALERT_RECIPIENTS`        | No       | -       | Email recipients for price alerts                                         |

\*Required for consumer and monitor modes

## Service Management

### Supervisor Commands

When running in `all` mode, you can manage services using supervisor:

```bash
# Check service status
docker exec crypto-full supervisorctl status

# Restart a service
docker exec crypto-full supervisorctl restart producer

# Stop a service
docker exec crypto-full supervisorctl stop consumer

# Start a service
docker exec crypto-full supervisorctl start alert_consumer

# View logs
docker exec crypto-full supervisorctl tail -f producer
```

### Service Groups

- **crypto_pipeline**: All services grouped together
- **producer**: Coinbase price producer
- **consumer**: PostgreSQL consumer
- **alert_consumer**: Price alert consumer
- **throughput_monitor**: Performance monitoring

## Monitoring

The image includes built-in monitoring capabilities:

- **Prometheus Metrics**: Available on port 9091
- **Supervisor Status**: Process management and health checks
- **Structured Logging**: JSON-formatted logs for better parsing
- **Health Endpoints**: Service health status endpoints

## Troubleshooting

### Common Issues

1. **Kafka Connection Failed**: Ensure Redpanda is running and accessible
2. **PostgreSQL Connection Failed**: Check database credentials and network
3. **Service Won't Start**: Check environment variables and dependencies
4. **High Memory Usage**: Monitor resource usage with `docker stats`

### Debug Mode

```bash
# Run with debug logging
docker run --rm --network crypto-network \
  -e MODE=all \
  -e LOG_LEVEL=DEBUG \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  crypto-full:latest
```

### Logs

```bash
# View all logs
docker logs crypto-full

# Follow logs
docker logs -f crypto-full

# View specific service logs
docker exec crypto-full supervisorctl tail -f producer
```

## Development

### Building Locally

```bash
# Clone the repository
git clone https://github.com/h-houta/Crypto_Pipeline.git
cd Crypto_Pipeline

# Build the full image
docker build -f ../Docker-Full-Image/Dockerfile -t crypto-full:latest .
```

### Testing

```bash
# Test individual components
docker run --rm --network crypto-network \
  -e MODE=producer \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  crypto-full:latest

# Test health check
docker run --rm --network crypto-network \
  -e MODE=health \
  crypto-full:latest
```

## Architecture

The full image uses:

- **Python 3.11**: Base runtime
- **Poetry**: Dependency management
- **Supervisor**: Process management
- **Confluent Kafka**: Python client
- **Psycopg2**: PostgreSQL adapter
- **Prometheus Client**: Metrics collection

## Security Notes

- Run with minimal required permissions
- Use Docker secrets for sensitive data in production
- Network isolation via Docker networks
- No root user escalation in the container
