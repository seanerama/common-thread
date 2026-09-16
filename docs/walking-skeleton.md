# Stage 0: authenticated, persistent person creation

Status: defined, not implemented. Testing target: mini-hp01 using portable containers.
This stage blocks all feature stages. Its scope is smaller than the product brief's
first complete person workflow.

## User-visible slice

An operator provisions a user and private workspace without a default password.
The user logs in, opens People, creates a fictional person, and sees the persisted
name on a detail page. Refreshing and restarting the application preserves it.
A different workspace cannot list, read, or modify the record, including through
raw HTTP requests. The JSON create/read seam calls the same application service.

## Deliverables

- Python/Django project with exact dependency lock, Ruff, pytest-django, Playwright,
  PostgreSQL configuration, custom user model, and initial migrations for accounts,
  workspaces/membership, Party/Person. Other domain tables follow feature stages.
- Server-rendered login, list, create, and detail UI with accessible labels, visible
  validation, keyboard navigation, and form submission that works without JavaScript.
- Frozen Person JSON endpoints, session/CSRF behavior, and runtime health endpoints.
- Reproducible container build and local Compose PostgreSQL setup; committed example
  configuration contains placeholders only. No SQLite test substitution.
- Portable Compose definition, mini-hp01 host overlay, and deployment runbook per ADR 0004.
  Build and deploy the same tested commit/image; do not deploy an untested rebuild.
- Operator provisioning, backup/restore, restart, release migration, rollback, and
  secret-location instructions. No public signup or default demo password.

## Required proof

1. Install strictly from lock; format/lint; Django system checks; detect uncommitted
   model changes; apply migrations from an empty PostgreSQL database.
2. Integration tests prove successful authenticated creation/read, invalid input
   without partial writes, unauthenticated rejection, CSRF rejection, workspace
   isolation (including forged IDs), deactivated membership, and login rate limiting.
3. Playwright logs in via the actual form, creates a fictional person, reloads its
   detail page, and verifies persisted data. Use a real application server and DB.
4. Build linux/amd64 and linux/arm64 images and smoke-test both (record emulation
   where used). Run the application as non-root without source bind mounts or host
   Python. Verify readiness and create/read persistence after replacing the app
   container while retaining the database. Change runtime configuration without
   rebuilding the image. A fresh GET must hit the replacement container.
5. CI retains secret scan/hygiene and executes these real gates through the committed
   .verity/gates.json after its dependency/database setup. Missing/skipped application
   checks cannot count as green. The current hygiene-only gate is insufficient.
6. Deploy the tested artifact to the selected target, with TLS and session settings;
   run create/read/restart smoke against fictional data. Record commit, CI URL,
   artifact digest, deployment URL/access method, and observed outcome in STATUS.md.
7. Prove a database backup can restore into a disposable database and demonstrate
   rollback to a prior healthy artifact where one exists. On initial deployment,
   failure stops the app and preserves the DB/diagnostics; never fabricate a prior
   release. Additive migrations support app rollback; destructive rollback is manual.

## Exit and handoff

Stage 0 is done only after all applicable proofs pass, including target deployment.
The architecture phase does not implement or claim these checks. Stage 0's Planner
may decompose internal tasks but cannot allow later feature stages to bypass its exit.
