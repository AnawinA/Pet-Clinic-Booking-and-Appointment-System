#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

echo "1/4 Waiting for /api/v1/health/ready ..."
ready=0
for _ in $(seq 1 60); do
  if curl -fsS "$BASE_URL/api/v1/health/ready" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" != "1" ]; then
  echo "FAIL: readiness endpoint did not become healthy within 60s"
  curl -s "$BASE_URL/api/v1/health/ready" || true
  exit 1
fi
curl -fsS "$BASE_URL/api/v1/health/ready"
echo

echo "2/4 Checking nginx round-robin across web1/web2 ..."
instances=""
for _ in $(seq 1 10); do
  id=$(curl -fsS -D - -o /dev/null "$BASE_URL/api/v1/health/live" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-instance-id"{print $2}')
  instances="$instances $id"
done
echo "instances:$instances"
echo "$instances" | tr ' ' '\n' | sort -u | grep -qx web1
echo "$instances" | tr ' ' '\n' | sort -u | grep -qx web2

echo "3/4 Smoke test: login + availability ..."
TOKEN=$(curl -fsS -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner1@petcare.local","password":"Petcare123!"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
DAY=$(python -c 'import datetime; print((datetime.date.today()+datetime.timedelta(days=1)).isoformat())')
curl -fsS "$BASE_URL/api/v1/availability?date=$DAY" -H "Authorization: Bearer $TOKEN" >/dev/null
echo "login + availability OK"

echo "4/4 Checking Prometheus targets ..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:9090/api/v1/targets" \
    | python -c 'import json,sys; data=json.load(sys.stdin); targets=data["data"]["activeTargets"]; assert targets; assert all(t["health"]=="up" for t in targets)' 2>/dev/null; then
    echo "all Prometheus targets are up"
    exit 0
  fi
  sleep 1
done
echo "FAIL: Prometheus targets are not all up within 60s"
exit 1
