# Stage 4: Connect parties with dated relationships

- **Type:** feature
- **Depends on:** 3
- **Work item:** https://github.com/seanerama/common-thread/issues/8
- **Release:** v0.2 — Relationship workflow

## Objectives

Explain how people are connected to each other, organizations and households, retaining prior affiliations.

## What to build

Add Relationship records with same-workspace endpoint constraints, scoped creation,
correction and close workflows, active-party selectors and paginated panels on both
endpoints. Preserve immutable endpoints, direction, kind, role and effective dates.
Close an affiliation without deleting it; a new employer or household is a separate
row. Distinguish current/future/ended relationships. Coordinate sorted Party locks
with existing archive operations. Directory flag off must not disable this feature's
scoped selectors; show labels without links to disabled directory routes.

## Interface contracts

- **Exposes:** Stage 4 portion of [relationship-crm-workflow-v1](../contracts/relationship-crm-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md),
  [person-workflow-v1](../contracts/person-workflow-v1.md),
  [person-http-v1](../contracts/person-http-v1.md) and
  [runtime-v1](../contracts/runtime-v1.md), plus preceding merged stages.
- Existing frozen contracts remain unchanged. Read the full new contract for shared
  pagination, reference-error, lock ordering and flag rules before implementation.

## Testing requirements

Prove cross-workspace FK rejection, unequal endpoints, kind/date validation,
future/current/ended classification including inclusive boundary dates, same pair
with distinct historical periods, and explicit direction. Use real PostgreSQL lock
waits to exercise create versus archive in both orders and stale correction/close.
Browser smoke connects a fictional person to a company and household, closes an
employment and creates another, then observes both endpoints and preserved history.

Extend the committed operator smoke and browser/container gates, retaining previous
proofs. Use real PostgreSQL, direct request tests and real Chromium, not mocks alone.
Test anonymous/revoked/foreign access, CSRF, feature-off requests before CSRF, and
independent flag combinations. Prove data survives off/on, app replacement and a
restored database. Both AMD64 and emulated ARM64 gates must pass. Deploy only the
exact tested image digest to private mini-hp01 and run the operator smoke; no
production promotion. Record observed evidence separately from this intent spec.

## Acceptance conditions

- [ ] RELATIONSHIPS_ENABLED defaults OFF in app/Compose; controls, routes and panels obey it without deleting data.
- [ ] A person can hold multiple independent affiliations without an enforced hierarchy.
- [ ] Closing/changing affiliations preserves old rows and never changes Party identity or client status.
- [ ] Direct references and new-link/archive races cannot create cross-workspace or invalid links.
- [ ] Operator-runnable UI-smoke demonstrates the stated workflow against the tested deployed container.
- [ ] Migrations are additive (or absent for Stage 7); prior-stage data and contracts are preserved.
- [ ] Existing and new tests, independent source review, full CI and deployed persistence proof pass.

## Pipeline test: NO
