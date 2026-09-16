#!/usr/bin/env bash
set -euo pipefail
export SMOKE_USERNAME="gate_browser_$$" SMOKE_PASSWORD="$(openssl rand -hex 24)"
export COMMON_THREAD_PASSWORD="$SMOKE_PASSWORD"
uv run python manage.py provision_user --username "$SMOKE_USERNAME" --workspace "Browser gate $$"
uv run gunicorn common_thread.wsgi:application --bind 127.0.0.1:18009 --access-logfile /dev/null &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
for attempt in $(seq 1 30); do
  if curl -fsS http://localhost:18009/health/ready/ >/dev/null; then break; fi
  sleep 1
done
uv run python scripts/check_health.py http://localhost:18009
uv run python scripts/browser_smoke.py --base-url http://localhost:18009
