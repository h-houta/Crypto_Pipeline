#!/bin/bash

# DBT Model Testing Script
# This script validates and runs the DBT transformation models

set -e  # Exit on error

echo "================================================"
echo "DBT Crypto Analytics - Model Testing Script"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Navigate to DBT project directory
cd "$(dirname "$0")"

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[ℹ]${NC} $1"
}

# Resolve dbt CLI (prefer Poetry)
if command -v poetry >/dev/null 2>&1 && poetry run dbt --version >/dev/null 2>&1; then
    DBT="poetry run dbt"
else
    if command -v dbt >/dev/null 2>&1; then
        DBT="$(command -v dbt)"
    else
        print_error "DBT is not installed. Install with 'poetry install -E dbt' <<preferred>> or 'pip install dbt-postgres'."
        exit 1
    fi
fi

# DB connection defaults (align with profiles.yml)
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5434}
DB_NAME=${DB_NAME:-crypto_db}
DB_USER=${DB_USER:-crypto_user}
DB_PASSWORD=${DB_PASSWORD:-cryptopass123}

# Check if DBT is installed
echo "1. Checking DBT installation..."
print_status "Using DBT: $DBT"
"$DBT" --version | head -n 1 || { print_error "DBT not working"; exit 1; }

# Test database connection
echo ""
echo "2. Testing database connection..."
if "$DBT" debug --profiles-dir . > /dev/null 2>&1; then
    print_status "Database connection successful"
else
    print_error "Database connection failed. Please check your profiles.yml"
    exit 1
fi

# Install DBT dependencies (if any)
echo ""
echo "3. Installing DBT dependencies..."
if "$DBT" deps --profiles-dir . > /dev/null 2>&1; then
    print_status "Dependencies installed"
else
    print_info "No dependencies to install or already installed"
fi

# Compile DBT project to check for syntax errors
echo ""
echo "4. Compiling DBT models..."
if "$DBT" compile --profiles-dir . > /dev/null 2>&1; then
    print_status "All models compiled successfully"
else
    print_error "Model compilation failed. Check for syntax errors."
    "$DBT" compile --profiles-dir .
    exit 1
fi

# Run DBT tests on source data
echo ""
echo "5. Running source data tests..."
if "$DBT" test --select source:* --profiles-dir . > /dev/null 2>&1; then
    print_status "Source data tests passed"
else
    print_info "Some source tests failed (this may be expected if no data yet)"
fi

# Run staging models
echo ""
echo "6. Running staging models..."
if "$DBT" run --select stg_crypto_prices --profiles-dir .; then
    print_status "Staging model created successfully"
else
    print_error "Failed to create staging model"
    exit 1
fi

# Run latest_crypto_prices model
echo ""
echo "7. Running latest_crypto_prices model..."
if "$DBT" run --select latest_crypto_prices --profiles-dir .; then
    print_status "latest_crypto_prices model created successfully"
else
    print_error "Failed to create latest_crypto_prices model"
    exit 1
fi

# Run price_summary_15min model (full refresh first time)
echo ""
echo "8. Running price_summary_15min model..."
if "$DBT" run --select price_summary_15min --full-refresh --profiles-dir .; then
    print_status "price_summary_15min model created successfully"
else
    print_error "Failed to create price_summary_15min model"
    exit 1
fi

# Test incremental update on price_summary_15min
echo ""
echo "9. Testing incremental update on price_summary_15min..."
if "$DBT" run --select price_summary_15min --profiles-dir .; then
    print_status "Incremental update successful"
else
    print_error "Failed incremental update"
    exit 1
fi

# Run all model tests
echo ""
echo "10. Running model tests..."
if "$DBT" test --exclude source:* --profiles-dir . > /dev/null 2>&1; then
    print_status "All model tests passed"
else
    print_info "Some model tests failed (review test results)"
    "$DBT" test --exclude source:* --profiles-dir .
fi

# Generate documentation
echo ""
echo "11. Generating documentation..."
if "$DBT" docs generate --profiles-dir . > /dev/null 2>&1; then
    print_status "Documentation generated successfully"
else
    print_info "Documentation generation skipped"
fi

# Show model row counts
echo ""
echo "12. Checking model results..."
echo "-----------------------------------"

# Function to run query and display results
run_query() {
    local query=$1
    local description=$2

    echo "$description:"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "$query" 2>/dev/null || echo "  No data available"
    echo ""
}

# Check staging model
run_query "SELECT COUNT(*) as row_count FROM stg_crypto_prices LIMIT 1;" \
          "  Staging model row count"

# Check latest prices
run_query "SELECT symbol, ROUND(latest_price::numeric, 2) as price,
           ROUND(price_change_pct_24h::numeric, 2) as change_24h_pct
           FROM latest_crypto_prices
           ORDER BY symbol LIMIT 5;" \
          "  Latest prices (top 5)"

# Check 15-min summaries
run_query "SELECT COUNT(DISTINCT symbol) as symbols,
           COUNT(*) as total_windows,
           MAX(window_start) as latest_window
           FROM price_summary_15min;" \
          "  15-minute summary statistics"

# Check recent 15-min windows
run_query "SELECT symbol, window_start,
           ROUND(avg_price::numeric, 2) as avg_price,
           update_count, activity_level
           FROM price_summary_15min
           WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
           ORDER BY window_start DESC, symbol
           LIMIT 5;" \
          "  Recent 15-min windows (last hour)"

echo "================================================"
echo "DBT Model Testing Complete!"
echo "================================================"
echo ""
print_info "To view the DBT documentation, run: $DBT docs serve --profiles-dir ."
print_info "To run models on a schedule, use the Airflow DAG: crypto_dbt_dag.py"
echo ""
