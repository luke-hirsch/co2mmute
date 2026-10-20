#!/usr/bin/env bash
#
# The local development stack: Postgres and Redis in Docker, the rest native.
#
#   devops/dev.sh up            start everything
#   devops/dev.sh status        what is running
#   devops/dev.sh logs web -f   follow one service
#   devops/dev.sh test          the suite, in the environment CI has
#   devops/dev.sh down          stop it again
#
# THE DATABASE
#   One Postgres and one Redis: the `postgres` and `redis` services of
#   devops/docker-compose.yaml, the ones the box runs. `up` starts only those
#   two, with their ports on localhost (docker-compose.dev.yaml: Postgres on
#   5432, Redis on 6380), and runs everything else natively. The app, the suite
#   and calibrate_map all use this one server; the suite makes and drops a test
#   database of its own on it. Name, user and password come from devops/.env, as
#   for the compose stack, or its defaults.
#
#   The compose stack's own app (`docker compose up` in devops/) reads the same
#   database: run one of the two at a time. A `docker compose up` without the
#   dev file takes the ports away; the next `dev.sh up` puts them back. `down`
#   leaves Postgres and Redis running.
#
# WHAT RUNS
#   postgres   docker, see above.
#   redis      docker, see above. It carries the channel layer, the cache and
#              the Celery broker — all three come off the one REDIS_URL.
#   web        ./manage.py runserver — which IS Daphne, because `daphne` is
#              first in INSTALLED_APPS, so websockets work with no extra
#              process. Auto-reloads.
#   worker     celery worker. Does NOT auto-reload: `dev.sh restart worker`
#              after touching game/tasks.py or anything the simulation imports.
#   beat       celery beat. Its schedule file goes in devops/.dev/.
#   vite       the SPA, plus the proxy that makes :5173 the whole origin.
#   css        tailwind --watch=always for the Django templates. The container
#              entrypoint used to build this; nothing else does natively, and
#              without it every server-rendered page is unstyled.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$REPO/devops/.dev"
SERVICES=(web worker beat vite css)

COMPOSE_FILES=(-f "$REPO/devops/docker-compose.yaml" -f "$REPO/devops/docker-compose.dev.yaml")

mkdir -p "$STATE"

# ── the environment ──────────────────────────────────────────────────────────

secret_key() {
  if [ ! -f "$STATE/secret" ]; then
    LC_ALL=C tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 64 >"$STATE/secret"
  fi
  cat "$STATE/secret"
}

# What the compose stack reads from devops/.env, else docker-compose.yaml's
# own default.
compose_value() {
  local value=""
  if [ -f "$REPO/devops/.env" ]; then
    value="$(sed -n "s/^$1=//p" "$REPO/devops/.env" | tail -n 1)"
    value="${value%\"}"; value="${value#\"}"; value="${value%\'}"; value="${value#\'}"
  fi
  echo "${value:-$2}"
}

PG_DB="$(compose_value POSTGRES_DB co2mmute)"
PG_USER="$(compose_value POSTGRES_USER co2mmute)"
PG_PASSWORD="$(compose_value POSTGRES_PASSWORD co2mmute)"

dev_env() {
  cat <<ENV
export DJANGO_DEBUG='True'
export POSTGRES_HOST='127.0.0.1'
export POSTGRES_PORT='5432'
export POSTGRES_DB='$PG_DB'
export POSTGRES_USER='$PG_USER'
export POSTGRES_PASSWORD='$PG_PASSWORD'
export REDIS_URL='redis://127.0.0.1:6380/0'
export DJANGO_SECRET_KEY='$(secret_key)'
export DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1'
export DJANGO_CSRF_TRUSTED_ORIGINS='https://localhost:5173,http://localhost:5173,http://localhost:8000,http://127.0.0.1:8000'
export DJANGO_BASE_URL='https://localhost:5173'
export BACKEND_ORIGIN='http://127.0.0.1:8000'
ENV
}

load_env() { eval "$(dev_env)"; }

# ── the interpreter ──────────────────────────────────────────────────────────

