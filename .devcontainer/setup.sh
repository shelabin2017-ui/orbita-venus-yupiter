#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Set BOT_TOKEN and database values before starting the bot."
fi

python -m compileall -q app

echo ""
echo "Orbita Codespace is ready."
echo "Start infrastructure: docker compose up -d postgres redis"
echo "Apply migrations: alembic upgrade head"
echo "Run bot: python -m app.main"
echo ""
