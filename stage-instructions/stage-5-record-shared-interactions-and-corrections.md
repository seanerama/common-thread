# Stage 5: Record shared interactions and corrections

- **Type:** feature
- **Depends on:** 4
- **Work item:** https://github.com/seanerama/common-thread/issues/9
- **Release:** v0.2 — Relationship workflow

## Objectives

Record one conversation involving several parties and correct it consistently across their histories.

## What to build

Add Interaction, unique InteractionParticipant links and workspace-scoped correction
revisions. Implement create/detail/edit/history forms, active selectors and paginated
participant detail-page history. Snapshot old text, occurred_at, participant set,
version and provenance atomically. Keep one interaction shared by all participants;
editing or removing participants must not leave copies or partial updates. Retain
historical archived references. Keep ContextNote source_interaction_id null and its
existing SQL constraint/forms unchanged. Do not add uploads, ingestion or messaging.

## Interface contracts

- **Exposes:** Stage 5 portion of [relationship-crm-workflow-v1](../contracts/relationship-crm-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md),
  [person-workflow-v1](../contracts/person-workflow-v1.md),
  [person-http-v1](../contracts/person-http-v1.md) and
  [runtime-v1](../contracts/runtime-v1.md), plus preceding merged stages.
- Existing frozen contracts remain unchanged. Read the full new contract for shared
  pagination, reference-error, lock ordering and flag rules before implementation.

## Testing requirements

Prove nonempty unique participants, offset-aware times, maximum Unicode form payload,
escaped text and forged attribution/reference rejection. Test correction rollback via
injected failure, concurrent edits, participant replacement versus archive, historical
participant access isolation and retained deactivated authors. Browser smoke creates
one conversation for two people, corrects it, checks both pages and prior history,
then changes participants and verifies current versus historical membership.

Extend the committed operator smoke and browser/container gates, retaining previous
proofs. Use real PostgreSQL, direct request tests and real Chromium, not mocks alone.
Test anonymous/revoked/foreign access, CSRF, feature-off requests before CSRF, and
independent flag combinations. Prove data survives off/on, app replacement and a
restored database. Both AMD64 and emulated ARM64 gates must pass. Deploy only the
exact tested image digest to private mini-hp01 and run the operator smoke; no
production promotion. Record observed evidence separately from this intent spec.

## Acceptance conditions

- [ ] INTERACTIONS_ENABLED defaults OFF in app/Compose; controls, routes and panels obey it without deleting data.
- [ ] One interaction ID appears for every current participant; no per-person copies exist.
- [ ] Correction and participant replacement preserve complete prior versions atomically.
- [ ] Stale/invalid writes and archive races produce no partial interaction, revision or link changes.
- [ ] ContextNote forms, history and null source-link constraint remain unchanged.
- [ ] Operator-runnable UI-smoke demonstrates the stated workflow against the tested deployed container.
- [ ] Migrations are additive (or absent for Stage 7); prior-stage data and contracts are preserved.
- [ ] Existing and new tests, independent source review, full CI and deployed persistence proof pass.

## Pipeline test: NO
