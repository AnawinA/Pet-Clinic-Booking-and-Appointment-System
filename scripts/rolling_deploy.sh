#!/usr/bin/env bash
# Rolling deploy for the PetCare Compose stack.
#
# Order: build -> tag images -> migrate -> web1 -> web2 -> worker -> nginx.
# Each service must pass its container healthcheck before the next one starts,
# then the script verifies readiness and nginx round-robin across both web nodes.
#
# Usage:
#   scripts/rolling_deploy.sh [--no-build] [--timeout SECONDS]
#
# Environment:
#   BASE_URL        public base URL (default: http://localhost)
#   HEALTH_TIMEOUT  health gate timeout in seconds (default: 120)
#   TAG             override the image tag (default: git short SHA, or GIT_COMMIT)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_IMAGE="petcare-backend"
NGINX_IMAGE="petcare-nginx"
LAST_GOOD_FILE=".last-good-tag"
BASE_URL="${BASE_URL:-http://localhost}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
BUILD=1

usage() {
  sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while (($# > 0)); do
  case "$1" in
    --no-build)
      BUILD=0
      ;;
    --timeout)
      if (($# < 2)); then
        echo "ERROR: --timeout requires a value" >&2
        exit 2
      fi
      HEALTH_TIMEOUT="$2"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! [[ "$HEALTH_TIMEOUT" =~ ^[0-9]+$ ]] || ((HEALTH_TIMEOUT < 1)); then
  echo "ERROR: timeout must be a positive number of seconds" >&2
  exit 2
fi

log() { printf '[deploy] %s\n' "$*"; }
fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
command -v curl >/dev/null 2>&1 || fail "curl is required for the HTTP health gate"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  fail "docker compose is not available"
fi

on_exit() {
  local status=$?
  if ((status != 0)); then
    log "Deploy failed (exit $status). Current services:"
    "${COMPOSE[@]}" ps || true
    log "Recent logs:"
    "${COMPOSE[@]}" logs --tail=40 web1 web2 worker nginx || true
  fi
}
trap on_exit EXIT

resolve_tag() {
  if [ -n "${TAG:-}" ]; then
    printf '%s' "$TAG"
    return
  fi

  local sha=""
  if command -v git >/dev/null 2>&1; then
    sha="$(git rev-parse --short=12 HEAD 2>/dev/null || true)"
  fi
  if [ -z "$sha" ]; then
    sha="${GIT_COMMIT:-}"
    sha="${sha:0:12}"
  fi
  if [ -z "$sha" ]; then
    printf 'manual-%s' "$(date +%Y%m%d-%H%M%S)"
    return
  fi

  if [ -n "$(git status --porcelain --untracked-files=normal 2>/dev/null || true)" ]; then
    printf '%s-dirty-%s' "$sha" "$(date +%Y%m%d-%H%M%S)"
  else
    printf '%s' "$sha"
  fi
}

TAG="$(resolve_tag)"
[ -n "$TAG" ] || fail "could not determine an image tag"
log "Image tag: $TAG"

PREVIOUS_TAG=""
if [ -f "$LAST_GOOD_FILE" ]; then
  PREVIOUS_TAG="$(tr -d '[:space:]' <"$LAST_GOOD_FILE")"
fi

if ((BUILD)); then
  log "Building images..."
  "${COMPOSE[@]}" build
else
  log "Skipping build (--no-build)"
fi

docker image inspect "${BACKEND_IMAGE}:local" >/dev/null 2>&1 \
  || fail "missing ${BACKEND_IMAGE}:local image"
docker image inspect "${NGINX_IMAGE}:local" >/dev/null 2>&1 \
  || fail "missing ${NGINX_IMAGE}:local image"

docker tag "${BACKEND_IMAGE}:local" "${BACKEND_IMAGE}:${TAG}"
docker tag "${NGINX_IMAGE}:local" "${NGINX_IMAGE}:${TAG}"
log "Tagged ${BACKEND_IMAGE}:${TAG} and ${NGINX_IMAGE}:${TAG}"

container_id() {
  "${COMPOSE[@]}" ps -q "$1" 2>/dev/null | head -n 1
}

wait_healthy() {
  local service="$1"
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  local container="" status=""

  log "Waiting for $service to become healthy (timeout ${HEALTH_TIMEOUT}s)..."
  while ((SECONDS < deadline)); do
    container="$(container_id "$service" || true)"
    if [ -n "$container" ]; then
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || echo missing)"
      case "$status" in
        healthy)
          log "$service healthy"
          return 0
          ;;
        exited | dead)
          fail "$service is $status"
          ;;
      esac
    fi
    sleep 2
  done

  fail "$service did not become healthy within ${HEALTH_TIMEOUT}s (last status: ${status:-missing})"
}

