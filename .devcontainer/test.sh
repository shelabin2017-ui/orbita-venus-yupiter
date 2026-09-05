#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
fi

docker compose up -d postgres redis
trap 'docker compose down' EXIT

python -m compileall -q app

echo "Waiting for PostgreSQL and Redis..."
for i in {1..30}; do
  if docker compose exec -T postgres pg_isready -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2)" -d "$(grep '^POSTGRES_DB=' .env | cut -d= -f2)" >/dev/null 2>&1 \
    && docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

alembic upgrade head

echo "Database migrations: OK"
echo "Python compilation: OK"
