#!/usr/bin/env bash
# Release only an already-tested immutable image. No host provisioning or rebuild.
set -euo pipefail
: "${1:?Usage: deploy.sh /absolute/path/to/app.env}"
export DEPLOY_ENV_FILE="$1"
test -f "$DEPLOY_ENV_FILE"
: "${COMPOSE_FILE:=compose.yml:compose.mini-hp01.yml}"
: "${COMPOSE_PROJECT_NAME:=common-thread-test}"
export COMPOSE_FILE COMPOSE_PROJECT_NAME
: "${RELEASE_DATA_DIR:=$(dirname "$DEPLOY_ENV_FILE")/releases}"
umask 077
mkdir -p "$RELEASE_DATA_DIR"
release_dir="$(mktemp -d "$RELEASE_DATA_DIR/release-XXXXXXXX")"
dc() { docker compose --env-file "$DEPLOY_ENV_FILE" "$@"; }
# Inspect only image names; never print the resolved configuration or secrets.
image="$(dc config --environment | sed -n 's/^APP_IMAGE=//p')"
if [[ ! "$image" =~ @sha256:[0-9a-f]{64}$ ]]; then
  echo 'APP_IMAGE must identify the tested image by immutable sha256 digest.' >&2
  exit 2
fi
previous=""
previous_container="$(dc ps -q app)"
if [[ -n "$previous_container" ]] && [[ "$(docker inspect "$previous_container" --format '{{.State.Health.Status}}')" == healthy ]]; then
  previous="$(docker inspect "$previous_container" --format '{{.Config.Image}}')"
fi
printf '%s\n' "$image" > "$release_dir/requested-image.txt"
printf '%s\n' "$previous" > "$release_dir/previous-image.txt"
recover() {
  status=$?
  trap - ERR
  dc logs --no-color > "$release_dir/failure.log" 2>&1 || true
  if [[ -n "$previous" ]]; then
    echo 'Release failed; restoring the previously healthy application image.' >&2
    export APP_IMAGE="$previous"
    if ! dc up -d --no-deps --force-recreate --wait app; then
      dc stop app || true
      echo 'Rollback failed; application stopped and database preserved.' >&2
    fi
  else
    dc stop app || true
    echo 'Initial release failed; application stopped and database preserved.' >&2
  fi
  echo "Diagnostics retained in $release_dir" >&2
  exit "$status"
}
trap recover ERR
dc pull
dc up -d --wait db
# Always back up before schema changes, including an empty first database.
dc exec -T db pg_dump -U common_thread -d common_thread -Fc > "$release_dir/pre-migration.dump"
test -s "$release_dir/pre-migration.dump"
dc run --rm migrate
dc up -d --wait app
container="$(dc ps -q app)"
test "$(docker inspect "$container" --format '{{.State.Health.Status}}')" = healthy
printf '%s\n' "$image" > "$release_dir/healthy-image.txt"
echo "Application ready; run the deployed browser smoke. Release evidence: $release_dir"
