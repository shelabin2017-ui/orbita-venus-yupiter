#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Codespaces secrets are environment variables inside the Codespace.
# Always sync credentials into .env when they are present. This fixes an older
# .env that was created from .env.example before the secrets were added.
if [ ! -f .env ]; then
  cp .env.example .env
fi

python - <<'PY'
from pathlib import Path
import os

p = Path('.env')
text = p.read_text(encoding='utf-8')
updates = {}
if os.getenv('ORBITA_BOT_TOKEN'):
    updates['BOT_TOKEN'] = os.environ['ORBITA_BOT_TOKEN']
if os.getenv('ORBITA_ADMIN_IDS'):
    updates['ADMIN_IDS'] = os.environ['ORBITA_ADMIN_IDS']
if os.getenv('ORBITA_OPENAI_API_KEY'):
    updates['PHOTO_MODERATION_API_KEY'] = os.environ['ORBITA_OPENAI_API_KEY']
    updates['PHOTO_MODERATION_ENABLED'] = 'true'
if os.getenv('ORBITA_OPENAI_MODEL'):
    updates['PHOTO_MODERATION_MODEL'] = os.environ['ORBITA_OPENAI_MODEL']

if updates:
    lines = text.splitlines()
    for key, value in updates.items():
        lines = [line for line in lines if not line.startswith(key + '=')]
        lines.append(f'{key}={value}')
    p.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    print('Synced Codespaces secrets: ' + ', '.join(sorted(updates)))
else:
    print('No ORBITA_* Codespaces secrets were visible during setup; runtime config will still check the environment.')
PY

python -m compileall -q app

echo ""
echo "Orbita Codespace is ready."
echo "Start infrastructure: docker compose up -d postgres redis"
echo "Apply migrations: alembic upgrade head"
echo "Run bot: python -m app.main"
echo ""
