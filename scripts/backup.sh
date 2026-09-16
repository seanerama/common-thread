#!/usr/bin/env bash
set -euo pipefail
# Caller supplies COMPOSE_FILE, COMPOSE_PROJECT_NAME and --env-file via environment.
: "${DEPLOY_ENV_FILE:?Path to private Compose environment file}"
: "${1:?Destination backup filename}"
umask 077
docker compose --env-file "$DEPLOY_ENV_FILE" exec -T db pg_dump -U common_thread -d common_thread -Fc > "$1"
test -s "$1"
echo 'Backup created; verify by restoring into a disposable database.'
