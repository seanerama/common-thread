# Relationship workflow assessment

- **Request:** owner invokes verity-plan after stages 0–2, accepting planning of the
  proposed organization/household → relationships → interactions → commitments →
  unified person-page sequence.
- **Decision:** SPLIT into five bounded feature stages 3 → 4 → 5 → 6 → 7.
- **Release:** v0.2 — Relationship workflow.
- **Baseline inspected:** 15600f7977e579ed778b6900e67e52c09ae1959a on main.
- **Scope:** planning only; no implementation, deployment or mutable runtime updates.

## Mandatory claim / reality verification

| Claim | Actual source checked | Reality and implication |
| --- | --- | --- |
| A working foundation exists | crm/models.py, services.py, views.py; common_thread/urls.py; tests/ | People, contacts and sourced notes exist; extend rather than scaffold again |
| All Party kinds are implemented | Party.kind choices versus sole Person subtype, create_person/get_person and URL routes | Organization/household names in an enum are not implemented workflows; stage 3 supplies subtypes and UI |
| Shared relationships already exist | No Relationship, Interaction, InteractionParticipant, Commitment or CommitmentPerson models/routes | Stages 4–6 require additive persistence and services, not UI-only changes |
| Attribution/history can be reused | ContextNoteRevision, update_context_note, protected User FKs | Reuse conventions, but shared interaction history must also snapshot participant sets and occurred_at |
| Notes can already link to interactions | note_no_interaction_yet SQL constraint; form allowlist; person-workflow-v1 | They cannot; retain null and explicitly defer linkage rather than silently dropping a guard |
| People are user accounts | User is separate from Party/Person; Membership is one-to-one to user and workspace | Keep explicit CRM debtor/recipient identities; do not create team sharing or infer current user's person |
| Concurrency helpers support arbitrary shared records | locked_person uses one Party lock; notes/contact writes lock parent first | Add deterministic multi-Party lock ordering without breaking existing archive semantics |
| Person page already aggregates everything | templates/person_detail.html contains contacts and notes only | Add owned panels in stages 4–6, then bounded preparation summary in stage 7 |
| Containers and validation are real | Dockerfile, compose.yml, .verity/gates.json, browser/container scripts; latest main CI success for inspected SHA | Extend the existing gates; keep exact-image deployment and restore proofs |
| An unplanned backlog might already exist | verity stage list showed only 0–2; GitHub issues 1–3 closed | Allocate 3–7; do not duplicate foundation work |
| Historical handoff prose is current | docs/architecture.md and CODING_AGENT_HANDOFF.md still contain initial documentation-only statements | Treat those as historical design context; source and runtime evidence establish current reality |
| Help agent/integrations are wanted now | docs/features.md and explicit owner deferral | Keep them out of this intake |

## Contract safety and architecture

Add NEW relationship-crm-workflow-v1 for HTML workflows and flag semantics. All five
existing frozen contracts remain byte-for-byte unchanged. crm-core-v1 already declares
these entities; ADRs 0001–0004 already select the shared transactional modular monolith,
Party subtypes, workspace constraints, provenance and portable containers. This intake
implements that architecture; no architecture-affecting decision or new ADR/approval
gate is needed. New schema is additive. Existing Person JSON, contact/note forms,
authentication, source_interaction_id=null for notes, and health behavior stay unchanged.

The substantive risks are shared-record correction atomicity, participant replacement,
foreign references, archive races and flags accidentally exposing another feature.
The new contract specifies reference-error behavior, link uniqueness, composite workspace
FKs, parent lock order, bounded lists, historical access and independent kill switches.
Tests must use real PostgreSQL and real browser flows; a mock-only check is insufficient.

## Why this split and boundary

Each stage has one deployable user outcome. Organization/household contact points are
deferred to keep stage 3 thin. Stage 4 adds dated connections. Stage 5 adds a shared
conversation and correction history. Stage 6 adds explicit promises and a work list.
Stage 7 integrates those existing workflows into preparation/follow-through scenarios;
it adds no dashboard engine, materialized store or notification service.

Dates use explicit UTC display/interpretation initially; local timezone preferences
are deferred. Private workspace ownership remains unchanged. No public signup, sharing,
imports, deduplication, professional engines, external APIs, background reminders,
marketing, automatic messages, note source linking or help agent is in this release.
Other projects retain portable deployment support; integration remains a separate intake.
Production promotion is not part of these stages.

## Handoff

See [the next backlog](../docs/handoff/relationship-workflow-backlog.md) for specs,
dependencies and GitHub work items. Start Stage 3 after the builder verifies Stage 2's
merged/deployed evidence. Complete each stage's source review, green CI and tested-image
private deployment before proceeding to the next. Specs describe intent, not progress.
