# Common Thread: Architect handoff to Verity Plan

Status: architecture complete and ready for Verity Plan. mini-hp01 is selected for
testing; a portable container is required. Production hosting remains a later choice.
No drop-in features were accepted; the optional help agent is excluded from this plan.

## Design map

- [Product brief](product-brief.md): accepted direction and first milestone.
- [Architecture](architecture.md): topology and integration ownership.
- [Stack ADR](adr/0001-choose-a-server-rendered-django-modular-monolith.md).
- [Storage/access ADR](adr/0002-choose-postgresql-and-workspace-scoped-access.md).
- [Contracts/skeleton ADR](adr/0003-choose-versioned-adapters-and-a-thin-walking-skeleton.md).
- [Container/deployment ADR](adr/0004-choose-a-portable-container-and-mini-hp01-testing-deployment.md).
- [Core semantics](../contracts/crm-core-v1.md), [session/auth](../contracts/session-auth-v1.md),
  [Person HTTP](../contracts/person-http-v1.md), [runtime](../contracts/runtime-v1.md).
- [Drop-in features](features.md) and [Stage 0 definition](walking-skeleton.md).
- [Deployment access pointer](../.verity/deploy-access.README.md).

## Thin backlog direction

The Planner owns final stage IDs and acceptance details. Suggested dependency order:

1. Stage 0: authenticated create/read person, real PostgreSQL, green CI, deployment.
2. People/contact editing, search, archive/restore, optimistic conflicts, and context
   correction history; make the person page the primary product surface.
3. Organizations/households and dated relationships with historical affiliations.
4. Multi-party interactions stored once, revision history, consistent participant views.
5. Commitments, explicit owed-by/owed-to, linked people, due dates, completion/history.
6. Acceptance scenarios across Realtor, Pre-Sales Engineer, and Attorney; verify
   all direct HTTP authorization paths, restart persistence, and browser workflows.

Keep scopes thin and runnable. Add contracts for new wire operations before the
corresponding implementation. Add real feature-specific gates rather than duplicating
implementation assertions. Do not implement integration, AI, email, sales pipelines,
team sharing, or profession-specific workflow engines in this milestone.

## Architectural assumptions

Private workspace per provisioned user; no public signup; browser-first online app;
fictional data for initial deployment; one application plus PostgreSQL. These are
recorded architectural defaults, not claims that the owner requested each detail.
Revisit consequential contrary requirements explicitly through new decisions.
