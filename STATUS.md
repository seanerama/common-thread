# Status & Handoff

> Runtime/ops truth (framework-spec §4.6). Generated from `.verity/runtime.json`
> by the Release/Deploy Operator. Secret LOCATIONS only — never values.

**Live version:** stage-2 / 16ffb4b91b85
**Deployed at:** 2026-09-16T03:44:47.453764+00:00
**Rollback from:** ghcr.io/seanerama/common-thread@sha256:70ca4d6893c45b57edfca05c7c735d95dfaad4a5bb2519cc127eea2ce5c25bbe

## Environments
- **testing:** {"target":"mini-hp01 (private Tailscale; URL in deploy-access.md)","image":"ghcr.io/seanerama/common-thread@sha256:eac93d7804998c35ba009c6163f3607f11963fef225906597e02d6aaaacb4dc7","tested_commit":"16ffb4b91b85329c911c424ace05b00a68dc0389","ci":"https://github.com/seanerama/common-thread/actions/runs/35052271612","verified":"HTTPS browser people/contact and sourced-note create/correct/history; independent flag cycles; container replacement read; disposable backup restore passed","flags":{"PEOPLE_MANAGEMENT_ENABLED":true,"CONTEXT_NOTES_ENABLED":true}}

## Secret locations (names + on-disk locations only, never values)
- DATABASE_URL, DJANGO_SECRET_KEY and fictional smoke credentials: private host app.env mapped in .verity/deploy-access.md

## Coordination notes
- Testing deployment only; production target not selected.
- Both image architectures passed CI; ARM was emulated, not deployed to native ARM hardware.
- This runtime record describes the tested image, not a rebuild of the documentation commit.
