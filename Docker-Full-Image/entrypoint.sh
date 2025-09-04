#!/bin/sh
set -e

# Default mode
MODE="${MODE:-all}"

# Function to print colored output
print_status() {
    local level=$1
    local message=$2
    case $level in
        "INFO")
            echo "ℹ️  $message"
            ;;
        "SUCCESS")
            echo "✅ $message"
            ;;
        "WARNING")
            echo "⚠️  $message"
            ;;
        "ERROR")
            echo "❌ $message"
            ;;
        *)
            echo "$message"
            ;;
    esac
}

# Function to check if required environment variables are set
check_env() {
    local required_vars=("$@")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "$(eval echo \$$var)" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_status "ERROR" "Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi

    return 0
}

# Function to wait for dependencies with timeout
wait_for_deps() {
    local timeout=${DEPENDENCY_TIMEOUT:-60}
    local start_time=$(date +%s)

    print_status "INFO" "Waiting for dependencies to be ready (timeout: ${timeout}s)..."

    # Wait for Kafka
    if [ -n "$KAFKA_BOOTSTRAP_SERVERS" ]; then
        print_status "INFO" "Checking Kafka availability at $KAFKA_BOOTSTRAP_SERVERS..."

        local kafka_ready=false
        while [ "$kafka_ready" = false ] && [ $(($(date +%s) - start_time)) -lt $timeout ]; do
            if nc -z $(echo $KAFKA_BOOTSTRAP_SERVERS | cut -d: -f1) $(echo $KAFKA_BOOTSTRAP_SERVERS | cut -d: -f2) 2>/dev/null; then
                kafka_ready=true
                print_status "SUCCESS" "Kafka is ready"
            else
                print_status "WARNING" "Waiting for Kafka... ($(($(date +%s) - start_time))s elapsed"
                sleep 5
            fi
        done

        if [ "$kafka_ready" = false ]; then
            print_status "ERROR" "Kafka not ready after ${timeout}s timeout"
            return 1
        fi
    fi

    # Wait for PostgreSQL
    if [ -n "$POSTGRES_HOST" ]; then
        print_status "INFO" "Checking PostgreSQL availability at $POSTGRES_HOST:$POSTGRES_PORT..."

        local postgres_ready=false
        while [ "$postgres_ready" = false ] && [ $(($(date +%s) - start_time)) -lt $timeout ]; do
            if nc -z $POSTGRES_HOST $POSTGRES_PORT 2>/dev/null; then
                postgres_ready=true
                print_status "SUCCESS" "PostgreSQL is ready"
            else
                print_status "WARNING" "Waiting for PostgreSQL... ($(($(date +%s) - start_time))s elapsed"
                sleep 5
            fi
        done

        if [ "$postgres_ready" = false ]; then
            print_status "ERROR" "PostgreSQL not ready after ${timeout}s timeout"
            return 1
        fi
    fi

    print_status "SUCCESS" "All dependencies are ready"
    return 0
}

# Function to validate configuration
validate_config() {
    print_status "INFO" "Validating configuration..."

    # Check Python environment
    if ! command -v python >/dev/null 2>&1; then
        print_status "ERROR" "Python not found in PATH"
        return 1
    fi

    # Check required files
    if [ ! -f "/app/supervisord.conf" ]; then
        print_status "ERROR" "supervisord.conf not found"
        return 1
    fi

    if [ ! -f "/app/entrypoint.sh" ]; then
        print_status "ERROR" "entrypoint.sh not found"
        return 1
    fi

    print_status "SUCCESS" "Configuration validation passed"
    return 0
}

# Main execution logic
main() {
    print_status "INFO" "Starting Crypto Pipeline (Mode: $MODE)"

    # Validate configuration
    if ! validate_config; then
        exit 1
    fi

    case "$MODE" in
        producer)
            if ! check_env "KAFKA_BOOTSTRAP_SERVERS"; then
                exit 1
            fi
            if ! wait_for_deps; then
                exit 1
            fi
            print_status "INFO" "Starting producer service..."
            exec python /app/producer/coinbase_producer.py
            ;;

        consumer)
            if ! check_env "KAFKA_BOOTSTRAP_SERVERS" "POSTGRES_HOST" "POSTGRES_PORT" "POSTGRES_DB" "POSTGRES_USER" "POSTGRES_PASSWORD"; then
                exit 1
            fi
            if ! wait_for_deps; then
                exit 1
            fi
            print_status "INFO" "Starting consumer service..."
            exec python /app/consumer/postgres_consumer.py
            ;;

        alert|alert-consumer)
            if ! check_env "KAFKA_BOOTSTRAP_SERVERS"; then
                exit 1
            fi
            if ! wait_for_deps; then
                exit 1
            fi
            print_status "INFO" "Starting alert consumer service..."
            exec python /app/alerting/price_alert_consumer.py
            ;;

        monitor|throughput-monitor)
            if ! check_env "KAFKA_BOOTSTRAP_SERVERS" "POSTGRES_HOST" "POSTGRES_PORT"; then
                exit 1
            fi
            if ! wait_for_deps; then
                exit 1
            fi
            print_status "INFO" "Starting throughput monitor service..."
            exec python /app/monitoring/throughput_monitor.py
            ;;

        all)
            print_status "INFO" "Starting all services via supervisor..."
            if ! wait_for_deps; then
                exit 1
            fi
            exec /usr/bin/supervisord -c /app/supervisord.conf
            ;;

        health)
            print_status "INFO" "Running health check..."
            if command -v supervisorctl >/dev/null 2>&1; then
                supervisorctl status
            else
                print_status "WARNING" "Supervisor not running - checking basic health"
                if [ -f "/app/supervisord.conf" ] && [ -f "/app/entrypoint.sh" ]; then
                    print_status "SUCCESS" "Basic health check passed"
                    exit 0
                else
                    print_status "ERROR" "Basic health check failed"
                    exit 1
                fi
            fi
            ;;

        *)
            print_status "ERROR" "Unknown MODE: $MODE"
            echo ""
            echo "Valid modes: all | producer | consumer | alert | monitor | health"
            echo ""
            echo "Environment variables:"
            echo "  MODE                           - Service mode (default: all)"
            echo "  KAFKA_BOOTSTRAP_SERVERS       - Kafka bootstrap servers (required)"
            echo "  POSTGRES_HOST                 - PostgreSQL host (required for consumer/monitor)"
            echo "  POSTGRES_PORT                 - PostgreSQL port (default: 5432)"
            echo "  POSTGRES_DB                   - PostgreSQL database name (required for consumer)"
            echo "  POSTGRES_USER                 - PostgreSQL username (required for consumer)"
            echo "  POSTGRES_PASSWORD             - PostgreSQL password (required for consumer)"
            echo "  ALERT_RECIPIENTS             - Email recipients for alerts (optional)"
            echo "  DEPENDENCY_TIMEOUT            - Dependency wait timeout in seconds (default: 60)"
            echo ""
            echo "Examples:"
            echo "  docker run -e MODE=producer -e KAFKA_BOOTSTRAP_SERVERS=localhost:9092 crypto-full:latest"
            echo "  docker run -e MODE=all -e KAFKA_BOOTSTRAP_SERVERS=localhost:9092 crypto-full:latest"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"