find_python() {
  if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    echo "$VIRTUAL_ENV/bin/python"; return
  fi
  local pyenv_root="${PYENV_ROOT:-$HOME/.pyenv}"
  if [ -x "$pyenv_root/versions/commute/bin/python" ]; then
    echo "$pyenv_root/versions/commute/bin/python"; return
  fi
  if [ -x "$REPO/.venv/bin/python" ]; then
    echo "$REPO/.venv/bin/python"; return
  fi
  cat >&2 <<'MSG'
No Python environment found. Expected the pyenv virtualenv `commute`:

    pyenv virtualenv 3.13.3 commute
    ~/.pyenv/versions/commute/bin/pip install -r backend/requirements.txt
    ~/.pyenv/versions/commute/bin/pip install 'psycopg[binary]'

The last line is local-only and deliberately NOT in requirements.txt: the
Debian-based backend image already carries libpq, and adding the binary wheel
would change what the box installs.
MSG
  exit 1
}

PYTHON="$(find_python)"
BIN="$(dirname "$PYTHON")"

# ── process bookkeeping ──────────────────────────────────────────────────────

pid_file() { echo "$STATE/$1.pid"; }
log_file() { echo "$STATE/$1.log"; }
pgid_of()  { ps -o pgid= -p "$1" 2>/dev/null | tr -d ' ' || true; }

is_running() {
  local file; file="$(pid_file "$1")"
  [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null
}

start_service() {
  local name="$1" dir="$2"
  shift 2
  if is_running "$name"; then
    echo "  $name already running"
    return
  fi
  # stdin from /dev/null: a service in its own process group that reads the
  # terminal gets EIO once this script exits, and Node 26 dies of it — vite
  # reads stdin for its key shortcuts, tailwind's watcher to notice a close.
  set -m
  ( cd "$dir" && exec "$@" ) </dev/null >"$(log_file "$name")" 2>&1 &
  local pid=$!
  set +m
  echo "$pid" >"$(pid_file "$name")"
  echo "  $name started (pid $pid)"
}

stop_service() {
  local name="$1" file pid pgid
  file="$(pid_file "$name")"
  [ -f "$file" ] || return 0
  pid="$(cat "$file")"
  pgid="$(pgid_of "$pid")"
  if [ -n "$pgid" ]; then
    kill -TERM "-$pgid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.3
    done
    kill -KILL "-$pgid" 2>/dev/null || true
  fi
  rm -f "$file"
  echo "  $name stopped"
}

# ── infrastructure ───────────────────────────────────────────────────────────

# docker compose on the box's file with the dev ports on top. The file insists
# on a DJANGO_SECRET_KEY for the app containers; this never starts them, but a
# fresh clone has no devops/.env yet, so it gets the dev key to read.
compose() {
  DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-$(secret_key)}" docker compose "${COMPOSE_FILES[@]}" "$@"
}

ensure_services() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop (or the docker daemon) and try again." >&2
    exit 1
  fi
  compose up -d --wait postgres redis
}

# Running and reachable from here: a `docker compose up` without the dev file
# leaves the container running with no port.
service_state() {
  docker info >/dev/null 2>&1 || { echo "down (docker is not running)"; return; }
  if [ -z "$(compose ps --status running -q "$1" 2>/dev/null)" ]; then
    echo "down"
    return
  fi
  # `compose port` answers ":0" for a port that is not published.
  case "$(compose port "$1" "$2" 2>/dev/null)" in
    "" | *:0) echo "running without its port: devops/dev.sh up" ;;
    *)        echo "up" ;;
  esac
}

# ── commands ─────────────────────────────────────────────────────────────────

cmd_env() { dev_env; }

cmd_css() {
  echo "→ building the backend Tailwind bundle"
  ( cd "$REPO/backend" && npm run --silent build:css )
}

cmd_migrate() {
  load_env
  ( cd "$REPO/backend" && "$PYTHON" manage.py migrate --noinput )
}

cmd_reset_db() {
  ensure_services
  compose exec -T postgres dropdb --force --if-exists -U "$PG_USER" "$PG_DB"
  compose exec -T postgres createdb -U "$PG_USER" "$PG_DB"
  echo "→ database $PG_DB emptied"
  cmd_migrate
  echo
  echo "   Put a map and a staff account back with:"
  echo "     cd frontend && npm run e2e:seed"
}

