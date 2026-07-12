#!/usr/bin/env bash
# Run local dev services in one terminal. Ctrl+C stops everything.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

run() {
  local name=$1
  shift
  (
    cd "$1" && shift
    exec "$@"
  ) 2>&1 | while IFS= read -r line; do
    printf '[%s] %s\n' "$name" "$line"
  done &
  PIDS+=("$!")
}

PIDS=()

cleanup() {
  echo
  echo "Stopping dev services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting MariaDB + Redis..."
docker compose up -d

echo "Starting app services (Ctrl+C to stop all)..."
echo

run api backend pipenv run python manage.py runserver
run celery backend pipenv run celery -A app worker -l info -Q celery,eveonline,market
run beat backend pipenv run celery -A app beat -l info
run frontend frontend/app npm run dev
run mobile mobile npm run start:tunnel

wait
