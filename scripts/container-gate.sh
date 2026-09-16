#!/usr/bin/env bash
set -euo pipefail
platform="${1:?Specify amd64 or arm64}"
case "$platform" in amd64|arm64) ;; *) exit 2;; esac
export COMPOSE_PROJECT_NAME="ct-gate-${platform}-$$"
export COMPOSE_FILE=compose.yml:compose.test.yml
export APP_IMAGE="common-thread:ci-${GITHUB_SHA:-local}-${platform}"
export POSTGRES_PASSWORD="$(openssl rand -hex 24)"
export DATABASE_URL="postgresql://common_thread:${POSTGRES_PASSWORD}@db:5432/common_thread"
export DJANGO_SECRET_KEY="$(openssl rand -hex 40)"
export APP_ENV=test ALLOWED_HOSTS=localhost,127.0.0.1
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=false RELATIONSHIPS_ENABLED=false INTERACTIONS_ENABLED=false
export CSRF_TRUSTED_ORIGINS=http://localhost:18010
export TEST_HTTP_PORT="${TEST_HTTP_PORT:-18010}"
export SMOKE_USERNAME=smoke SMOKE_PASSWORD="$(openssl rand -hex 24)"
export COMMON_THREAD_PASSWORD="$SMOKE_PASSWORD"
export DOCKER_DEFAULT_PLATFORM="linux/$platform"
# Classic Docker stores cannot associate two architectures with the same index
# reference. Resolve its pinned platform manifest without changing shared images.
postgres_index="$(docker compose -f compose.yml config --images db)"
postgres_digest="$(docker buildx imagetools inspect --raw "$postgres_index" | node -e '
const fs = require("node:fs");
const index = JSON.parse(fs.readFileSync(0, "utf8"));
const matches = index.manifests.filter(m => m.platform.os === "linux" && m.platform.architecture === process.argv[1]);
if (matches.length !== 1 || !/^sha256:[a-f0-9]{64}$/.test(matches[0].digest)) {
  throw new Error("Pinned PostgreSQL index must contain exactly one requested platform");
}
process.stdout.write(matches[0].digest);
' "$platform")"
export TEST_POSTGRES_IMAGE="${postgres_index%%@*}@${postgres_digest}"
proof_dir="$(mktemp -d)"
cleanup() {
  docker compose logs --no-color > "$proof_dir/containers.log" 2>&1 || true
  docker compose down --volumes --remove-orphans
  echo "Container diagnostics: $proof_dir"
}
trap cleanup EXIT
docker buildx build --platform "linux/$platform" --load -t "$APP_IMAGE" .
test "$(docker image inspect "$APP_IMAGE" --format '{{.Architecture}}')" = "$platform"
test "$(docker run --rm --entrypoint id "$APP_IMAGE" -u)" != 0
docker compose pull --policy always db
test "$(docker image inspect "$TEST_POSTGRES_IMAGE" --format '{{.Architecture}}')" = "$platform"
docker compose up -d --wait db
# No migration: readiness must report failure while liveness remains available.
docker compose up -d app
for attempt in $(seq 1 60); do
  if curl -fsS "http://localhost:$TEST_HTTP_PORT/health/live/" >/dev/null; then break; fi
  sleep 1
done
uv run python scripts/check_health.py "http://localhost:$TEST_HTTP_PORT" --ready 503
docker compose run --rm migrate
docker compose up -d --wait app
docker compose exec -T -e COMMON_THREAD_PASSWORD app python manage.py provision_user --username smoke --workspace Smoke
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --relationships off --interactions off --record-file "$proof_dir/person.json"
# Both architectures exercise enabled workflows and the runtime kill switch.
export PEOPLE_MANAGEMENT_ENABLED=true CONTEXT_NOTES_ENABLED=true PARTY_DIRECTORY_ENABLED=true RELATIONSHIPS_ENABLED=true INTERACTIONS_ENABLED=true
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management on --context-notes on --party-directory on --relationships on --interactions on --record-file "$proof_dir/managed-person.json"
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=false RELATIONSHIPS_ENABLED=false INTERACTIONS_ENABLED=false
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management off --context-notes off --party-directory off --relationships off --interactions off --read-file "$proof_dir/managed-person.json"
export INTERACTIONS_ENABLED=true
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management off --context-notes off --party-directory off --relationships off --interactions on --read-file "$proof_dir/managed-person.json"
export INTERACTIONS_ENABLED=false
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=false RELATIONSHIPS_ENABLED=true
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management off --context-notes off --party-directory off --relationships on --read-file "$proof_dir/managed-person.json"
export PEOPLE_MANAGEMENT_ENABLED=false CONTEXT_NOTES_ENABLED=false PARTY_DIRECTORY_ENABLED=true RELATIONSHIPS_ENABLED=false
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management off --context-notes off --party-directory on --relationships off --read-file "$proof_dir/managed-person.json"
export PEOPLE_MANAGEMENT_ENABLED=true CONTEXT_NOTES_ENABLED=true PARTY_DIRECTORY_ENABLED=true RELATIONSHIPS_ENABLED=true INTERACTIONS_ENABLED=true
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management on --context-notes on --party-directory on --relationships on --interactions on --read-file "$proof_dir/managed-person.json"
old_id="$(docker compose ps -q app)"
# Runtime-only configuration change, same image.
export ALLOWED_HOSTS=localhost,127.0.0.1,changed.example.invalid
docker compose up -d --force-recreate --wait app
test "$old_id" != "$(docker compose ps -q app)"
test -z "$(docker inspect "$(docker compose ps -q app)" --format '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}{{end}}{{end}}')"
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management on --context-notes on --party-directory on --relationships on --interactions on --read-file "$proof_dir/managed-person.json"
docker compose exec -T db pg_dump -U common_thread -d common_thread -Fc > "$proof_dir/backup.dump"
docker compose exec -T db createdb -U common_thread restore_check
docker compose exec -T db pg_restore -U common_thread -d restore_check --exit-on-error < "$proof_dir/backup.dump"
export DATABASE_URL="postgresql://common_thread:${POSTGRES_PASSWORD}@db:5432/restore_check"
docker compose up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url "http://localhost:$TEST_HTTP_PORT" --people-management on --context-notes on --party-directory on --relationships on --interactions on --read-file "$proof_dir/managed-person.json"
docker compose stop db
uv run python scripts/check_health.py "http://localhost:$TEST_HTTP_PORT" --ready 503
docker compose stop app
# Required production config must fail startup without exposing secrets.
if docker run --rm -e APP_ENV=production "$APP_IMAGE" python manage.py check > "$proof_dir/missing-config.log" 2>&1; then
  echo 'ERROR: production started without configuration'; exit 1
fi
echo "Container $platform proof passed (ARM may be emulated; see runner architecture)."
