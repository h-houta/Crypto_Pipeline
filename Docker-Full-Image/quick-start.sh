#!/bin/bash

# Docker Full Image - Quick Start Script
# This script helps you get up and running quickly with the crypto pipeline

set -e

# Script version
SCRIPT_VERSION="2.0.0"

echo "🚀 Crypto Pipeline - Docker Full Image Quick Start v${SCRIPT_VERSION}"
echo "================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "info")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
        "success")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "warning")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "error")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "step")
            echo -e "${PURPLE}🔧 $message${NC}"
            ;;
        "check")
            echo -e "${CYAN}🔍 $message${NC}"
            ;;
    esac
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if Docker is running
check_docker() {
    print_status "check" "Checking Docker status..."
    if ! docker info >/dev/null 2>&1; then
        print_status "error" "Docker is not running. Please start Docker and try again."
        echo ""
        echo "💡 To start Docker:"
        echo "   - macOS: Open Docker Desktop application"
        echo "   - Linux: sudo systemctl start docker"
        echo "   - Windows: Open Docker Desktop application"
        exit 1
    fi
    print_status "success" "Docker is running"
}

# Function to check Docker version
check_docker_version() {
    print_status "check" "Checking Docker version..."
    local docker_version=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    local major_version=$(echo $docker_version | cut -d'.' -f1)
    local minor_version=$(echo $docker_version | cut -d'.' -f2)

    if [ "$major_version" -lt 20 ] || ([ "$major_version" -eq 20 ] && [ "$minor_version" -lt 10 ]); then
        print_status "warning" "Docker version $docker_version detected. Version 20.10+ is recommended."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_status "success" "Docker version $docker_version is compatible"
    fi
}

# Function to check if required ports are available
check_ports() {
    print_status "check" "Checking port availability..."
    local ports=("9092" "5432" "8000" "8001" "9091" "9090" "3000" "9100")
    local available=true
    local conflicting_services=()

    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            local service=$(lsof -Pi :$port -sTCP:LISTEN | head -1 | awk '{print $1}')
            print_status "warning" "Port $port is already in use by $service"
            available=false
            conflicting_services+=("$port:$service")
        fi
    done

    if [ "$available" = false ]; then
        print_status "warning" "Some ports are already in use. You may need to stop conflicting services."
        echo ""
        echo "🔍 Conflicting services:"
        for service in "${conflicting_services[@]}"; do
            echo "   - Port $service"
        done
        echo ""
        echo "💡 To resolve conflicts:"
        echo "   - Stop the conflicting service"
        echo "   - Use different ports via environment variables"
        echo "   - Run this script with --force to continue anyway"
        echo ""

        if [[ "$*" == *"--force"* ]]; then
            print_status "info" "Continuing with --force flag..."
        else
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        print_status "success" "All required ports are available"
    fi
}

# Function to check system resources
check_resources() {
    print_status "check" "Checking system resources..."

    # Check available memory
    local total_mem=$(sysctl -n hw.memsize 2>/dev/null || grep MemTotal /proc/meminfo | awk '{print $2}')
    local total_mem_gb=$((total_mem / 1024 / 1024 / 1024))

    if [ "$total_mem_gb" -lt 4 ]; then
        print_status "warning" "System has ${total_mem_gb}GB RAM. 4GB+ is recommended for optimal performance."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_status "success" "System has ${total_mem_gb}GB RAM"
    fi

    # Check available disk space
    local available_space=$(df . | tail -1 | awk '{print $4}')
    local available_space_gb=$((available_space / 1024 / 1024))

    if [ "$available_space_gb" -lt 5 ]; then
        print_status "warning" "Available disk space: ${available_space_gb}GB. 5GB+ is recommended."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_status "success" "Available disk space: ${available_space_gb}GB"
    fi
}

