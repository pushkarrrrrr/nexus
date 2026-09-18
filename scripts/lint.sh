#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "==> Running Linting & Quality Checks..."

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

echo "--> Python Ruff Linting:"
ruff check .

echo "--> Python Ruff Format Check:"
ruff format --check .

echo "--> TypeScript Typecheck:"
npm run typecheck

echo "==> All quality checks passed!"
