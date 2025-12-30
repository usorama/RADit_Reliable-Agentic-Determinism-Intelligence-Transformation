#!/bin/bash
# Setup script: Configure git to use project hooks
#
# Run this once after cloning the repository:
#   ./scripts/setup-hooks.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Configuring git to use project hooks..."

# Set the hooks path to our .githooks directory
git config core.hooksPath .githooks

echo "Git hooks configured successfully!"
echo ""
echo "Installed hooks:"
ls -la "$PROJECT_ROOT/.githooks/"
echo ""
echo "The pre-commit hook will auto-regenerate docs/codebase_map.json"
echo "when Python source files in packages/daw-agents/src/ are modified."