# Function to setup infrastructure
setup_infrastructure() {
    print_status "step" "Setting up infrastructure..."

    # Create network
    if ! docker network ls | grep -q crypto-network; then
        print_status "info" "Creating crypto-network..."
        docker network create crypto-network
        print_status "success" "Network created"
    else
        print_status "info" "Network crypto-network already exists"
    fi

    # Start Redpanda
    if ! docker ps | grep -q redpanda; then
        print_status "info" "Starting Redpanda..."
        docker run -d --name redpanda --network crypto-network -p 9092:9092 \
            docker.redpanda.com/redpandadata/redpanda:latest \
            redpanda start --overprovisioned --smp 1 --memory 1G --reserve-memory 0M \
            --check=false --node-id 0 --kafka-addr "PLAINTEXT://0.0.0.0:9092" \
            --advertise-kafka-addr "PLAINTEXT://redpanda:9092"
        print_status "success" "Redpanda started"
    else
        print_status "info" "Redpanda is already running"
    fi

    # Start PostgreSQL
    if ! docker ps | grep -q postgres; then
        print_status "info" "Starting PostgreSQL with TimescaleDB..."
        docker run -d --name postgres --network crypto-network \
            -e POSTGRES_DB=crypto_db \
            -e POSTGRES_USER=crypto_user \
            -e POSTGRES_PASSWORD=cryptopass123 \
            -p 5432:5432 \
            timescale/timescaledb:latest-pg15
        print_status "success" "PostgreSQL started"
    else
        print_status "info" "PostgreSQL is already running"
    fi

    # Wait for services to be ready
    print_status "info" "Waiting for services to be ready..."
    local timeout=60
    local start_time=$(date +%s)

    # Wait for Redpanda
    while ! nc -z localhost 9092 2>/dev/null && [ $(($(date +%s) - start_time)) -lt $timeout ]; do
        echo -n "."
        sleep 2
    done
    echo ""

    if nc -z localhost 9092 2>/dev/null; then
        print_status "success" "Redpanda is ready"
    else
        print_status "error" "Redpanda failed to start within ${timeout}s"
        exit 1
    fi

    # Wait for PostgreSQL
    start_time=$(date +%s)
    while ! nc -z localhost 5432 2>/dev/null && [ $(($(date +%s) - start_time)) -lt $timeout ]; do
        echo -n "."
        sleep 2
    done
    echo ""

    if nc -z localhost 5432 2>/dev/null; then
        print_status "success" "PostgreSQL is ready"
    else
        print_status "error" "PostgreSQL failed to start within ${timeout}s"
        exit 1
    fi

    print_status "success" "Infrastructure setup completed"
}

# Function to build the image
build_image() {
    print_status "step" "Building Docker Full Image..."

    if [ "$1" = "local" ]; then
        print_status "info" "Building from local source..."
        if [ ! -d "../crypto-pipeline" ]; then
            print_status "error" "Local crypto-pipeline directory not found"
            echo "💡 Make sure you're running this script from the Docker-Full-Image directory"
            exit 1
        fi
        docker build -t crypto-full:latest \
            --build-arg GIT_REPO_URL="file://$(pwd)/../crypto-pipeline" \
            --build-arg GIT_REF="local" \
            --build-arg APP_SRC="." \
            -f Dockerfile \
            ../crypto-pipeline
    else
        print_status "info" "Building from remote repository..."
        docker build -t crypto-full:latest \
            --build-arg GIT_REPO_URL="https://github.com/h-houta/Crypto_Pipeline.git" \
            --build-arg GIT_REF="main" \
            --build-arg APP_SRC="crypto-pipeline" \
            -f Dockerfile \
            .
    fi

    print_status "success" "Image built successfully"
}

# Function to run the full stack
run_stack() {
    print_status "step" "Starting complete stack..."

    # Create necessary directories
    mkdir -p logs backups

    # Check if docker-compose is available
    if ! command_exists docker-compose; then
        print_status "warning" "docker-compose not found, using docker compose (newer syntax)..."
        if ! command_exists docker; then
            print_status "error" "Docker not found"
            exit 1
        fi

        # Try to use docker compose
        if docker compose version >/dev/null 2>&1; then
            print_status "info" "Using 'docker compose' (newer syntax)"
            docker compose up -d
        else
            print_status "error" "Neither docker-compose nor docker compose found"
            echo "💡 Install docker-compose: pip install docker-compose"
            exit 1
        fi
    else
        print_status "info" "Using docker-compose"
        docker-compose up -d
    fi

    print_status "success" "Stack started successfully!"
    echo ""
    echo "🌐 Access Points:"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin123)"
    echo "  - Producer Metrics: http://localhost:8000/metrics"
    echo "  - Consumer Metrics: http://localhost:8001/metrics"
    echo "  - Monitor Metrics: http://localhost:9091/metrics"
    echo "  - Node Exporter: http://localhost:9100/metrics"
    echo ""
    echo "📊 Monitor the stack:"
    echo "  - View logs: make logs"
    echo "  - Check status: make status"
    echo "  - Stop stack: make stop"
    echo ""
    echo "🔧 Management commands:"
    echo "  - make logs-follow  # Follow logs in real-time"
    echo "  - make shell        # Open shell in container"
    echo "  - make health       # Run health checks"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  -h, --help         Show this help message"
    echo "  -v, --version      Show script version"
    echo "  -l, --local        Build from local source instead of remote repository"
    echo "  -i, --infra        Only setup infrastructure (Redpanda + PostgreSQL)"
    echo "  -b, --build        Only build the Docker image"
    echo "  -r, --run          Only run the stack (assumes infrastructure is ready)"
    echo "  -f, --full         Full setup: infrastructure + build + run (default)"
    echo "  --force            Force continue even with port conflicts"
    echo "  --skip-checks      Skip system resource and port availability checks"
    echo ""
    echo "Examples:"
    echo "  $0                    # Full setup"
    echo "  $0 --local           # Full setup with local build"
    echo "  $0 --infra           # Setup infrastructure only"
    echo "  $0 --build           # Build image only"
    echo "  $0 --run             # Run stack only"
    echo "  $0 --force           # Force continue with conflicts"
    echo ""
    echo "Environment Variables:"
    echo "  DEPENDENCY_TIMEOUT   Dependency wait timeout in seconds (default: 60)"
    echo "  BUILD_TIMEOUT        Build timeout in seconds (default: 1800)"
}

