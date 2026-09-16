# Initial backlog: handoff to Verity Build

Release: [v0.1 — Person foundation](https://github.com/seanerama/common-thread/milestone/1).
Intake decision: split into three dependency-ordered stages. This file is intent,
not mutable progress; use GitHub issues, PRs and Verity stage views for progress.

| Stage | Specification | Work item | Depends on |
| --- | --- | --- | --- |
| 0 | [Deploy the authenticated person walking skeleton](../../stage-instructions/stage-0-deploy-the-authenticated-person-walking-skeleton.md) | [Issue #1](https://github.com/seanerama/common-thread/issues/1) | none |
| 1 | [Manage and find people](../../stage-instructions/stage-1-manage-and-find-people.md) | [Issue #2](https://github.com/seanerama/common-thread/issues/2) | 0 |
| 2 | [Capture and correct personal context](../../stage-instructions/stage-2-capture-and-correct-personal-context.md) | [Issue #3](https://github.com/seanerama/common-thread/issues/3) | 1 |

## Start here

Run `$verity-build` for Stage 0, issue #1. Read its spec, the four architecture
contracts, ADRs 0001–0004, and the walking-skeleton definition before coding.
Stage 0 must pass real CI and deployed smoke before Stage 1 or 2 starts.
Later features must also read the new person-workflow-v1 contract. The private
access file is gitignored; its committed pointer explains how to obtain it.

The [assessment](../../feature-assessments/initial-person-foundation-assessment.md)
contains the mandatory claim/reality table and contract-safety analysis. This intake
adds no architecture changes and does not edit the four existing frozen contracts.
The CLI-generated first stage was normalized to number 0 to preserve the existing
walking-skeleton designation; Verity lists stages 0, 1, 2 correctly.

## Scope boundary

This release proves portable containers, person management and sourced memory.
Organizations, households, affiliations, interactions and commitments remain in
accepted product scope, to be decomposed in the next thin intake after feedback.
External-project API integrations need their own authentication/ownership contracts.
The help agent is deferred by owner choice. Production hosting remains unselected.

## Evidence handoff

Every implementation PR references its stage and linked issue. Builder/Operator
records test commands/results, CI run, artifact digest and deployed smoke as required
by the spec. A green documentation-only pipeline is never application evidence.
