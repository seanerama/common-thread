# Stage 0: Deploy the authenticated person walking skeleton

- **Type:** chore
- **Depends on:** none
- **Work item:** https://github.com/seanerama/common-thread/issues/1
- **Release:** v0.1 — Person foundation

## Objectives

Prove the real application, authentication, database, CI and container deployment
spine. This is the architecture's Stage 0, not an assertion that a CRM already
exists. It blocks every feature stage until the deployed proof succeeds.

## What to build

Implement every deliverable and exit proof in
[the walking-skeleton definition](../docs/walking-skeleton.md), under ADRs 0001–0004.
Create the Django/Python lock, custom user, workspace/membership and Party/Person
migrations, login/logout, HTML list/create/detail and JSON create/read endpoints.
Use real PostgreSQL locally and in CI, explicit authorization services, CSRF,
server sessions, membership revocation and tested account/source login throttling.
Operator provisioning must be repeatable without overwriting existing passwords
or creating duplicate workspaces. Use fictional fixtures and no default credentials.

Provide Dockerfile, .dockerignore, portable Compose and separate testing-host overlay,
example environment configuration, readiness/liveness, one-shot migrations, and
release/backup/restore runbooks. Build amd64 and arm64 images, run as non-root, retain
PostgreSQL data outside the app container, and test replacement without source mounts.
Resolve exact supported dependency patches during implementation, not from stale
version guesses in this spec. Update the shared gates definition and CI setup with
real lint, migration, PostgreSQL, browser and container checks.

Deploy the tested platform digest to the selected mini-hp01 target. Obtain private
access details through [.verity/deploy-access.README.md](../.verity/deploy-access.README.md).
Inspect target capabilities, free ports and TLS before provisioning isolated app
resources; proposed paths are not evidence of existing services. Never use this
stage to deploy to production or modify unrelated applications.

## Interface contracts

- **Exposes:** person-http-v1 and runtime-v1.
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md),
  [person-http-v1](../contracts/person-http-v1.md),
  [runtime-v1](../contracts/runtime-v1.md).
- Do not implement later domain modules or change frozen contract behavior.

## Testing requirements

All seven proof groups in docs/walking-skeleton.md are mandatory. Include direct
HTTP checks for unsupported media, malformed/oversized payloads, forbidden input
fields, identical missing/foreign-object behavior and exact session/error semantics.
Use a real browser for login/create/reload and a deployed smoke asset runnable by
the Operator. Prove restart persistence with a fresh HTTP read, DB restore into a
disposable database, and truthful failure/readiness behavior. Report emulated ARM
evidence explicitly. Tests must fail on missing dependencies or skipped gates.

## Acceptance conditions

- [ ] Clear exit-state: authenticated fictional person creation/read works in a
  deployed portable container and survives replacement; two workspaces stay isolated.
- [ ] All walking-skeleton proof groups pass, including both image architectures.
- [ ] Same tested artifact is deployed; CI URL, commit and platform digest identify it.
- [ ] Operator can rerun setup/smoke and backup/restore using the documented commands.
- [ ] Existing hygiene/secret scan and all new gates are green; no fake test stubs.
- [ ] Builder/Operator records observed deployment evidence in STATUS.md. On initial
  failure stop the app and retain DB/diagnostics; do not invent a prior release.

This foundational chore has no feature dark-launch flag; private deployment plus
stopping/reverting the application is its operational exit path. UI-smoke remains
mandatory. Later feature stages require their own default-off flags.

## Pipeline test: NO
