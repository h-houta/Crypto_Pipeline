#!/bin/bash

# Complete cleanup script for removing all traces of old paths
echo "Starting complete cleanup of old paths..."

# Clean up PATH environment variable
export PATH=$(echo $PATH | tr ':' '\n' | grep -v "Downloads/Beltone" | grep -v "venv_py311" | tr '\n' ':' | sed 's/:$//')

# Clean up Python cache files
echo "Cleaning up Python cache files..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Clean up old log files that might contain old paths
echo "Cleaning up old log files..."
rm -rf dbt_crypto/logs/* 2>/dev/null || true

# Ensure current project's virtual environment is properly set up
if [[ ":$PATH:" != *":$(pwd)/.venv/bin:"* ]]; then
    export PATH="$(pwd)/.venv/bin:$PATH"
    echo "Added current project's .venv to PATH"
fi

# Verify Pylint is working
echo "Testing Pylint configuration..."
if source .venv/bin/activate && command -v pylint &> /dev/null; then
    echo "Pylint is available and working"
    echo "Testing Pylint on a sample file..."
    source .venv/bin/activate && pylint producer/test_producer.py --rcfile=.pylintrc --disable=all --score=n 2>/dev/null && echo "Pylint test completed successfully!" || echo "Pylint test completed"
else
    echo "Warning: Pylint not found or not working properly"
fi

echo ""
echo "Cleanup completed!"
echo "Current PATH:"
echo $PATH | tr ':' '\n' | grep -E "(\.venv|pyenv|bin)" | head -10

echo ""
echo "To verify no old paths remain, run:"
echo "echo \$PATH | tr ':' '\n' | grep 'Downloads/Beltone\|venv_py311' || echo 'No old paths found'"
