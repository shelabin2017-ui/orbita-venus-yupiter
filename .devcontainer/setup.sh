#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Codespaces secrets are environment variables inside the Codespace.
# Always sync the two required bot secrets into .env when they are present.
# This also fixes an older .env that was created from .env.example before
# the Codespaces secrets were added.
if [ -n "${ORBITA_BOT_TOKEN:-}" ] && [ -n "${ORBITA_ADMIN_IDS:-}" ]; then
  if [ ! -f .env ]; then
    cp .env.example .env
  fi
  python - <<'PY'
from pathlib import Path
import os

p = Path('.env')
text = p.read_text(encoding='utf-8') if p.exists() else ''
lines = [line for line in text.splitlines() if not line.startswith(('BOT_TOKEN=', 'ADMIN_IDS='))]
lines += [
    f"BOT_TOKEN={os.environ['ORBITA_BOT_TOKEN']}",
    f"ADMIN_IDS={os.environ['ORBITA_ADMIN_IDS']}",
]
p.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
PY
  echo "Synced BOT_TOKEN and ADMIN_IDS from Codespaces secrets."
else
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
  fi
  echo "Codespaces bot secrets are not visible to setup.sh; runtime config will also try ORBITA_BOT_TOKEN and ORBITA_ADMIN_IDS."
fi

python -m compileall -q app

echo ""
echo "Orbita Codespace is ready."
echo "Start infrastructure: docker compose up -d postgres redis"
echo "Apply migrations: alembic upgrade head"
echo "Run bot: python -m app.main"
echo ""