# Function to show version
show_version() {
    echo "Crypto Pipeline Quick Start Script v${SCRIPT_VERSION}"
    echo "Copyright (c) 2024 Crypto Pipeline Project"
}

# Main script logic
main() {
    local build_local=false
    local setup_infra_only=false
    local build_only=false
    local run_only=false
    local full_setup=true
    local force_mode=false
    local skip_checks=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -v|--version)
                show_version
                exit 0
                ;;
            -l|--local)
                build_local=true
                shift
                ;;
            -i|--infra)
                setup_infra_only=true
                full_setup=false
                shift
                ;;
            -b|--build)
                build_only=true
                full_setup=false
                shift
                ;;
            -r|--run)
                run_only=true
                full_setup=false
                shift
                ;;
            --force)
                force_mode=true
                shift
                ;;
            --skip-checks)
                skip_checks=true
                shift
                ;;
            *)
                print_status "error" "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Show welcome message
    echo "🎯 Mode: $([ "$setup_infra_only" = true ] && echo "Infrastructure Only" || [ "$build_only" = true ] && echo "Build Only" || [ "$run_only" = true ] && echo "Run Only" || echo "Full Setup")"
    echo "🔧 Local Build: $([ "$build_local" = true ] && echo "Yes" || echo "No")"
    echo "⚡ Force Mode: $([ "$force_mode" = true ] && echo "Yes" || echo "No")"
    echo "🔍 Skip Checks: $([ "$skip_checks" = true ] && echo "Yes" || echo "No")"
    echo ""

    # Check prerequisites
    if [ "$skip_checks" = false ]; then
        check_docker
        check_docker_version
        check_ports $([ "$force_mode" = true ] && echo "--force")
        check_resources
    else
        print_status "warning" "Skipping system checks (--skip-checks)"
    fi

    # Execute based on options
    if [ "$setup_infra_only" = true ]; then
        setup_infrastructure
    elif [ "$build_only" = true ]; then
        build_image $([ "$build_local" = true ] && echo "local")
    elif [ "$run_only" = true ]; then
        run_stack
    elif [ "$full_setup" = true ]; then
        setup_infrastructure
        build_image $([ "$build_local" = true ] && echo "local")
        run_stack
    fi

    echo ""
    print_status "success" "Setup completed successfully!"
    echo ""
    echo "🎉 Your crypto pipeline is now running!"
    echo ""
    echo "📚 Next steps:"
    echo "  1. Open Grafana at http://localhost:3000"
    echo "  2. Add Prometheus as a data source (http://prometheus:9090)"
    echo "  3. Import dashboards for monitoring"
    echo "  4. Check logs with: make logs"
    echo "  5. Stop everything with: make stop"
    echo ""
    echo "🔧 Useful commands:"
    echo "  - make status       # Check service status"
    echo "  - make health       # Run health checks"
    echo "  - make backup       # Create backup"
    echo "  - make clean        # Clean up resources"
    echo ""
    echo "📖 Documentation: README.md"
    echo "🐛 Issues: Check the logs or run 'make health'"
}

# Run main function with all arguments
main "$@"
