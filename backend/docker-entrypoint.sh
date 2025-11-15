#!/bin/sh
set -eu

POSTGRES_HOST="${POSTGRES_HOST:-}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-}"
POSTGRES_USER="${POSTGRES_USER:-}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
DB_WAIT_TIMEOUT="${DJANGO_DB_WAIT_TIMEOUT:-60}"

if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT} (timeout: ${DB_WAIT_TIMEOUT}s)..."
  python <<'PY'
import os
import sys
import time

import psycopg
from psycopg import OperationalError

host = os.environ.get("POSTGRES_HOST", "")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
dbname = os.environ.get("POSTGRES_DB", "")
user = os.environ.get("POSTGRES_USER", "")
password = os.environ.get("POSTGRES_PASSWORD", "")
timeout = int(os.environ.get("DJANGO_DB_WAIT_TIMEOUT", "60"))
deadline = time.time() + timeout

while True:
    try:
        psycopg.connect(host=host, port=port, dbname=dbname or None, user=user or None, password=password or None, connect_timeout=5).close()
        break
    except (OperationalError, psycopg.Error) as exc:
        if time.time() > deadline:
            raise SystemExit(f"PostgreSQL is unavailable after {timeout}s: {exc}") from exc
        time.sleep(1)
PY
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static assets..."
STATIC_ROOT="${DJANGO_STATIC_ROOT:-/app/staticfiles}"
mkdir -p "$STATIC_ROOT"
mkdir -p /app/logs
python manage.py collectstatic --noinput

exec "$@"
