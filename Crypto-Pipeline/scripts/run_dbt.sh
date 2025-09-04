#!/bin/bash

# Smart DBT Runner Script
# Automatically detects project structure and runs dbt commands with correct profiles

set -e

# Function to find dbt project root
find_dbt_project() {
    local dir="$PWD"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/dbt_project.yml" ]]; then
            echo "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

# Function to find profiles.yml
find_profiles() {
    local dbt_root="$1"
    local profiles_dir="$dbt_root"

    # Check if profiles.yml exists in dbt root
    if [[ -f "$dbt_root/profiles.yml" ]]; then
        echo "$dbt_root"
        return 0
    fi

    # Check parent directory for profiles.yml
    local parent_dir=$(dirname "$dbt_root")
    if [[ -f "$parent_dir/profiles.yml" ]]; then
        echo "$parent_dir"
        return 0
    fi

    # Check dbt_crypto subdirectory
    if [[ -f "$dbt_root/dbt_crypto/profiles.yml" ]]; then
        echo "$dbt_root/dbt_crypto"
        return 0
    fi

    return 1
}

# Main execution
main() {
    echo "🔍 Detecting DBT project structure..."

    # Find dbt project root
    local dbt_root
    if ! dbt_root=$(find_dbt_project); then
        echo "❌ Error: No dbt_project.yml found in current or parent directories"
        echo "   Please run this script from within a dbt project"
        exit 1
    fi

    echo "📁 DBT project found at: $dbt_root"

    # Find profiles.yml
    local profiles_dir
    if ! profiles_dir=$(find_profiles "$dbt_root"); then
        echo "❌ Error: No profiles.yml found"
        echo "   Expected locations:"
        echo "     - $dbt_root/profiles.yml"
        echo "     - $(dirname "$dbt_root")/profiles.yml"
        echo "     - $dbt_root/dbt_crypto/profiles.yml"
        exit 1
    fi

    echo "📋 Profiles found at: $profiles_dir"

        # Determine the working directory for dbt commands
    local working_dir="$dbt_root"
    if [[ "$profiles_dir" == "$dbt_root/dbt_crypto" ]]; then
        working_dir="$dbt_root/dbt_crypto"
        echo "📂 DBT project has subdirectory structure, working from: $working_dir"
    else
        echo "📂 Changed to DBT project directory: $dbt_root"
    fi

    cd "$working_dir"

        # Run dbt command with correct profiles directory
    local relative_profiles_dir
    if [[ "$working_dir" == "$profiles_dir" ]]; then
        relative_profiles_dir="."
    else
        if command -v realpath >/dev/null 2>&1 && realpath --help 2>&1 | grep -q "relative-to"; then
            relative_profiles_dir=$(realpath --relative-to="$working_dir" "$profiles_dir")
        else
            # Fallback for macOS or systems without --relative-to option
            relative_profiles_dir=$(cd "$working_dir" && realpath "$profiles_dir" | sed "s|$(realpath "$working_dir")||" | sed 's|^/||')
        fi
    fi

    echo "🚀 Running: dbt $* --profiles-dir $relative_profiles_dir"
    echo ""

    poetry run dbt "$@" --profiles-dir "$relative_profiles_dir"
}

# Check if arguments provided
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <dbt_command> [options]"
    echo ""
    echo "Examples:"
    echo "  $0 run --target dev"
    echo "  $0 test --target dev"
    echo "  $0 build --target prod"
    echo "  $0 debug"
    echo ""
    echo "This script automatically detects your DBT project structure"
    echo "and runs commands with the correct profiles directory."
    exit 1
fi

# Run main function with all arguments
main "$@"
