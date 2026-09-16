# Portable container release and recovery

The release unit is an immutable OCI image, plus runtime environment and external
PostgreSQL. No source mounts or host Python are required. The same image supports
other projects' deployments. mini-hp01 is the private testing instance only.

## Runtime and local development

Install Docker Compose, uv 0.10.12, Python 3.13 and Node for local gates. Supply a
real PostgreSQL DATABASE_URL, APP_ENV=test, DJANGO_SECRET_KEY, ALLOWED_HOSTS including
localhost, and CSRF_TRUSTED_ORIGINS=http://localhost:18009. Run `uv sync --frozen`,
`uv run playwright install --with-deps chromium`, then `node .verity/run-gates.cjs`.
Both Docker platforms must be runnable; ARM on amd64 requires QEMU/binfmt configured
by the machine administrator. Missing Docker/browser/PostgreSQL is a failure.
The gate creates and removes its own database volumes and does not touch deployments.

## First deployment and subsequent release

1. Find host/SSH/secret *locations* in the private `.verity/deploy-access.md`.
   Verify disk, Docker, available ports, Tailscale identity and TLS before changing
   the selected test host. Do not touch unrelated workloads.
2. CI publishes the exact two locally tested platform images and a multiarch manifest
   to `ghcr.io/seanerama/common-thread:sha-<CI GITHUB_SHA>`. On PR runs this is the
   tested merge SHA. Inspect the retained `tested-image-digests` artifact and CI URL;
   set APP_IMAGE to the tested platform digest, never rebuild for deployment.
3. Place compose.yml and compose.mini-hp01.yml in a deployment directory, such as
   `$HOME/.local/share/common-thread-test/`. Copy `.env.example` to `app.env` there,
   chmod 600, and replace placeholders. Generate random secrets with a secret store
   or `openssl rand -hex 40`; do not commit environment files. URL-encode a database
   password if it contains URL reserved characters. Include localhost in ALLOWED_HOSTS.
4. Set APP_ENV=production, TRUST_PROXY_HTTPS=true, and the actual tailnet hostname
   in ALLOWED_HOSTS and HTTPS origin with port 8445 in CSRF_TRUSTED_ORIGINS. The app
   listens only on loopback 8010 using the host overlay. Only the trusted local TLS
   proxy may reach it; do not expose the raw app port. Tailscale Serve terminates
   private HTTPS on port 8445 and forwards to http://127.0.0.1:8010. The operator
   configures that listener only after checking it is unused.
5. Use the committed `deploy.sh /absolute/path/to/app.env` from an operator
   checkout with COMPOSE_FILE pointing to the two deployed Compose files. This
   validates immutable digests, backs up before migration, waits for readiness,
   and restores the prior healthy image or stops the initial failed app while
   preserving data. The wrapper uses Bash and Docker Compose, with no host Python runtime. The equivalent manual sequence
   follows for operator diagnosis. In that directory export `COMPOSE_PROJECT_NAME=common-thread-test` and
   `COMPOSE_FILE=compose.yml:compose.mini-hp01.yml`. Use the following commands:

```bash
docker compose --env-file app.env pull
docker compose --env-file app.env up -d --wait db
docker compose --env-file app.env run --rm migrate
docker compose --env-file app.env up -d --wait app
# COMMON_THREAD_PASSWORD is supplied securely in the operator environment.
docker compose --env-file app.env exec -T -e COMMON_THREAD_PASSWORD app \
  python manage.py provision_user --username OPERATOR --workspace 'Private workspace'
```

Provisioning can be rerun; it does not reset existing passwords. No default account
exists. Password changes require an explicit operator action. Keep secrets out of
command arguments, logs and shell tracing.

6. From the operator checkout run the real browser deployed smoke with credentials
   in SMOKE_USERNAME and SMOKE_PASSWORD. Use fictional data and retain the proof
   file privately:

```bash
uv run python scripts/browser_smoke.py --base-url https://HOST.ts.net:8445 --record-file /tmp/ct-person.json
docker compose --env-file app.env up -d --force-recreate --wait app
uv run python scripts/browser_smoke.py --base-url https://HOST.ts.net:8445 --read-file /tmp/ct-person.json
```

Record actual CI URL, tested commit, platform digest, target access method and smoke
outcome in STATUS.md. Never record credentials or personal data. CI tests ARM under
emulation; this is not proof of native ARM deployment.

## Backup and restore proof

Before releases, set DEPLOY_ENV_FILE to the absolute private app.env path and
COMPOSE_FILE/COMPOSE_PROJECT_NAME as above, then run from the operator checkout:

