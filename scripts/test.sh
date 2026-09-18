#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "==> Running Automated Tests..."

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

echo "--> Python Test Suite:"
PYTHONPATH=. pytest tests services/api/tests

echo "--> TypeScript Workspace Typecheck:"
npm run typecheck

echo "==> All test suites passed successfully!"
