# Stage 2: Capture and correct personal context

- **Type:** feature
- **Depends on:** 1
- **Work item:** https://github.com/seanerama/common-thread/issues/3
- **Release:** v0.1 — Person foundation

## Objectives

Make the person page useful for remembering what matters: authored context with a
source and correction history. This is not the full relationship/commitment milestone.

## What to build

Add ContextNote and workspace-scoped revision storage with same-workspace parent
constraints. Add create/edit/history forms and current-note display on the person
page. Preserve prior content/source, authorship, editor and edit time atomically
on correction. Use expected_version to prevent lost updates. Escape user text.
source_interaction_id remains null until a later interaction stage is specified.
Reject forged attribution/parent links, prohibit edits on archived parents, and
keep existing notes/history readable when the parent is archived and the flag is on.
Implement CONTEXT_NOTES_ENABLED (default off) per person-workflow-v1. No LLM,
inferred facts, integration endpoints, notes-sharing rules or automatic messaging.

## Interface contracts

- **Exposes:** context portion of [person-workflow-v1](../contracts/person-workflow-v1.md).
- **Consumes:** [crm-core-v1](../contracts/crm-core-v1.md),
  [session-auth-v1](../contracts/session-auth-v1.md), and Stage 1 person workflows.
- Existing four architecture contracts remain unchanged.

## Testing requirements

PostgreSQL tests must prove correction atomicity, original author retention,
revision access isolation, concurrent conflict/no partial history, required source,
escaped text and archived-parent behavior. Direct requests exercise unauthenticated,
CSRF, foreign-workspace and feature-off paths. Browser smoke creates sourced context,
corrects it and inspects the prior version. Reopen after app restart to prove storage.

## Acceptance conditions

- [ ] Kill-switch CONTEXT_NOTES_ENABLED defaults OFF and hides/blocks all new surfaces
  without deleting data or altering the original person/JSON workflow.
- [ ] UI-smoke demonstrates create/correct/history using fictional personal context.
- [ ] Corrections preserve prior versions and provenance; conflicts never lose edits.
- [ ] Author, current record and history remain workspace-authorized on direct requests.
- [ ] Additive migrations preserve Stage 1 data; existing suite stays green; CI all-green.
- [ ] Operator can run smoke against the deployed, tested container artifact.

## Pipeline test: NO
