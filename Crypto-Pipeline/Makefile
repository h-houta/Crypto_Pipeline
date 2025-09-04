###################################################################################################################################################################
#  Version History
###################################################################################################################################################################
#  	Version 	| Date        	         | 	    Author			|	Comments
#  	1.0      	| 16 AUG, 2025 	         | 	    HASSAN HOUTA	|	Initial.
###################################################################################################################################################################
# This file is to configure the Makefile for the project.
###################################################################################################################################################################

.PHONY: help setup start stop clean test monitor

help:
	@echo "Available commands:"
	@echo "  make setup    - Install dependencies and setup environment"
	@echo "  make start    - Start all services"
	@echo "  make stop     - Stop all services"
	@echo "  make clean    - Clean up containers and volumes"
	@echo "  make test     - Run tests"
	@echo "  make monitor  - Open monitoring dashboards"
	@echo "  make dbt-clean - Clean DBT environment and fix import conflicts"
	@echo "  make dbt-smart  - Run DBT with smart profile detection (e.g., make dbt-smart build --target prod)"


setup:
	@echo "Setting up environment..."
	@command -v poetry >/dev/null 2>&1 && poetry install -E dbt || pip3 install -r requirements.txt
	@echo "Pulling images..."
	@docker compose pull || true

start:
	@echo "Starting core services (Kafka, Postgres, Producer, Consumer)..."
	@docker network create crypto-network 2>/dev/null || true
	@docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@echo "Services started! Access points:"
	@echo "  - Redpanda Console: http://localhost:8080"
	@echo "  - PostgreSQL: localhost:5434"
	@echo "  - Kafka (external): localhost:19092"

producer-start:
	@echo "Starting producer..."
	@poetry run python producer/coinbase_producer.py
setup-timescaledb:
	@echo "Setting up TimescaleDB (install TimescaleDB extension)."
	@bash scripts/setup_timescaledb.sh

consumer-start:
	@echo "Starting consumer..."
	@poetry run python consumer/postgres_consumer.py

dbt-run:
	@echo "Running DBT models..."
	@cd dbt_crypto && poetry run dbt run

dbt-test:
	@echo "Testing DBT models..."
	@cd dbt_crypto && poetry run dbt test

dbt-clean:
	@echo "Cleaning DBT environment..."
	@bash scripts/clean_dbt.sh

dbt-smart:
	@echo "Running DBT with smart profile detection..."
	@bash scripts/run_dbt.sh $(filter-out $@,$(MAKECMDGOALS))

dbt-docs:
	@echo "Generating DBT documentation..."
	@cd dbt_crypto && poetry run dbt docs generate
	@cd dbt_crypto && poetry run dbt docs serve

check-prices:
	@echo "Checking latest prices in database..."
	@docker compose exec postgres psql -U crypto_user -d crypto_db -c \
		"SELECT symbol, MAX(time) as latest, COUNT(*) as total, \
		 ROUND(AVG(price)::numeric, 2) as avg_price \
		 FROM raw_crypto_prices_log \
		 GROUP BY symbol ORDER BY symbol;"

check-ohlcv:
	@echo "Checking OHLCV aggregates..."
	@docker compose exec postgres psql -U crypto_user -d crypto_db -c \
		"SELECT * FROM crypto_ohlcv_15min \
		 ORDER BY bucket DESC LIMIT 10;"

tail-all:
	@echo "Tailing all service logs..."
	@docker compose logs -f --tail=50

stop:
	@echo "Stopping services..."
	@docker compose down

clean:
	@echo "Cleaning up..."
	@rm -rf target/ dbt_packages/ logs/

test:
	@echo "Running tests..."
	pytest tests/ -v

restart: stop start

status:
	@echo "Checking service status..."
	@docker compose ps



# Airflow commands
airflow-init:
	@echo "Initializing Airflow..."
	@docker network create crypto-network 2>/dev/null || true
	@cd airflow && docker compose -f docker-compose-airflow.yml run --rm airflow-init
	@echo "Airflow initialized!"

airflow-start:
	@echo "Starting Airflow..."
	@cd airflow && docker compose -f docker-compose-airflow.yml up -d
	@echo "Waiting for Airflow to be ready..."
	@sleep 20
	@echo "Airflow started!"
	@echo "  - Airflow UI: http://localhost:8081"
	@echo "  - Username: admin"
	@echo "  - Password: admin123"

airflow-stop:
	@echo "Stopping Airflow..."
	@cd airflow && docker compose -f docker-compose-airflow.yml down

w:
	@cd airflow && docker compose -f docker-compose-airflow.yml logs -f --tail=50

airflow-clean:
	@echo "Cleaning Airflow..."
	@cd airflow && docker compose -f docker-compose-airflow.yml down -v
	@rm -rf airflow/logs/* airflow/plugins/*

# Full stack commands
stack-start: start airflow-start
	@echo "Full stack started!"
	@echo "Services:"
	@echo "  - Redpanda Console: http://localhost:8080"
	@echo "  - Airflow UI: http://localhost:8081"
	@echo "  - PostgreSQL: localhost:5434"

stack-stop: airflow-stop stop
	@echo "Full stack stopped!"

stack-status:
	@echo "=== Docker Services ==="
	@docker compose ps
	@echo ""
	@echo "=== Airflow Services ==="
	@cd airflow && docker compose -f docker-compose-airflow.yml ps

monitor:
	@echo "Opening monitoring dashboards..."
	@open http://localhost:8080  # Redpanda Console
	@open http://localhost:3000  # Grafana (if configured)

logs-producer:
	docker logs -f crypto-producer --tail 100

logs-consumer:
	docker logs -f crypto-consumer --tail 100

psql:
	@docker compose exec postgres psql -U crypto_user -d crypto_db

psql-host:
	@psql -h localhost -p 5434 -U crypto_user -d crypto_db
