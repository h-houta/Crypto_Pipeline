# Docker Full Image - Makefile
# Provides easy commands for building, running, and managing the full image

.PHONY: help build build-local run run-all stop clean logs status health test shell setup-infra remove-infra ps backup restore

# Default target
.DEFAULT_GOAL := help

help:
	@echo "🚀 Docker Full Image - Available Commands"
	@echo "=========================================="
	@echo ""
	@echo "📦 Build Commands:"
	@echo "  make build        - Build the full image from remote Git repository"
	@echo "  make build-local  - Build the full image from local source"
	@echo ""
	@echo "▶️  Run Commands:"
	@echo "  make run          - Run the full image with all services"
	@echo "  make run-all      - Run complete stack with infrastructure (docker-compose)"
	@echo "  make stop         - Stop all running containers"
	@echo ""
	@echo "🔧 Management Commands:"
	@echo "  make logs         - View logs from the full image container"
	@echo "  make status       - Check status of all services"
	@echo "  make health       - Run health check on the full image"
	@echo "  make shell        - Open shell in running container"
	@echo ""
	@echo "🏗️  Infrastructure Commands:"
	@echo "  make setup-infra  - Setup infrastructure (Redpanda + PostgreSQL)"
	@echo "  make remove-infra - Remove infrastructure containers and network"
	@echo ""
	@echo "🧪 Testing & Development:"
	@echo "  make test         - Test individual components"
	@echo "  make backup       - Backup current data and configuration"
	@echo "  make restore      - Restore from backup"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  make clean        - Clean up containers, images, and volumes"
	@echo "  make ps           - Show running services"
	@echo "  make logs-follow  - Follow logs in real-time"

# Build the full image from remote Git repository
build:
	@echo "📦 Building Docker Full Image from remote repository..."
	@if ! docker info >/dev/null 2>&1; then \
		echo "❌ Docker is not running. Please start Docker and try again."; \
		exit 1; \
	fi
	docker build -t crypto-full:latest \
		--build-arg GIT_REPO_URL="https://github.com/h-houta/Crypto_Pipeline.git" \
		--build-arg GIT_REF="main" \
		--build-arg APP_SRC="crypto-pipeline" \
		-f Dockerfile \
		.
	@echo "✅ Build completed successfully!"

# Build the full image from local source
build-local:
	@echo "📦 Building Docker Full Image from local source..."
	@if ! docker info >/dev/null 2>&1; then \
		echo "❌ Docker is not running. Please start Docker and try again."; \
		exit 1; \
	fi
	@if [ ! -d "../crypto-pipeline" ]; then \
		echo "❌ Local crypto-pipeline directory not found. Please ensure you're in the correct location."; \
		exit 1; \
	fi
	docker build -t crypto-full:latest \
		--build-arg GIT_REPO_URL="file://$(shell pwd)/../crypto-pipeline" \
		--build-arg GIT_REF="local" \
		--build-arg APP_SRC="." \
		-f Dockerfile \
		../crypto-pipeline
	@echo "✅ Local build completed successfully!"

# Run the full image with all services
run:
	@echo "▶️  Starting Docker Full Image..."
	@echo "⚠️  Prerequisites: Ensure crypto-network exists and Redpanda/Postgres are running"
	@echo ""
	@if ! docker network ls | grep -q crypto-network; then \
		echo "❌ crypto-network not found. Run 'make setup-infra' first."; \
		exit 1; \
	fi
	docker run --rm --name crypto-full \
		--network crypto-network \
		-e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
		-e POSTGRES_HOST=postgres \
		-e POSTGRES_PORT=5432 \
		-e POSTGRES_DB=crypto_db \
		-e POSTGRES_USER=crypto_user \
		-e POSTGRES_PASSWORD=cryptopass123 \
		-e ALERT_RECIPIENTS="test@example.com" \
		-v "$(shell pwd)/logs:/logs" \
		-p 8000:8000 -p 8001:8001 -p 9091:9091 \
		crypto-full:latest

# Run complete stack with infrastructure using docker-compose
run-all:
	@echo "🚀 Starting complete stack with docker-compose..."
	@if ! command -v docker-compose >/dev/null 2>&1; then \
		echo "❌ docker-compose not found. Please install docker-compose."; \
		exit 1; \
	fi
	@mkdir -p logs
	docker-compose up -d
	@echo "✅ Stack started! Access points:"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000 (admin/admin123)"
	@echo "  - Producer Metrics: http://localhost:8000/metrics"
	@echo "  - Consumer Metrics: http://localhost:8001/metrics"
	@echo "  - Monitor Metrics: http://localhost:9091/metrics"
	@echo "  - Node Exporter: http://localhost:9100/metrics"

# Stop all running containers
stop:
	@echo "⏹️  Stopping all containers..."
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose down; \
	else \
		echo "⚠️  docker-compose not found, stopping containers manually..."; \
		docker stop crypto-full redpanda postgres prometheus grafana node-exporter 2>/dev/null || true; \
		docker rm crypto-full redpanda postgres prometheus grafana node-exporter 2>/dev/null || true; \
	fi
	@echo "✅ All containers stopped!"

# View logs from the full image container
logs:
	@echo "📋 Viewing logs from crypto-full container..."
	@if docker ps | grep -q crypto-full; then \
		docker logs -f crypto-full; \
	else \
		echo "❌ crypto-full container is not running"; \
		exit 1; \
	fi

# Follow logs in real-time
logs-follow:
	@echo "📋 Following logs in real-time..."
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose logs -f; \
	else \
		echo "❌ docker-compose not found. Use 'make logs' instead."; \
		exit 1; \
	fi

