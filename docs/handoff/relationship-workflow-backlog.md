# Relationship workflow: planner handoff

Release: [v0.2 — Relationship workflow](https://github.com/seanerama/common-thread/milestone/2).
This is the next bounded intake after the person foundation. These files express
intent; use GitHub issues/PRs and Verity state for mutable progress.

| Stage | Specification | Work item | Depends on |
| --- | --- | --- | --- |
| 3 | [Manage organizations and households](../../stage-instructions/stage-3-manage-organizations-and-households.md) | [Issue #7](https://github.com/seanerama/common-thread/issues/7) | 2 |
| 4 | [Connect parties with dated relationships](../../stage-instructions/stage-4-connect-parties-with-dated-relationships.md) | [Issue #8](https://github.com/seanerama/common-thread/issues/8) | 3 |
| 5 | [Record shared interactions and corrections](../../stage-instructions/stage-5-record-shared-interactions-and-corrections.md) | [Issue #9](https://github.com/seanerama/common-thread/issues/9) | 4 |
| 6 | [Track commitments and follow-through](../../stage-instructions/stage-6-track-commitments-and-follow-through.md) | [Issue #10](https://github.com/seanerama/common-thread/issues/10) | 5 |
| 7 | [Unify the person relationship overview](../../stage-instructions/stage-7-unify-the-person-relationship-overview.md) | [Issue #11](https://github.com/seanerama/common-thread/issues/11) | 6 |

## Start here

Run `$verity-build 3` for issue #7. First verify Stage 2 is merged and its tested
private deployment evidence is available. Read Stage 3's instruction, the NEW
[relationship-crm-workflow-v1](../../contracts/relationship-crm-workflow-v1.md), all
five existing frozen contracts, and ADRs 0001–0004 from disk. Each stage gets a fresh
executor, source review, green CI and private tested-image deployment before the next.
The new contract is additive; do not edit old contracts or infer APIs from model names.

The [assessment](../../feature-assessments/relationship-workflow-assessment.md) records
the mandatory source-backed claim/reality table and contract-safety decisions. Source
inspection, not old documentation-only handoff statements, establishes the baseline.
No architecture change, production promotion or implementation is part of this intake.

## Release outcome

A professional can prepare for a conversation using individual context, current
relationships, recent shared conversations and outstanding promises, then record a
conversation and follow through. Validate with fictional Realtor, Pre-Sales Engineer
and Attorney scenarios, without adding industry-specific schema or a sales pipeline.

Stages 4–6 each expose their own usable detail-page panel; Stage 7 composes them into
a compact overview instead of postponing usefulness until a final UI stage. Feature
flags remain independent and default off. Portable images, workspace isolation,
optimistic concurrency, historical references and existing notes remain intact.

## Deliberate deferrals

Organization/household contact management, note-to-interaction source linking,
timezone preferences, recurrence, reminder delivery, imports/deduplication, team
sharing, external integration APIs and the help agent require later intake. Existing
Person contacts are unchanged. Other projects can continue deploying the portable
container; no cross-project database coupling or implicit data sharing is introduced.
