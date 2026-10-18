#!/usr/bin/env bash
# Run local dev services in one terminal. Ctrl+C stops everything.
# Usage: ./dev.sh [--mobile]   (or: make dev MOBILE=1)
#   --mobile  also start the dormant Expo proof of concept in mobile/
set -euo pipefail

WITH_MOBILE="${WITH_MOBILE:-0}"
for arg in "$@"; do
  case "$arg" in
    --mobile) WITH_MOBILE=1 ;;
    -h|--help)
      sed -n '2,4p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

stop_local_apps() {
  # Tear down leftover stacks from prior make dev / ./dev.sh runs.
  local my_pid=$$
  local pid
  for pid in $(pgrep -f '(^|/)(\./)?dev\.sh$|bash \./dev\.sh' 2>/dev/null || true); do
    if [[ "$pid" -ne "$my_pid" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  pkill -f 'manage.py runserver' 2>/dev/null || true
  pkill -f 'celery -A app ' 2>/dev/null || true
  pkill -f 'expo start --tunnel' 2>/dev/null || true
  # Astro/Vite from this repo's frontend (avoid killing unrelated node apps).
  pkill -f "${ROOT}/frontend/app/node_modules/.bin/astro" 2>/dev/null || true
  pkill -f 'astro dev --host' 2>/dev/null || true
  pkill -f 'astro dev$' 2>/dev/null || true

  # Free ports commonly held by stale listeners.
  if command -v fuser >/dev/null 2>&1; then
    fuser -k 8000/tcp 4321/tcp 8081/tcp 2>/dev/null || true
  fi

  sleep 0.3

  # Hard-kill anything that ignored SIGTERM.
  for pid in $(pgrep -f '(^|/)(\./)?dev\.sh$|bash \./dev\.sh' 2>/dev/null || true); do
    if [[ "$pid" -ne "$my_pid" ]]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f 'manage.py runserver' 2>/dev/null || true
  pkill -9 -f 'celery -A app ' 2>/dev/null || true
  pkill -9 -f 'expo start --tunnel' 2>/dev/null || true
  pkill -9 -f "${ROOT}/frontend/app/node_modules/.bin/astro" 2>/dev/null || true
}

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
  stop_local_apps
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Stopping leftover local app processes..."
stop_local_apps

echo "Starting MariaDB + Redis..."
# Recreate Redis so a broken/unpublished 6379 binding cannot block Celery.
docker compose up -d --force-recreate redis
docker compose up -d

echo "Running database migrations..."
(
  cd "$ROOT/backend"
  pipenv run python manage.py migrate --noinput
  # Same as deploy (backend/app-start.sh): PilotFeature rows are defined in code,
  # and gated pages 403 until they exist.
  pipenv run python manage.py sync_pilot_features
)

echo "Starting app services (Ctrl+C to stop all)..."
echo

run api backend pipenv run python manage.py runserver
run celery backend pipenv run celery -A app worker -l info -Q celery,feed,fleets,campaigns,eveonline,market,industry,community
run beat backend pipenv run celery -A app beat -l info
run frontend frontend/app npm run dev
if [[ "$WITH_MOBILE" == "1" ]]; then
  run mobile mobile npm run start:tunnel
fi

wait
