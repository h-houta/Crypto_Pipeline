#!/bin/bash

# Clean DBT Environment Script
# This script removes conflicting packages and ensures clean dbt operation

set -e

echo "🧹 Cleaning DBT environment..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
else
    echo "❌ Error: Virtual environment not found. Run 'poetry install' first."
    exit 1
fi

# Remove problematic packages that conflict with dbt
echo "🗑️  Removing conflicting packages..."
poetry run pip uninstall pytest-dbt-adapter -y 2>/dev/null || true
poetry run pip uninstall dbt-adapter-tests -y 2>/dev/null || true

# Reinstall dbt dependencies
echo "🔄 Reinstalling DBT dependencies..."
poetry install -E dbt

# Verify dbt installation
echo "✅ Verifying DBT installation..."
poetry run dbt --version

echo "🎉 DBT environment cleaned successfully!"
echo ""
echo "Next steps:"
echo "  cd dbt_crypto"
echo "  poetry run dbt deps --profiles-dir ."
echo "  poetry run dbt run --target dev --profiles-dir ."
echo "  poetry run dbt test --target dev --profiles-dir ."