cmd_up() {
  ensure_services

  # The tracked static/css/tailwind.css is an empty placeholder — the container
  # entrypoint used to fill it. Nothing does that natively, so a first run must.
  if [ ! -s "$REPO/backend/static/css/tailwind.css" ]; then
    cmd_css
  fi

  cmd_migrate

  echo "→ starting"
  # Written the long way on purpose: macOS ships bash 3.2, where an empty array
  # under `set -u` is an unbound variable rather than an empty expansion.
  local wanted
  if [ $# -gt 0 ]; then wanted=("$@"); else wanted=("${SERVICES[@]}"); fi

  load_env
  for name in "${wanted[@]}"; do
    case "$name" in
      web)    start_service web "$REPO/backend" "$PYTHON" manage.py runserver 127.0.0.1:8000 ;;
      worker) start_service worker "$REPO/backend" "$BIN/celery" -A co2mmute worker -l info ;;
      beat)   start_service beat "$REPO/backend" "$BIN/celery" -A co2mmute beat -l info \
                 --schedule "$STATE/celerybeat-schedule" ;;
      vite)   start_service vite "$REPO/frontend" npm run --silent dev ;;
      css)    start_service css "$REPO/backend" npm run --silent watch:css ;;
      *)      echo "unknown service: $name" >&2; exit 1 ;;
    esac
  done

  echo
  echo "   https://localhost:5173        everything — SPA, landing, lobby, join, admin"
  echo "   http://127.0.0.1:8000         Django on its own, unproxied"
  echo
  echo "   devops/dev.sh logs web -f     follow a service"
  echo "   devops/dev.sh down            stop"
}

cmd_down() {
  for name in "${SERVICES[@]}"; do stop_service "$name"; done
}

cmd_restart() {
  [ $# -gt 0 ] || { echo "restart needs a service name" >&2; exit 1; }
  local wanted=("$@")
  for name in "${wanted[@]}"; do stop_service "$name"; done
  cmd_up "${wanted[@]}"
}

cmd_status() {
  printf "  %-8s %s\n" "postgres" "$(service_state postgres 5432) (docker, 127.0.0.1:5432, database $PG_DB)"
  printf "  %-8s %s\n" "redis" "$(service_state redis 6379) (docker, 127.0.0.1:6380)"
  for name in "${SERVICES[@]}"; do
    if is_running "$name"; then
      printf "  %-8s running (pid %s)\n" "$name" "$(cat "$(pid_file "$name")")"
    else
      printf "  %-8s stopped\n" "$name"
    fi
  done
}

cmd_logs() {
  local name="${1:-web}"; shift || true
  local file; file="$(log_file "$name")"
  [ -f "$file" ] || { echo "no log for $name yet" >&2; exit 1; }
  if [ "${1:-}" = "-f" ]; then tail -f "$file"; else tail -n 100 "$file"; fi
}

cmd_manage() {
  load_env
  ( cd "$REPO/backend" && exec "$PYTHON" manage.py "$@" )
}


cmd_test() {
  ensure_services
  ( cd "$REPO/backend" && env -i \
      PATH="$PATH" HOME="$HOME" LANG="${LANG:-en_US.UTF-8}" \
      POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 \
      POSTGRES_DB="$PG_DB" POSTGRES_USER="$PG_USER" POSTGRES_PASSWORD="$PG_PASSWORD" \
      "$PYTHON" manage.py test --settings=co2mmute.settings_test --noinput "$@" )
}

usage() {
  sed -n '3,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  echo "commands: up down restart status logs env manage test css migrate reset-db"
}

case "${1:-}" in
  up)       shift; cmd_up "$@" ;;
  down)     cmd_down ;;
  restart)  shift; cmd_restart "$@" ;;
  status)   cmd_status ;;
  logs)     shift; cmd_logs "$@" ;;
  env)      cmd_env ;;
  manage)   shift; cmd_manage "$@" ;;
  test)     shift; cmd_test "$@" ;;
  css)      cmd_css ;;
  migrate)  cmd_migrate ;;
  reset-db) cmd_reset_db ;;
  *)        usage ;;
esac
