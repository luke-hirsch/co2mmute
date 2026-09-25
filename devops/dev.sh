#!/usr/bin/env bash
#
# The local development stack. No Docker.
#
#   devops/dev.sh up            start everything
#   devops/dev.sh status        what is running
#   devops/dev.sh logs web -f   follow one service
#   devops/dev.sh test          the suite, in the environment CI has
#   devops/dev.sh down          stop it again
#
# Docker was here to spare a developer who is no longer on the team the job of
# setting five services up by hand. Everything now runs on the host, the way jac
# does. `devops/docker-compose.yaml` stays exactly as it is — it is how the box
# is deployed and `main → prod` still goes through it — it is just not what a
# working day touches any more.
#
# Everything lands on ONE origin, https://localhost:5173. The Vite dev server
# proxies every path Django owns, the way nginx does in the container, so the
# landing page, the lobby, the join flow, the legal pages and the admin are all
# there beside the SPA — and a session cookie set by one reaches the other. That
# matters more here than in a pure SPA: this is a hybrid, the funnel is
# server-rendered.
#
# WHICH DATABASE
#   The app runs on sqlite, at backend/db.sqlite3. That is settings.py's own
#   default whenever DEBUG is on, so it needs no override: disposable, no server
#   to keep running. `dev.sh reset-db` throws it away.
#
#   The SUITE runs on Postgres, and that is not a preference — settings_test.py
#   has forced it since 1.5, because sqlite makes select_for_update() a no-op,
#   so the row locks the capacity check and the anonymisation depend on would go
#   untested while staying green. On top of that the simulation is seeded off
#   the round pk: Postgres sequences climb through a run while sqlite reuses the
#   rowid after each TestCase, so a sqlite suite draws different seeds than CI
#   does. That has cost a day twice. Hence `brew install postgresql@18` — the
#   same major the box runs, native, no container.
#
#   To run the app on Postgres too (closer to the box, and it keeps its data):
#       DJANGO_DB=postgres devops/dev.sh up
#
# WHAT RUNS
#   postgres   brew service, used by the suite only.
#   redis      the valkey brew already runs, on database index 3 so it cannot
#              collide with another project on this machine. It carries the
#              channel layer, the cache and the Celery broker — all three come
#              off the one REDIS_URL.
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

PG_BIN="/opt/homebrew/opt/postgresql@18/bin"
[ -d "$PG_BIN" ] || PG_BIN=""

mkdir -p "$STATE"

# ── the environment ──────────────────────────────────────────────────────────

# A key of its own, generated once and kept out of git. It has to be stable
# across restarts or every player cookie in flight is invalidated: both are
# TimestampSigner values salted from SECRET_KEY.
secret_key() {
  if [ ! -f "$STATE/secret" ]; then
    # Alphanumerics only. This value is interpolated into `export` lines that
    # get eval'd, and a shell metacharacter in it is a syntax error rather than
    # a weaker key. 64 of these is ~380 bits.
    LC_ALL=C tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 64 >"$STATE/secret"
  fi
  cat "$STATE/secret"
}

dev_env() {
  cat <<ENV
export DJANGO_DEBUG='True'
export DJANGO_DB='${DJANGO_DB:-sqlite}'
export POSTGRES_HOST='localhost'
export POSTGRES_PORT='5432'
export POSTGRES_DB='commute'
export POSTGRES_USER='commute'
export POSTGRES_PASSWORD='commute'
export REDIS_URL='redis://127.0.0.1:6379/3'
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
  # `set -m` gives the background job a process group of its own, so stopping it
  # signals the whole tree. Django's autoreloader forks a child, and killing the
  # parent alone would leave that child holding port 8000.
  set -m
  ( cd "$dir" && exec "$@" ) >"$(log_file "$name")" 2>&1 &
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

ensure_redis() {
  local cli
  cli="$(command -v redis-cli || command -v valkey-cli || true)"
  [ -n "$cli" ] || { echo "note: no redis-cli to check with; assuming 6379 is up" >&2; return; }
  "$cli" -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1 && return
  cat >&2 <<'MSG'
Nothing is answering on 127.0.0.1:6379.

    brew services start valkey

Valkey is a Redis fork and speaks the same protocol, so the channel layer, the
cache and the Celery broker all take it unchanged.
MSG
  exit 1
}

ensure_postgres() {
  [ -n "$PG_BIN" ] || { echo "postgresql@18 is not installed: brew install postgresql@18" >&2; exit 1; }
  "$PG_BIN/pg_isready" -q 2>/dev/null && return
  cat >&2 <<'MSG'
Postgres is not accepting connections.

    brew services start postgresql@18

It is only needed for the test suite — the app itself runs on sqlite.
MSG
  exit 1
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
  load_env
  rm -f "$REPO/backend/db.sqlite3"
  echo "→ sqlite database removed"
  cmd_migrate
  echo
  echo "   Put a map and a staff account back with:"
  echo "     cd frontend && npm run e2e:seed"
}

cmd_up() {
  ensure_redis
  [ "${DJANGO_DB:-sqlite}" = "sqlite" ] || ensure_postgres

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
  local redis="down" pg="down"
  (command -v redis-cli >/dev/null 2>&1 && redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1) && redis="up"
  [ -n "$PG_BIN" ] && "$PG_BIN/pg_isready" -q 2>/dev/null && pg="up"
  printf "  %-8s %s\n" "redis" "$redis (valkey, db 3)"
  printf "  %-8s %s\n" "postgres" "$pg (brew, suite only)"
  printf "  %-8s %s\n" "app db" "${DJANGO_DB:-sqlite}"
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

# The suite, in the environment CI actually has — which is POSTGRES_* and
# nothing else. Deliberately does NOT load the dev environment: settings.py
# derives things at import from os.environ, and a run carrying DJANGO_DEBUG or
# DJANGO_SECRET_KEY is not the run the runner does. Four red CI runs once looked
# unexplainable from a locally green suite for exactly that reason, and against
# the container it took a wall of `env -u` flags to reproduce.
cmd_test() {
  ensure_postgres
  ( cd "$REPO/backend" && env -i \
      PATH="$PATH" HOME="$HOME" LANG="${LANG:-en_US.UTF-8}" \
      POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
      POSTGRES_DB=commute POSTGRES_USER=commute POSTGRES_PASSWORD=commute \
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
