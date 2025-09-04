#!/bin/bash

# Airflow Deployment Script
# Allows switching between secure HTTPS and development HTTP setups

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  secure     Deploy Airflow with HTTPS and security features"
    echo "  dev        Deploy Airflow with HTTP (development only)"
    echo "  stop       Stop all Airflow services"
    echo "  restart    Restart Airflow services"
    echo "  logs       Show logs for all services"
    echo "  status     Show status of all services"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 secure    # Deploy with HTTPS (recommended for production)"
    echo "  $0 dev       # Deploy with HTTP (development only)"
    echo "  $0 stop      # Stop all services"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi

    # Check if docker-compose is available
    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "docker-compose is not installed. Please install it and try again."
        exit 1
    fi

    # Check if crypto-network exists
    if ! docker network ls | grep -q crypto-network; then
        print_warning "crypto-network not found. Creating it..."
        docker network create crypto-network
    fi

    print_success "Prerequisites check passed!"
}

# Function to deploy secure setup
deploy_secure() {
    print_status "Deploying Airflow with HTTPS and security features..."

    # Check if SSL certificates exist
    if [[ ! -f "nginx/ssl/airflow.crt" ]] || [[ ! -f "nginx/ssl/airflow.key" ]]; then
        print_warning "SSL certificates not found. Generating them..."
        ./generate_certs.sh
        cp certs/airflow.crt nginx/ssl/
        cp certs/airflow.key nginx/ssl/
    fi

    # Stop existing services
    docker-compose -f docker-compose-airflow.yml down 2>/dev/null || true

    # Start secure services
    docker-compose -f docker-compose-secure.yml up -d

    print_success "Secure Airflow deployment started!"
    echo ""
    echo "🔐 Access Airflow at: https://localhost"
    echo "⚠️  Accept the self-signed certificate warning in your browser"
    echo "👤 Username: admin"
    echo "🔑 Password: admin123"
    echo ""
    echo "📊 Monitor services: $0 status"
    echo "📝 View logs: $0 logs"
}

# Function to deploy development setup
deploy_dev() {
    print_status "Deploying Airflow with HTTP (development only)..."

    # Stop secure services
    docker-compose -f docker-compose-secure.yml down 2>/dev/null || true

    # Start development services
    docker-compose -f docker-compose-airflow.yml up -d

    print_success "Development Airflow deployment started!"
    echo ""
    echo "🌐 Access Airflow at: http://localhost:8081"
    echo "👤 Username: admin"
    echo "🔑 Password: admin123"
    echo ""
    echo "⚠️  WARNING: This setup uses HTTP and is NOT secure for production!"
    echo "📊 Monitor services: $0 status"
    echo "📝 View logs: $0 logs"
}

# Function to stop services
stop_services() {
    print_status "Stopping all Airflow services..."

    docker-compose -f docker-compose-airflow.yml down 2>/dev/null || true
    docker-compose -f docker-compose-secure.yml down 2>/dev/null || true

    print_success "All services stopped!"
}

# Function to restart services
restart_services() {
    print_status "Restarting Airflow services..."

    # Determine which compose file is currently running
    if docker-compose -f docker-compose-secure.yml ps | grep -q "Up"; then
        print_status "Restarting secure services..."
        docker-compose -f docker-compose-secure.yml restart
        print_success "Secure services restarted!"
    elif docker-compose -f docker-compose-airflow.yml ps | grep -q "Up"; then
        print_status "Restarting development services..."
        docker-compose -f docker-compose-airflow.yml restart
        print_success "Development services restarted!"
    else
        print_warning "No running services found. Use '$0 secure' or '$0 dev' to start services."
    fi
}

# Function to show logs
show_logs() {
    print_status "Showing logs for all services..."

    # Determine which compose file is currently running
    if docker-compose -f docker-compose-secure.yml ps | grep -q "Up"; then
        docker-compose -f docker-compose-secure.yml logs -f
    elif docker-compose -f docker-compose-airflow.yml ps | grep -q "Up"; then
        docker-compose -f docker-compose-airflow.yml logs -f
    else
        print_warning "No running services found. Use '$0 secure' or '$0 dev' to start services."
    fi
}

# Function to show status
show_status() {
    print_status "Showing status of all services..."

    echo ""
    echo "🔒 Secure Services (docker-compose-secure.yml):"
    docker-compose -f docker-compose-secure.yml ps 2>/dev/null || echo "  No services running"

    echo ""
    echo "🌐 Development Services (docker-compose-airflow.yml):"
    docker-compose -f docker-compose-airflow.yml ps 2>/dev/null || echo "  No services running"

    echo ""
    echo "🌍 Network Status:"
    docker network ls | grep crypto-network || echo "  crypto-network not found"
}

# Main script logic
case "${1:-help}" in
    secure)
        check_prerequisites
        deploy_secure
        ;;
    dev)
        check_prerequisites
        deploy_dev
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown option: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
