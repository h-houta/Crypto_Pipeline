#!/bin/bash

# Clean up environment script to remove old paths
echo "Cleaning up environment..."

# Remove old Downloads/Beltone paths from PATH
export PATH=$(echo $PATH | tr ':' '\n' | grep -v "Downloads/Beltone" | tr '\n' ':' | sed 's/:$//')

# Remove old venv_py311 paths from PATH
export PATH=$(echo $PATH | tr ':' '\n' | grep -v "venv_py311" | tr '\n' ':' | sed 's/:$//')

# Ensure current project's .venv is in PATH
if [[ ":$PATH:" != *":$(pwd)/.venv/bin:"* ]]; then
    export PATH="$(pwd)/.venv/bin:$PATH"
fi

echo "Environment cleaned up!"
echo "Current PATH:"
echo $PATH | tr ':' '\n' | grep -E "(\.venv|pyenv|bin)" | head -10

echo ""
echo "To make this permanent, add this to your ~/.zshrc:"
echo "export PATH=\$(echo \$PATH | tr ':' '\n' | grep -v 'Downloads/Beltone' | grep -v 'venv_py311' | tr '\n' ':' | sed 's/:\$//')"
