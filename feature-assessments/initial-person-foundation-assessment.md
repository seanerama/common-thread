# Initial person foundation assessment

- **Request:** owner invokes Verity Plan after accepted architecture, portable
  containers, private mini-hp01 testing target, and explicit help-agent deferral.
- **Decision:** SPLIT into stages 0 → 1 → 2; release v0.1 — Person foundation.
- **Baseline inspected:** bb16142, documentation/governance only.

## Claim / reality verification

| Claim or assumption | Verified reality | Planning implication |
| --- | --- | --- |
| Identity is locked | .verity/identity.json names Common Thread / seanerama/common-thread | Preserve identity |
| Django/PostgreSQL exist | No pyproject, Python source, migrations or app tests; ADRs only | Stage 0 creates them |
| Container deployment exists | No Dockerfile/Compose/deploy script; ADR 0004 specifies requirements | Build and test actual containers in Stage 0 |
| CI is green | GitHub run 35043837915 succeeded on bootstrap; ci.yml and gates.json only run hygiene/secret checks | Does not prove application or later commits |
| Core contracts exist | Four frozen Markdown contracts in contracts/ | Treat as requirements, not implemented APIs |
| Target is ready | Access file supplies catalog locations/proposed paths; no live-host verification in this intake | Builder must inspect before provisioning |
| Existing backlog exists | verity stage list and GitHub issue list were empty | New initial intake; no duplicate work items |
| Optional AI is wanted | docs/features.md records explicit deferral | No helper-bot stages |
| Other projects can integrate now | ADR 0004 promises portability; no machine auth or integration implementation | Prove container portability now, specify external API/auth later |

## Impact and contract safety

Stage 0 implements the existing design. Stages 1/2 add HTML workflows and
operational flags through NEW person-workflow-v1. Existing contracts are not edited;
JSON create/read remain unchanged when feature flags are off. No architectural
decision changes and no additional deployment target are introduced by this plan.
Database changes, concurrency checks and every access path need real integration
tests. Feature flags gate functionality, never authorization.

## Why this split

Stage 0 includes the minimum persistent authenticated UI and deployment proof;
splitting its infrastructure tasks into independently complete feature stages would
weaken the prerequisite. Stage 1 adds contact lifecycle, and Stage 2 adds sourced
memory with history. These provide a small useful foundation without prematurely
planning the full CRM. Both feature stages stay blocked by deployed Stage 0.

## Deferred intake

Organizations/households, dated relationships, shared interactions and commitments
remain accepted product direction. Plan their next thin batch after foundation
feedback. The first full CRM milestone is NOT finished by these three stages.
Integration with Kelsey Knows Omaha/other projects needs machine authentication,
scopes and ownership contracts before implementation. Help agent, public signup,
team sharing, industry engines, and production promotion remain deferred.

## Traceability and numbering

See docs/handoff/initial-backlog.md for linked GitHub issues and stage files.
The CLI starts at 1 with no explicit number option; its initial generated chore
was normalized to stage-0 before creating the dependent stages. This preserves the
architecture's Stage 0 meaning. Specs express intent; GitHub/Verity derive progress.
