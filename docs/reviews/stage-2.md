# Stage 2 review evidence

PR: https://github.com/seanerama/common-thread/pull/6
Implementation head: 3ee29bebbdf60a86379004a2f3081ce9510f5a57.
CI: https://github.com/seanerama/common-thread/actions/runs/35052271612
Tested merge source: 16ffb4b91b85329c911c424ace05b00a68dc0389.
CI passed 106 PostgreSQL tests plus real browser and both container architecture gates.

| Claim | Checked against | Result |
| --- | --- | --- |
| Default-off, independent notes flag | Settings/Compose, pre-CSRF route guard, direct requests and browser flag combinations | Pass |
| Scoped notes and history | Services, views, workspace composite foreign keys, Person subtype constraint and foreign-resource request tests | Pass |
| Provenance retained | Server-assigned author, atomic old body/source/version snapshot, correcting editor/time, protected deactivated author test | Pass |
| Corrections cannot partially commit | Transaction code, injected failure rollback, stale HTTP409 with retained input | Pass |
| Archive and competing-write safety | Parent-first row locks; PostgreSQL lock-wait tests for competing correction and archive | Pass |
| Text and attribution validation | Escaped templates, forged/duplicate field rejection, maximum Unicode form and unchanged JSON size guard | Pass |
| Additive schema | Migration 0003, prior-stage data preservation tests and unchanged frozen contracts | Pass |
| Portable tested artifacts | Green AMD64 and emulated ARM64 container gates | Pass |
| Deployed persistence and kill switch | Exact tested AMD64 image, HTTPS browser create/correct/history, disabled routes, replacement and restored backup | Pass |

The fresh stage executor implemented the application and tests. The root independently
reviewed actual source and tests, then performed CI and deployment verification.
Review follow-ups added maximum-size URL-encoded Unicode coverage, deactivated-author
retention/protection checks and explicit CI flag configuration. No application or
contract blocker remained. Runtime artifact and deployment evidence are recorded in
STATUS.md and .verity/runtime.json. Both feature defaults remain false; only the
private testing deployment explicitly enables them.
