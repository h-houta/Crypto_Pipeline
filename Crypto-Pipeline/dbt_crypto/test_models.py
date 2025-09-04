#!/usr/bin/env python3
"""
DBT Model Testing Script - Python Version
Tests and validates the DBT transformation models for crypto analytics
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
import psycopg2


# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_status(message, status='success'):
    """Print colored status messages"""
    if status == 'success':
        print(f"{GREEN}[✓]{RESET} {message}")
    elif status == 'error':
        print(f"{RED}[✗]{RESET} {message}")
    elif status == 'info':
        print(f"{YELLOW}[ℹ]{RESET} {message}")
    elif status == 'header':
        print(f"\n{BLUE}{'='*60}")
        print(f"{message}")
        print(f"{'='*60}{RESET}\n")


def run_command(command, description, capture_output=True):
    """Run a shell command and return success status"""
    try:
        if capture_output:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent
            )
            if result.returncode == 0:
                print_status(description)
                return True
            else:
                print_status(f"{description} - Failed", 'error')
                if not capture_output:
                    print(result.stderr)
                return False
        else:
            # Run without capturing output (for commands that need to show progress)
            result = subprocess.run(
                command,
                shell=True,
                cwd=Path(__file__).parent
            )
            if result.returncode == 0:
                print_status(description)
                return True
            else:
                print_status(f"{description} - Failed", 'error')
                return False
    except Exception as e:
        print_status(f"{description} - Error: {str(e)}", 'error')
        return False


def test_database_connection():
    """Test database connection using psycopg2"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="crypto_db",
            user="postgres",
            password="postgres"
        )
        conn.close()
        print_status("Database connection successful")
        return True
    except Exception as e:
        print_status(f"Database connection failed: {str(e)}", 'error')
        return False


def run_query(query, description):
    """Execute a query and display results"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="crypto_db",
            user="postgres",
            password="postgres"
        )
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()

        print(f"\n{description}:")
        if results:
            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Print header
            header = " | ".join(f"{col:15}" for col in columns)
            print(f"  {header}")
            print(f"  {'-' * len(header)}")

            # Print rows
            for row in results:
                row_str = " | ".join(f"{str(val)[:15]:15}" for val in row)
                print(f"  {row_str}")
        else:
            print("  No data available")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  Query failed: {str(e)}")
        return False


def main():
    """Main test execution"""
    print_status("DBT Crypto Analytics - Model Testing", 'header')

    # Change to DBT project directory
    os.chdir(Path(__file__).parent)

    # Test steps
    tests = [
        ("1. Checking DBT installation",
         "dbt --version > /dev/null 2>&1",
         "DBT is installed"),

        ("2. Testing database connection",
         None,  # Will use custom function
         "Database connection test"),

        ("3. Installing DBT dependencies",
         "dbt deps --profiles-dir . > /dev/null 2>&1",
         "Dependencies installed"),

        ("4. Compiling DBT models",
         "dbt compile --profiles-dir . > /dev/null 2>&1",
         "All models compiled successfully"),

        ("5. Running source data tests",
         "dbt test --select source:* --profiles-dir . > /dev/null 2>&1",
         "Source data tests completed"),
    ]

    # Run initial tests
    for step, command, description in tests:
        print(f"\n{step}")
        if command is None:
            # Custom test for database connection
            test_database_connection()
        else:
            run_command(command, description)

    # Run models
    print("\n6. Running DBT models")
    models = [
        ("stg_crypto_prices", "Staging model"),
        ("latest_crypto_prices", "Latest prices model"),
    ]

    for model, description in models:
        command = f"dbt run --select {model} --profiles-dir ."
        print(f"   Running {description}...")
        if not run_command(command, f"{description} created successfully", capture_output=False):
            print_status(f"Failed to create {description}", 'error')
            sys.exit(1)

    # Run incremental model with full refresh first
    print("\n7. Running incremental model (price_summary_15min)")
    print("   Initial full refresh...")
    if run_command(
        "dbt run --select price_summary_15min --full-refresh --profiles-dir .",
        "Full refresh completed",
        capture_output=False
    ):
        print("   Testing incremental update...")
        run_command(
            "dbt run --select price_summary_15min --profiles-dir .",
            "Incremental update successful",
            capture_output=False
        )

    # Run model tests
    print("\n8. Running model tests")
    run_command(
        "dbt test --exclude source:* --profiles-dir .",
        "Model tests completed",
        capture_output=False
    )

    # Generate documentation
    print("\n9. Generating documentation")
    run_command(
        "dbt docs generate --profiles-dir .",
        "Documentation generated"
    )

    # Query results
    print("\n10. Checking model results")
    print("-" * 40)

    queries = [
        ("SELECT COUNT(*) as row_count FROM stg_crypto_prices;",
         "Staging model row count"),

        ("SELECT symbol, ROUND(latest_price::numeric, 2) as price, "
         "ROUND(price_change_pct_24h::numeric, 2) as change_24h "
         "FROM latest_crypto_prices ORDER BY symbol LIMIT 5;",
         "Latest prices (top 5 symbols)"),

        ("SELECT COUNT(DISTINCT symbol) as unique_symbols, "
         "COUNT(*) as total_windows, "
         "TO_CHAR(MAX(window_start), 'YYYY-MM-DD HH24:MI') as latest_window "
         "FROM price_summary_15min;",
         "15-minute summary statistics"),

        ("SELECT symbol, TO_CHAR(window_start, 'HH24:MI') as time, "
         "ROUND(avg_price::numeric, 2) as avg_price, "
         "update_count, activity_level "
         "FROM price_summary_15min "
         "WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour' "
         "ORDER BY window_start DESC, symbol LIMIT 5;",
         "Recent 15-minute windows"),
    ]

    for query, description in queries:
        run_query(query, description)

    # Summary
    print_status("DBT Model Testing Complete!", 'header')
    print_status("To view documentation: dbt docs serve --profiles-dir .", 'info')
    print_status("To schedule models: Use Airflow DAG (crypto_dbt_dag.py)", 'info')
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Error: {str(e)}{RESET}")
        sys.exit(1)
