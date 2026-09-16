#!/usr/bin/env bash
set -euo pipefail
: "${DEPLOY_ENV_FILE:?Path to private Compose environment file}"
: "${1:?Backup filename}"
restore_db="restore_check_$(date +%s)_$$"
dc() { docker compose --env-file "$DEPLOY_ENV_FILE" "$@"; }
cleanup() { dc exec -T db dropdb -U common_thread --if-exists "$restore_db"; }
trap cleanup EXIT
dc exec -T db createdb -U common_thread "$restore_db"
dc exec -T db pg_restore -U common_thread -d "$restore_db" --exit-on-error < "$1"
# Full restore must include applied migrations and application tables.
dc exec -T db psql -U common_thread -d "$restore_db" -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM django_migrations;'
echo "Restore succeeded in disposable database $restore_db"
