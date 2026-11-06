#!/usr/bin/env bash
# Run Playwright against an isolated test stack.
#
# The test stack uses its own PostgreSQL container/database (postgres-e2e /
# petcare_e2e), its own backend on port 8001, and its own photo volume. The real
# petcare database and petphotos volume are never used by these tests.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE=(docker compose -p petcare-e2e -f "$ROOT_DIR/docker-compose.e2e.yml")
DB_NAME="petcare_e2e"
API_URL="http://127.0.0.1:8001"
WEB_URL="http://127.0.0.1:5174"
VITE_LOG="$ROOT_DIR/frontend/.e2e-vite.log"
VITE_PID=""

log() { printf '[e2e] %s\n' "$*"; }
fail() {
  printf '[e2e] ERROR: %s\n' "$*" >&2
  exit 1
}

on_exit() {
  local status=$?

  if [ -n "$VITE_PID" ]; then
    kill "$VITE_PID" >/dev/null 2>&1 || true
    wait "$VITE_PID" 2>/dev/null || true
  fi

  if ((status != 0)); then
    log "E2E failed (exit $status). Recent test-stack logs:"
    if [ -f "$VITE_LOG" ]; then
      log "Vite log ($VITE_LOG):"
      tail -n 40 "$VITE_LOG" || true
    fi
    "${COMPOSE[@]}" logs --tail=40 postgres-e2e web-e2e || true
  fi

  exit "$status"
}
trap on_exit EXIT

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
command -v curl >/dev/null 2>&1 || fail "curl is required for the readiness check"

log "Starting isolated PostgreSQL..."
"${COMPOSE[@]}" up -d postgres-e2e

for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T postgres-e2e pg_isready -U petcare -d "$DB_NAME" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
"${COMPOSE[@]}" exec -T postgres-e2e pg_isready -U petcare -d "$DB_NAME" >/dev/null \
  || fail "postgres-e2e did not become ready"

log "Recreating $DB_NAME (test database only)..."
"${COMPOSE[@]}" stop web-e2e >/dev/null 2>&1 || true
"${COMPOSE[@]}" exec -T postgres-e2e psql -U petcare -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
  >/dev/null
"${COMPOSE[@]}" exec -T postgres-e2e dropdb -U petcare --if-exists "$DB_NAME"
"${COMPOSE[@]}" exec -T postgres-e2e createdb -U petcare "$DB_NAME"

log "Building and migrating the isolated backend..."
"${COMPOSE[@]}" build web-e2e
"${COMPOSE[@]}" run --rm --no-deps web-e2e \
  sh -c "alembic upgrade head && python -m scripts.seed"

log "Starting web-e2e on $API_URL..."
"${COMPOSE[@]}" up -d --no-deps web-e2e

for _ in $(seq 1 60); do
  if curl -fsS "$API_URL/api/v1/health/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "$API_URL/api/v1/health/ready" >/dev/null \
  || fail "web-e2e did not become ready at $API_URL"

cd frontend
if [ ! -x node_modules/.bin/playwright ]; then
  fail "frontend dependencies are missing; run 'npm install' in frontend first"
fi

# Keep Vite under this script's control. Playwright's webServer wrapper can lose
# the Vite process during a long Windows run when stdin is detached.
export VITE_API_PROXY="$API_URL"
export E2E_BASE_URL="$WEB_URL"
: > "$VITE_LOG"
log "Starting isolated Vite on $WEB_URL..."
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort \
  >> "$VITE_LOG" 2>&1 &
VITE_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS "$WEB_URL/login" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$VITE_PID" >/dev/null 2>&1; then
    fail "Vite exited before becoming ready; see $VITE_LOG"
  fi
  sleep 1
done
curl -fsS "$WEB_URL/login" >/dev/null || fail "Vite did not become ready at $WEB_URL"

log "Running Playwright against $WEB_URL ..."
node_modules/.bin/playwright test "$@"
