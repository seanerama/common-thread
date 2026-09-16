# Status & Handoff

> Runtime/ops truth (framework-spec §4.6). Generated from `.verity/runtime.json`
> by the Release/Deploy Operator. Secret LOCATIONS only — never values.

**Live version:** stage-1 / b4a1f0dbb271
**Deployed at:** 2026-09-16T03:26:34.662365+00:00
**Rollback from:** ghcr.io/seanerama/common-thread@sha256:5cb4fa031f0c42ad8935c5827ac7fa47fd68f50667f822617e38b1e1cc3ce2fa

## Environments
- **testing:** {"target":"mini-hp01 (private Tailscale; URL in deploy-access.md)","image":"ghcr.io/seanerama/common-thread@sha256:70ca4d6893c45b57edfca05c7c735d95dfaad4a5bb2519cc127eea2ce5c25bbe","tested_commit":"b4a1f0dbb271fa10ff3a7cd5e4ddcad73488f4c7","ci":"https://github.com/seanerama/common-thread/actions/runs/35051070459","verified":"HTTPS browser people management workflow; flag off/on preservation; container replacement read; disposable backup restore passed","flags":{"PEOPLE_MANAGEMENT_ENABLED":true}}

## Secret locations (names + on-disk locations only, never values)
- DATABASE_URL, DJANGO_SECRET_KEY and fictional smoke credentials: private host app.env mapped in .verity/deploy-access.md

## Coordination notes
- Testing deployment only; production target not selected.
- Both image architectures passed CI; ARM was emulated, not deployed to native ARM hardware.
- This runtime record describes the tested image, not a rebuild of the documentation commit.
