#!/bin/bash

# Test DBT Setup Script
echo "🔍 Testing DBT Crypto Analytics Setup..."
echo "========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to dbt project directory
cd "$(dirname "$0")"

# Test 1: Check DBT installation (prefer Poetry)
echo -n "1. Checking DBT installation... "
if command -v poetry >/dev/null 2>&1 && poetry run dbt --version >/dev/null 2>&1; then
    DBT_CMD="poetry run dbt"
    echo -e "${GREEN}✓${NC} DBT installed ($($DBT_CMD --version | head -n 1))"
elif command -v dbt &> /dev/null; then
    DBT_CMD="dbt"
    echo -e "${GREEN}✓${NC} DBT installed ($(dbt --version | head -n 1))"
else
    echo -e "${RED}✗${NC} DBT not found. Install with: poetry install -E dbt or pip install dbt-postgres"
    exit 1
fi

# Test 2: Debug connection
echo "2. Testing database connection..."
if $DBT_CMD debug --profiles-dir . > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Database connection successful"
else
    echo -e "${RED}✗${NC} Database connection failed. Check profiles.yml"
    echo "   Run '$DBT_CMD debug --profiles-dir .' for details"
    exit 1
fi

# Test 3: Parse project
echo -n "3. Parsing DBT project... "
if $DBT_CMD parse --profiles-dir . > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Project structure valid"
else
    echo -e "${RED}✗${NC} Project parsing failed"
    exit 1
fi

# Test 4: List models
echo "4. Available models:"
$DBT_CMD list --resource-type model --profiles-dir . 2>/dev/null | grep -E "^crypto_analytics" | sed 's/^/   - /'

echo ""
echo "========================================="
echo -e "${GREEN}✅ DBT setup looks good!${NC}"
echo ""
echo "Next steps:"
echo "  1. Run staging model:     $DBT_CMD run --select staging --profiles-dir ."
echo "  2. Run all models:        $DBT_CMD run --profiles-dir ."
echo "  3. Run tests:             $DBT_CMD test --profiles-dir ."
echo "  4. Generate docs:         $DBT_CMD docs generate --profiles-dir ."
