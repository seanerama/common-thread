# Stage 6: Track commitments and follow-through

- **Type:** feature
- **Depends on:** 5
- **Work item:** https://github.com/seanerama/common-thread/issues/10
- **Release:** v0.2 — Relationship workflow

## Objectives

Make explicit promises visible, actionable and retained after completion.

## What to build

Add Commitment and unique CommitmentPerson links with same-workspace and Person
subtype constraints. Implement create/detail/edit/complete/reopen, the paginated
open/completed work list with due filters, and person panels through explicit links.
Require description, explicit owing/receiving parties and at least one linked person;
allow due date and scoped source interaction. Enforce server attribution/status/time,
optimistic versions and atomic link changes. Allow completion of historical commitments
whose parties were archived. Preserve/hide existing interaction references when the
interaction feature is off; block newly assigning such references until it is on.
No recurring tasks, reminders, email, notification service or professional pipelines.

## Interface contracts

- **Exposes:** Stage 6 portion of [relationship-crm-workflow-v1](../contracts/relationship-crm-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md),
  [person-workflow-v1](../contracts/person-workflow-v1.md),
  [person-http-v1](../contracts/person-http-v1.md) and
  [runtime-v1](../contracts/runtime-v1.md), plus preceding merged stages.
- Existing frozen contracts remain unchanged. Read the full new contract for shared
  pagination, reference-error, lock ordering and flag rules before implementation.

## Testing requirements

Prove required Person links (organizations are invalid for that set), foreign IDs,
source validation, shared visibility and explicit debtor/recipient semantics. Test
complete/reopen server times, invalid repeated transitions, stale concurrent state
changes, new-link/archive races and atomic invalid edits. Cover UTC due-day boundaries,
null dates and stable pagination. Browser smoke creates a promise after a shared
conversation, checks both linked people and work list, completes and reopens it.

Extend the committed operator smoke and browser/container gates, retaining previous
proofs. Use real PostgreSQL, direct request tests and real Chromium, not mocks alone.
Test anonymous/revoked/foreign access, CSRF, feature-off requests before CSRF, and
independent flag combinations. Prove data survives off/on, app replacement and a
restored database. Both AMD64 and emulated ARM64 gates must pass. Deploy only the
exact tested image digest to private mini-hp01 and run the operator smoke; no
production promotion. Record observed evidence separately from this intent spec.

## Acceptance conditions

- [ ] COMMITMENTS_ENABLED defaults OFF in app/Compose; controls, routes and panels obey it without deleting data.
- [ ] Every commitment has explicit owing/receiving parties and at least one linked Person.
- [ ] Complete/reopen is versioned, uses server timestamps and preserves the record.
- [ ] Person panels use CommitmentPerson rather than inference from relationships/client status.
- [ ] Work list filters, optional source references and independent flags obey the contract.
- [ ] Operator-runnable UI-smoke demonstrates the stated workflow against the tested deployed container.
- [ ] Migrations are additive (or absent for Stage 7); prior-stage data and contracts are preserved.
- [ ] Existing and new tests, independent source review, full CI and deployed persistence proof pass.

## Pipeline test: NO