```bash
scripts/backup.sh /secure/backups/common-thread.dump
scripts/restore-check.sh /secure/backups/common-thread.dump
```

Backup files contain private data: restrict access, encrypt off-host retention and
apply the operator's retention policy. Restore-check creates an isolated temporary
DB, restores with errors fatal, verifies migrations and drops only that DB. CI also
starts the app against a restored DB and reads the same fictional person via browser.
Production restore is manual: stop the app, restore to a new database, update
DATABASE_URL, run readiness/browser proof, and retain the old database until approved.
Never overwrite or delete the active database as a restore test.

## Failure and rollback

Migrations are one-shot release actions, not worker startup hooks. Back up before
migration. Use additive migrations so an earlier healthy image can run against the
new schema. For a subsequent failed release set APP_IMAGE back to the recorded prior
healthy digest, rerun `up -d --wait app` and the browser read smoke. Never reverse
destructive schema changes automatically. On the first deployment there is no prior
healthy release: `docker compose --env-file app.env stop app`, retain DB/diagnostics,
fix the failure, and retest. Never use `down --volumes` on the deployed instance.

Readiness returns 503 when DB is unavailable or migrations are outstanding; liveness
remains 200 when the HTTP process responds. CI proves both cases. SIGTERM gets up to
30 seconds (Gunicorn graceful timeout 25); Compose restarts unexpected exits.

## Authentication operations

Sessions expire absolutely after 12 hours. Login failures are limited per casefolded
username (5 failures) and direct REMOTE_ADDR source (20 failures) within 900 seconds;
the next attempt returns 429 with Retry-After. Behind the trusted tailnet proxy,
users may share a source bucket. Forwarded client IP headers are not trusted for
rate-limit identity. Use `python manage.py changepassword USERNAME` interactively
inside the app container for an explicit operator password reset.

## Stage 1 people management acceptance and kill switch

`PEOPLE_MANAGEMENT_ENABLED` defaults to `false` in the application and Compose.
Set it explicitly to `true` in the private runtime environment to enable person
editing, contact management, search, archive and restore. Apply environment changes
with `docker compose --env-file app.env up -d --force-recreate --wait app`.
Changing the file alone does not update running processes. No image rebuild is needed.

With operator smoke credentials exported, run against the deployed URL:

```bash
uv run python scripts/browser_smoke.py --base-url https://HOST.ts.net:8445 --people-management on --record-file /tmp/ct-managed-person.json
```

This creates a fictional person and contact, updates them, checks two stale forms
return visible conflicts without overwriting accepted changes, searches by contact,
archives/restores the same person, and archives a second contact. Retain the private
proof file for subsequent
restart and backup/restore verification with `--read-file` and
`--people-management on`; this read mode does not repeat the edits.

To disable Stage 1, set the flag to `false` and recreate the app. Run the same
read command with `--people-management off` to verify the original person detail
remains readable, controls disappear, and edit routes return 404. The default smoke
mode is `off`, preserving the Stage 0 create/read/reload proof. Reenable the flag,
recreate, and use `--people-management on --read-file /tmp/ct-managed-person.json`
to verify the contact persisted through the toggle. Disabling the flag does not
remove data. Local browser gates and both amd64/arm64 container gates execute this
off/on/off/on sequence; container gates also read the managed contact after restore.

## Stage 2 context-note acceptance

`CONTEXT_NOTES_ENABLED` defaults to `false` and operates independently of
`PEOPLE_MANAGEMENT_ENABLED`. Set it to `true` in the external environment file and
recreate the app to enable sourced notes, corrections and history. Apply the new
migration from the exact tested image before starting it. Setting the flag back to
`false` and recreating the app hides note panels and rejects all note routes while
retaining current notes, original authors and correction history in PostgreSQL.

With operator smoke credentials supplied through `SMOKE_USERNAME` and
`SMOKE_PASSWORD`, run the browser against the deployed artifact:

```sh
uv run python scripts/browser_smoke.py --base-url "$COMMON_THREAD_URL" \
  --people-management on --context-notes on --record-file /tmp/context-proof.json
```

The smoke creates fictional sourced context, corrects it, rejects a stale edit and
reads the prior content/source with author/editor provenance. After app replacement,
run the same command with `--read-file /tmp/context-proof.json` instead of
`--record-file`. Repeat with `--context-notes off` after disabling/recreating, then
reenable/recreate and reread to prove data survived the kill switch. Set
`--people-management off` when that separate feature is disabled. The browser gate
runs this restart sequence; both architecture container gates additionally read
current notes and history after image-container replacement and database restore.
