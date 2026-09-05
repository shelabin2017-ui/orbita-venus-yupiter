#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Phone-friendly secrets setup:
# GitHub Codespaces secrets ORBITA_BOT_TOKEN and ORBITA_ADMIN_IDS are
# automatically converted into the local .env file. Nothing secret is committed.
if [ ! -f .env ]; then
  if [ -n "${ORBITA_BOT_TOKEN:-}" ] && [ -n "${ORBITA_ADMIN_IDS:-}" ]; then
    cat > .env <<EOF
# Generated automatically from GitHub Codespaces secrets.
BOT_TOKEN=${ORBITA_BOT_TOKEN}
ADMIN_IDS=${ORBITA_ADMIN_IDS}

POSTGRES_DB=orbita
POSTGRES_USER=orbita
POSTGRES_PASSWORD=${ORBITA_POSTGRES_PASSWORD:-orbita_local_dev}
DATABASE_URL=postgresql+asyncpg://orbita:${ORBITA_POSTGRES_PASSWORD:-orbita_local_dev}@postgres:5432/orbita
REDIS_URL=redis://redis:6379/0

MIN_AGE=18
MAX_AGE=99
FREE_DAILY_LIKES=20
VIP_DAILY_LIKES=200
MAX_PHOTOS=5
ANTISPAM_SECONDS=2
STARS_VIP_PRICE=100
VIP_DAYS=30
PROFILE_INACTIVE_DAYS=7
INACTIVITY_REMINDER_DAYS=14
ACTIVITY_TOUCH_INTERVAL_SECONDS=900
ACTIVITY_WORKER_SECONDS=600
AUTHOR_NAME=zeroshka
AUTHOR_URL=https://t.me/zeroshkaoff
AUTHOR_TIKTOK_URL=https://www.tiktok.com/@zeroshkayt?_r=1&_t=ZS-99TvDfLcoAU
BACKUP_DIR=/backups
EOF
    echo "Created .env from GitHub Codespaces secrets."
  else
    cp .env.example .env
    echo "Created .env from .env.example. Add BOT_TOKEN and ADMIN_IDS, or configure Codespaces secrets ORBITA_BOT_TOKEN and ORBITA_ADMIN_IDS."
  fi
fi

python -m compileall -q app

echo ""
echo "Orbita Codespace is ready."
echo "Start infrastructure: docker compose up -d postgres redis"
echo "Apply migrations: alembic upgrade head"
echo "Run bot: python -m app.main"
echo ""