wait_ready() {
  local service="$1"
  local deadline=$((SECONDS + HEALTH_TIMEOUT))

  log "Waiting for $service readiness ..."
  until "${COMPOSE[@]}" exec -T "$service" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" \
    >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then
      fail "$service did not become ready within ${HEALTH_TIMEOUT}s"
    fi
    sleep 2
  done
  log "$service ready"
}

wait_http() {
  local url="$1"
  local deadline=$((SECONDS + HEALTH_TIMEOUT))

  log "Waiting for HTTP readiness: $url ..."
  until curl -fsS "$url" >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then
      fail "HTTP check failed within ${HEALTH_TIMEOUT}s: $url"
    fi
    sleep 2
  done
  log "HTTP OK: $url"
}

check_round_robin() {
  local attempt="" seen=""

  for attempt in 1 2 3 4 5; do
    seen="$(
      for _ in $(seq 1 10); do
        curl -fsS -D - -o /dev/null "$BASE_URL/api/v1/health/live" \
          | tr -d '\r' \
          | awk -F': ' 'tolower($1) == "x-instance-id" { print $2 }' || true
      done | sort -u | tr '\n' ' '
    )"

    if printf '%s\n' "$seen" | grep -qw web1 \
      && printf '%s\n' "$seen" | grep -qw web2; then
      log "Round robin OK: ${seen}"
      return 0
    fi
    sleep 2
  done

  fail "nginx did not route to both web1 and web2 (seen: ${seen:-none})"
}

web1_id="$(container_id web1 || true)"
if [ -n "$web1_id" ] \
  && [ "$(docker inspect -f '{{.State.Running}}' "$web1_id" 2>/dev/null || echo false)" = "true" ]; then
  log "Existing web1 found; starting rolling update"
  log "Running database migration..."
  "${COMPOSE[@]}" run --rm migrate

  log "Rolling web1..."
  "${COMPOSE[@]}" up -d --no-deps --force-recreate web1
  wait_healthy web1
  wait_ready web1

  log "Rolling web2..."
  "${COMPOSE[@]}" up -d --no-deps --force-recreate web2
  wait_healthy web2
  wait_ready web2

  log "Updating worker..."
  "${COMPOSE[@]}" up -d --no-deps --force-recreate worker
  wait_healthy worker

  log "Updating nginx..."
  "${COMPOSE[@]}" up -d --no-deps --force-recreate nginx
  wait_healthy nginx
else
  log "No running web1 found; starting the full stack"
  "${COMPOSE[@]}" up -d
  wait_healthy postgres
  wait_healthy web1
  wait_ready web1
  wait_healthy web2
  wait_ready web2
  wait_healthy worker
  wait_healthy nginx
fi

wait_http "$BASE_URL/api/v1/health/ready"
check_round_robin

printf '%s\n' "$TAG" >"$LAST_GOOD_FILE"
log "Deploy succeeded. Recorded ${LAST_GOOD_FILE} = ${TAG}"

if [ -n "$PREVIOUS_TAG" ] && [ "$PREVIOUS_TAG" != "$TAG" ]; then
  log "To roll back to ${PREVIOUS_TAG}:"
  log "  docker tag ${BACKEND_IMAGE}:${PREVIOUS_TAG} ${BACKEND_IMAGE}:local"
  log "  docker tag ${NGINX_IMAGE}:${PREVIOUS_TAG} ${NGINX_IMAGE}:local"
  log "  ${COMPOSE[*]} up -d --no-deps --force-recreate web1 web2 worker nginx"
else
  log "No previous tag recorded yet; future deploys can roll back to this one."
fi
