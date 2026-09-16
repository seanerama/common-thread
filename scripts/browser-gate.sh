#!/usr/bin/env bash
set -euo pipefail
export SMOKE_USERNAME="gate_browser_$$" SMOKE_PASSWORD="$(openssl rand -hex 24)"
export COMMON_THREAD_PASSWORD="$SMOKE_PASSWORD"
uv run python manage.py provision_user --username "$SMOKE_USERNAME" --workspace "Browser gate $$"
proof_dir="$(mktemp -d)"
server_pid=''
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$proof_dir"
}
trap cleanup EXIT
start_server() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid"
    wait "$server_pid" || true
  fi
  uv run gunicorn common_thread.wsgi:application --bind 127.0.0.1:18009 --access-logfile /dev/null &
  server_pid=$!
  for attempt in $(seq 1 30); do
    if curl -fsS http://localhost:18009/health/ready/ >/dev/null; then break; fi
    sleep 1
  done
  uv run python scripts/check_health.py http://localhost:18009
}
export PEOPLE_MANAGEMENT_ENABLED=false
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off
export PEOPLE_MANAGEMENT_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management on --record-file "$proof_dir/person.json"
export PEOPLE_MANAGEMENT_ENABLED=false
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --read-file "$proof_dir/person.json"
export PEOPLE_MANAGEMENT_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management on --read-file "$proof_dir/person.json"
