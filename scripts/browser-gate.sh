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
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=false RELATIONSHIPS_ENABLED=false INTERACTIONS_ENABLED=false COMMITMENTS_ENABLED=false PERSON_OVERVIEW_ENABLED=false
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --context-notes off --party-directory off --relationships off --interactions off --commitments off
export PEOPLE_MANAGEMENT_ENABLED=true CONTEXT_NOTES_ENABLED=true PARTY_DIRECTORY_ENABLED=true RELATIONSHIPS_ENABLED=true INTERACTIONS_ENABLED=true COMMITMENTS_ENABLED=true PERSON_OVERVIEW_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management on --context-notes on --party-directory on --relationships on --interactions on --commitments on --person-overview on --record-file "$proof_dir/person.json"
export PERSON_OVERVIEW_ENABLED=false
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management on --context-notes on --party-directory on --relationships on --interactions on --commitments on --person-overview off --read-file "$proof_dir/person.json"
export PERSON_OVERVIEW_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management on --context-notes on --party-directory on --relationships on --interactions on --commitments on --person-overview on --read-file "$proof_dir/person.json"
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=false RELATIONSHIPS_ENABLED=false INTERACTIONS_ENABLED=false COMMITMENTS_ENABLED=false PERSON_OVERVIEW_ENABLED=false
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --context-notes off --party-directory off --relationships off --interactions off --commitments off --read-file "$proof_dir/person.json"
export INTERACTIONS_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --context-notes off --party-directory off --relationships off --interactions on --commitments off --read-file "$proof_dir/person.json"
export INTERACTIONS_ENABLED=false
export COMMITMENTS_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --context-notes off --party-directory off --relationships off --interactions off --commitments on --read-file "$proof_dir/person.json"
export COMMITMENTS_ENABLED=false
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=false RELATIONSHIPS_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --context-notes off --party-directory off --relationships on --interactions off --commitments off --read-file "$proof_dir/person.json"
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=true RELATIONSHIPS_ENABLED=false
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management off --context-notes off --party-directory on --relationships off --interactions off --commitments off --read-file "$proof_dir/person.json"
export PEOPLE_MANAGEMENT_ENABLED=true CONTEXT_NOTES_ENABLED=true PARTY_DIRECTORY_ENABLED=true RELATIONSHIPS_ENABLED=true INTERACTIONS_ENABLED=true COMMITMENTS_ENABLED=true PERSON_OVERVIEW_ENABLED=true
start_server
uv run python scripts/browser_smoke.py --base-url http://localhost:18009 --people-management on --context-notes on --party-directory on --relationships on --interactions on --commitments on --person-overview on --read-file "$proof_dir/person.json"
