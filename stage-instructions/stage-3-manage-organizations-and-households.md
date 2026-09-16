# Stage 3: Manage organizations and households

- **Type:** feature
- **Depends on:** 2
- **Work item:** https://github.com/seanerama/common-thread/issues/7
- **Release:** v0.2 — Relationship workflow

## Objectives

Create durable organization and household records without forcing people into a hierarchy.

## What to build

Add Organization and Household subtypes sharing Party identity, scoped services,
HTML directory/detail/create/edit/archive/restore routes, and navigation. Preserve
immutable kind, explicit client status, historical access and optimistic versions.
Implement name search and archive filters with 50-row pagination. Reuse validation
without letting typed routes accept another Party kind. Keep new contact-point
management out of scope. Document the default-off flag and restart behavior.

## Interface contracts

- **Exposes:** Stage 3 portion of [relationship-crm-workflow-v1](../contracts/relationship-crm-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md),
  [person-workflow-v1](../contracts/person-workflow-v1.md),
  [person-http-v1](../contracts/person-http-v1.md) and
  [runtime-v1](../contracts/runtime-v1.md), plus preceding merged stages.
- Existing frozen contracts remain unchanged. Read the full new contract for shared
  pagination, reference-error, lock ordering and flag rules before implementation.

## Testing requirements

Prove subtype identity and atomic creation, typed-route isolation, duplicate names,
explicit client status, search/filter/pagination, stale forms and archive/restore.
Test foreign workspaces, revoked users, staff/superusers, CSRF and flag-off direct
requests. Upgrade a database containing existing people, contacts and notes; prove
all records and versions survive. Browser smoke creates, edits, searches, archives
and restores one organization and one household, then reads both after replacement.

Extend the committed operator smoke and browser/container gates, retaining previous
proofs. Use real PostgreSQL, direct request tests and real Chromium, not mocks alone.
Test anonymous/revoked/foreign access, CSRF, feature-off requests before CSRF, and
independent flag combinations. Prove data survives off/on, app replacement and a
restored database. Both AMD64 and emulated ARM64 gates must pass. Deploy only the
exact tested image digest to private mini-hp01 and run the operator smoke; no
production promotion. Record observed evidence separately from this intent spec.

## Acceptance conditions

- [ ] PARTY_DIRECTORY_ENABLED defaults OFF in app/Compose; controls, routes and panels obey it without deleting data.
- [ ] Organization and Household each retain one stable Party ID; no implicit person linking or client promotion.
- [ ] Typed routes, scoped search and archived reads obey the new contract.
- [ ] Concurrent edits conflict without overwriting data; existing Person workflows remain unchanged.
- [ ] Operator-runnable UI-smoke demonstrates the stated workflow against the tested deployed container.
- [ ] Migrations are additive (or absent for Stage 7); prior-stage data and contracts are preserved.
- [ ] Existing and new tests, independent source review, full CI and deployed persistence proof pass.

## Pipeline test: NO
