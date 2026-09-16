# Stage 7: Unify the person relationship overview

- **Type:** feature
- **Depends on:** 6
- **Work item:** https://github.com/seanerama/common-thread/issues/11
- **Release:** v0.2 — Relationship workflow

## Objectives

Prepare for a conversation and record its follow-through from a coherent person page.

## What to build

Add the bounded preparation summary and clear navigation to existing detail sections:
current relationships, five recent interactions and five open commitments, with counts
and links to all paginated records. Improve labels, empty states, keyboard access and
archived-person presentation while retaining contact/note sections. Reuse owning
services and mutation routes; do not add a parallel write API, aggregate store or
schema migration. Respect every section flag and retain the stage-6 layout when the
overview flag is off. Provide operator-runnable fictional end-to-end scenarios for
Realtor, Pre-Sales Engineer and Attorney; no industry-specific schema or workflow.

## Interface contracts

- **Exposes:** Stage 7 portion of [relationship-crm-workflow-v1](../contracts/relationship-crm-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md),
  [person-workflow-v1](../contracts/person-workflow-v1.md),
  [person-http-v1](../contracts/person-http-v1.md) and
  [runtime-v1](../contracts/runtime-v1.md), plus preceding merged stages.
- Existing frozen contracts remain unchanged. Read the full new contract for shared
  pagination, reference-error, lock ordering and flag rules before implementation.

## Testing requirements

Verify ordering, count/preview consistency, bounded queries (no per-row lookup growth),
empty and more-than-one-page datasets, escaping, foreign records, archived people and
independent flags. Browser scenarios cover a household's individual priorities and
shared conversation; technical/business contacts with changed employment; an attorney's
promised update. In every scenario create a commitment, complete it and verify history.
Prove feature-off restores the prior layout without hiding enabled underlying workflows.

Extend the committed operator smoke and browser/container gates, retaining previous
proofs. Use real PostgreSQL, direct request tests and real Chromium, not mocks alone.
Test anonymous/revoked/foreign access, CSRF, feature-off requests before CSRF, and
independent flag combinations. Prove data survives off/on, app replacement and a
restored database. Both AMD64 and emulated ARM64 gates must pass. Deploy only the
exact tested image digest to private mini-hp01 and run the operator smoke; no
production promotion. Record observed evidence separately from this intent spec.

## Acceptance conditions

- [ ] PERSON_OVERVIEW_ENABLED defaults OFF in app/Compose; controls, routes and panels obey it without deleting data.
- [ ] Each fictional profession scenario supports conversation preparation and follow-through without industry-specific modules.
- [ ] Summary, full sections and owning record pages agree; truncation is visible and full history reachable.
- [ ] Feature-off preserves the stage-6 experience and all data; disabled underlying panels stay hidden.
- [ ] No new persistence or duplicated mutation logic is introduced.
- [ ] Operator-runnable UI-smoke demonstrates the stated workflow against the tested deployed container.
- [ ] Migrations are additive (or absent for Stage 7); prior-stage data and contracts are preserved.
- [ ] Existing and new tests, independent source review, full CI and deployed persistence proof pass.

## Pipeline test: NO