# Check status of all services
status:
	@echo "📊 Checking service status..."
	@echo ""
	@echo "🐳 Container Status:"
	@docker ps --filter "name=crypto" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "📈 Supervisor Status (if running):"
	@if docker ps | grep -q crypto-full; then \
		docker exec crypto-full supervisorctl status 2>/dev/null || echo "⚠️  Supervisor not available"; \
	else \
		echo "❌ crypto-full container is not running"; \
	fi

# Run health check on the full image
health:
	@echo "🏥 Running health check..."
	@if docker network ls | grep -q crypto-network; then \
		docker run --rm --network crypto-network \
			-e MODE=health \
			crypto-full:latest; \
	else \
		echo "❌ crypto-network not found. Run 'make setup-infra' first."; \
		exit 1; \
	fi

# Clean up containers, images, and volumes
clean:
	@echo "🧹 Cleaning up Docker resources..."
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose down -v --remove-orphans; \
	else \
		echo "⚠️  docker-compose not found, cleaning manually..."; \
		docker stop crypto-full redpanda postgres prometheus grafana node-exporter 2>/dev/null || true; \
		docker rm crypto-full redpanda postgres prometheus grafana node-exporter 2>/dev/null || true; \
	fi
	@docker rmi crypto-full:latest 2>/dev/null || true
	@docker system prune -f
	@docker volume prune -f
	@echo "✅ Cleanup completed!"

# Test individual components
test:
	@echo "🧪 Testing individual components..."
	@echo ""
	@if ! docker network ls | grep -q crypto-network; then \
		echo "❌ crypto-network not found. Run 'make setup-infra' first."; \
		exit 1; \
	fi
	@echo "🔍 Testing Producer Mode:"
	@docker run --rm --network crypto-network \
		-e MODE=producer \
		-e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
		--name test-producer \
		crypto-full:latest &
	@sleep 10
	@docker stop test-producer 2>/dev/null || true
	@echo "✅ Producer test completed!"
	@echo ""
	@echo "🔍 Testing Health Check:"
	@docker run --rm --network crypto-network \
		-e MODE=health \
		--name test-health \
		crypto-full:latest
	@echo "✅ Health check test completed!"

# Open shell in running container
shell:
	@echo "🐚 Opening shell in crypto-full container..."
	@if docker ps | grep -q crypto-full; then \
		docker exec -it crypto-full /bin/bash; \
	else \
		echo "❌ crypto-full container is not running"; \
		exit 1; \
	fi

# Setup infrastructure (Redpanda + Postgres)
setup-infra:
	@echo "🏗️  Setting up infrastructure..."
	@echo "🔗 Creating crypto-network..."
	@docker network create crypto-network 2>/dev/null || echo "✅ Network already exists"
	@echo ""
	@echo "🔴 Starting Redpanda..."
	@if ! docker ps | grep -q redpanda; then \
		docker run -d --name redpanda --network crypto-network -p 9092:9092 \
			docker.redpanda.com/redpandadata/redpanda:latest \
			redpanda start --overprovisioned --smp 1 --memory 1G --reserve-memory 0M \
			--check=false --node-id 0 --kafka-addr "PLAINTEXT://0.0.0.0:9092" \
			--advertise-kafka-addr "PLAINTEXT://redpanda:9092"; \
		echo "✅ Redpanda started"; \
	else \
		echo "✅ Redpanda is already running"; \
	fi
	@echo ""
	@echo "🐘 Starting PostgreSQL with TimescaleDB..."
	@if ! docker ps | grep -q postgres; then \
		docker run -d --name postgres --network crypto-network \
			-e POSTGRES_DB=crypto_db \
			-e POSTGRES_USER=crypto_user \
			-e POSTGRES_PASSWORD=cryptopass123 \
			-p 5432:5432 \
			timescale/timescaledb:latest-pg15; \
		echo "✅ PostgreSQL started"; \
	else \
		echo "✅ PostgreSQL is already running"; \
	fi
	@echo ""
	@echo "⏳ Waiting for services to be ready..."
	@sleep 30
	@echo "✅ Infrastructure setup completed!"

# Remove infrastructure
remove-infra:
	@echo "🗑️  Removing infrastructure..."
	@docker stop redpanda postgres 2>/dev/null || true
	@docker rm redpanda postgres 2>/dev/null || true
	@docker network rm crypto-network 2>/dev/null || true
	@echo "✅ Infrastructure removed!"

# Show running services
ps:
	@echo "🐳 Running services:"
	@docker ps --filter "name=crypto" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Backup current data and configuration
backup:
	@echo "💾 Creating backup..."
	@mkdir -p backups
	@tar -czf "backups/crypto-pipeline-$(date +%Y%m%d-%H%M%S).tar.gz" \
		--exclude='backups' \
		--exclude='logs' \
		--exclude='*.log' \
		--exclude='.git' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		.
	@echo "✅ Backup created successfully!"

# Restore from backup
restore:
	@echo "📥 Restoring from backup..."
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "❌ Please specify BACKUP_FILE=filename.tar.gz"; \
		echo "   Example: make restore BACKUP_FILE=backups/crypto-pipeline-20241201-120000.tar.gz"; \
		exit 1; \
	fi
	@if [ ! -f "$(BACKUP_FILE)" ]; then \
		echo "❌ Backup file $(BACKUP_FILE) not found"; \
		exit 1; \
	fi
	@tar -xzf "$(BACKUP_FILE)"
	@echo "✅ Restore completed successfully!"
