#!/bin/bash

# Test Pylint configuration
echo "Testing Pylint configuration..."

# Activate virtual environment
source .venv/bin/activate

# Check Pylint version
echo "Pylint version:"
pylint --version

# Test Pylint on a sample file
echo -e "\nTesting Pylint on producer/test_producer.py:"
pylint producer/test_producer.py --rcfile=.pylintrc

# Test Pylint using pyproject.toml config
echo -e "\nTesting Pylint using pyproject.toml configuration:"
pylint producer/test_producer.py

echo -e "\nPylint test completed!"
