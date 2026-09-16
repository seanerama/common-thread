# Stage 1: Manage and find people

- **Type:** feature
- **Depends on:** 0
- **Work item:** https://github.com/seanerama/common-thread/issues/2
- **Release:** v0.1 — Person foundation

## Objectives

Let an authenticated user find a person, maintain their name/contact points and
explicit client status, and archive/restore them without losing identity.
Begin only after Stage 0 is CI-green and deployed with recorded persistence proof.

## What to build

Add ContactPoint persistence and person edit/archive/restore with optimistic
versions. Add workspace-scoped paginated name/contact search and archived filters.
Shared email/phone values must not merge records. Render forms and contact details
on the existing person surface. New child references must obey same-workspace
constraints. Use additive migrations and transactional archive/write race handling.
Implement PEOPLE_MANAGEMENT_ENABLED as defined by person-workflow-v1; keep the
Stage 0 workflow usable with this flag off. No new JSON endpoints in this stage.

## Interface contracts

- **Exposes:** contact-management portion of
  [person-workflow-v1](../contracts/person-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md), and unchanged
  [person-http-v1](../contracts/person-http-v1.md).

## Testing requirements

Use PostgreSQL and direct HTTP to prove same-address distinct people, archived
exclusion/restore, pagination/search scoping, forged child IDs, CSRF, membership
revocation, and stale edits with zero partial writes. Exercise concurrent archive
and child creation with transactions. Test feature-off endpoints and unchanged
Stage 0 behavior. Browser smoke edits a fictional person's contact, searches for
it, archives it, then restores it. Verify current-version changes succeed while a
second stale form produces a visible conflict without overwriting the first edit.

## Acceptance conditions

- [ ] Kill-switch PEOPLE_MANAGEMENT_ENABLED defaults OFF; server routes and controls
  obey it; disabling preserves existing data and the Stage 0 workflow.
- [ ] Operator-runnable UI-smoke proves search/edit/archive/restore on deployed UI.
- [ ] Shared/changed contact points preserve stable Party IDs and explicit client status.
- [ ] Workspace isolation and concurrency tests pass through real request handlers.
- [ ] Additive migrations apply to Stage 0 data without loss.
- [ ] Existing suite stays green; CI all-green; deploy uses the tested image digest.

## Pipeline test: NO
