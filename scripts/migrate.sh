#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "==> Running NEXUS Database Migrations..."
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

alembic -c infra/database/alembic.ini upgrade head
echo "==> Migrations complete!"
