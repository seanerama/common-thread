# 0002. Choose PostgreSQL and workspace-scoped access

- **Status:** Accepted
- **Date:** 2026-09-16

## Context

One interaction can involve several people, affiliations change over time, and
archiving must preserve history. A general-purpose product must keep independent
professionals' records separate. No collaboration or record-level sharing requirement
has been accepted. The contracts-first guide recommends defining stable seams early.

## Decision

Use PostgreSQL 17 for local development, CI, and deployment; pin the current security
patch image/digest in Stage 0. Use explicit relational tables, UUID primary keys,
foreign keys, transactions, and committed Django migrations. Never use email as an
identity key. Use a Party supertype with person/organization/household subtypes so
relationships can reference typed entities with real foreign keys.

All CRM records belong to a workspace. Start with one private workspace per user;
users are provisioned by the operator, with no public signup, invitations, shared
workspaces, or private-note ACLs in milestone one. Create a custom Django user model
before the first migration. Keep application users separate from CRM people.
An active owner membership grants all CRM reads/writes within that workspace.
Check membership on every request and scope both object lookup and related IDs.
Do not treat knowledge of a UUID or network access as authorization. Staff/superuser
status must not silently bypass workspace checks in product routes.

Use server-side Django sessions and CSRF protections. No browser JWT or integration
credential exists in v1. Require TLS for deployed login; localhost HTTP is development
only. Operator password reset is sufficient initially; email delivery is deferred.
Log operation/request IDs and outcomes, excluding names, notes, credentials, and
request bodies. All initial development and deployment data is fictional.

Enforce same-workspace relationships using composite foreign keys to unique
(workspace_id, id) pairs, with SQL migrations where the ORM cannot express these.
Mutations use transactions and optimistic versions; no silent last-write-wins.
Archive rather than delete through the product. Snapshot prior note/interaction
content into workspace-scoped revision rows with actor and timestamp on correction.
This is editing history, not a compliance or immutable-audit claim.

## Alternatives considered

- SQLite simplifies setup but would not exercise PostgreSQL constraints/concurrency
  in development and CI. It is not the supported persistence backend.
- A document database makes shared references and transactional updates less direct.
- A single global address book leaks data between independent users.
- Full team roles, record-level ACLs, and database row-level security can be added with
  a specific sharing requirement; they are not substitutes for tested service scoping.
- JWT and external SSO add token/lifecycle work unnecessary for the same-origin app.

## Consequences

PostgreSQL is required for integration tests. Cross-workspace access, removed
membership, forged related IDs, and concurrent edits require direct endpoint tests.
All members of a future shared workspace would see its records unless a NEW access
contract defines narrower visibility; sharing cannot be silently enabled under v1.
Database administrators remain trusted operators.

## Sources

[PostgreSQL lifecycle](https://www.postgresql.org/support/versioning/),
[Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/).
