#!/bin/sh
set -eu
mkdir -p /backups
STAMP=$(date -u +%Y-%m-%d_%H-%M-%S)
FILE="/backups/orbita_${STAMP}.dump"
pg_dump --format=custom --no-owner --no-acl --dbname="$DATABASE_URL" > "$FILE"
find /backups -type f -name 'orbita_*.dump' -mtime +14 -delete
