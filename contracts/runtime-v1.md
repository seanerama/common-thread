# Contract: runtime-v1

- **Status:** frozen v1
- **Owner:** application runtime; consumed by deployment and CI

## Exposes

- GET /health/live/ returns 200 application/json {"status":"ok"} when the HTTP
  process can respond. It performs no database query.
- GET /health/ready/ returns 200 {"status":"ready"} only when a database query
  succeeds and all migrations packaged with the running app have been applied;
  otherwise 503 {"status":"not_ready"}. Both endpoints are unauthenticated,
  return Cache-Control: no-store, and expose no host, version, data, or exception.
- The process handles SIGTERM gracefully. Infrastructure bounds graceful shutdown
  to 30 seconds and applies restart policy on unexpected exit.

## Consumes

Environment variables: DATABASE_URL (secret location supplied by operator),
DJANGO_SECRET_KEY (secret), ALLOWED_HOSTS (comma-separated hostnames),
CSRF_TRUSTED_ORIGINS (comma-separated HTTPS origins), PORT (default 8000), and
APP_ENV (development, test, or production). Deployed instances use production
security settings even on a private development host. Missing required production
configuration fails startup. DEBUG is disabled in production; no baked credentials.
Database and TLS provisioning belong to the selected deployment method.

The app is stateless outside PostgreSQL. Schema migration is an explicit one-shot
release action before starting the new app, never a competing startup action in
every worker. Readiness must not falsely claim a successful migration. Logs are
structured JSON on stdout with timestamp, level, event, request_id and outcome;
exclude request bodies, notes, passwords, cookies, and personal contact values.

## Versioning

Frozen v1; additive-only. Exact deployment commands and paths live in the deployment
ADR/access file and the Stage 0 runbook, not this public contract.
