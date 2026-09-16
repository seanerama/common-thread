# Stage 0 review evidence

PR: https://github.com/seanerama/common-thread/pull/4
Implementation head: 2b6ebc6. CI: https://github.com/seanerama/common-thread/actions/runs/35049627689
Tested merge source: 28d757718e0f834cd9f07e4994ba4da1f999a06a.

| Claim | Checked against | Result |
| --- | --- | --- |
| Workspace isolation and revocation | services, middleware, direct-request tests including foreign/superuser requests | Pass |
| Session/CSRF/error contracts | source plus 57 CI integration tests; independent reproduction of oversized form, malformed multipart, missing CSRF and anonymous requests | Pass |
| Real user workflow | Chromium login/create/reload in CI and deployed HTTPS instance | Pass |
| Portable images | AMD64 and emulated ARM64 container gates; non-root, no source mounts, immutable published manifests | Pass |
| Persistent and recoverable data | CI replacement/restored-DB browser reads; host replacement read and disposable restore | Pass |
| Frozen contracts and scope | diff against main; no contract or identity changes, no future feature implementation | Pass |
| Release artifact | deployed AMD64 digest exactly matches tested-image-digests artifact | Pass |

Independent source review requested changes for oversized form requests returning
HTML400. The executor added pre-CSRF auth/size/media guards and regression tests;
the reviewer reproduced correct 401/413/415/403 responses and cleared the blocker.
CI also exposed a Docker classic-store architecture collision, corrected by selecting
platform-specific database manifests from the pinned index. Both final gates passed.

The root reviewer did not implement application code. Runtime evidence is in STATUS.md
and .verity/runtime.json; credential locations are supplied privately. Stage 0 has no
feature flag because it is the foundational chore; the deployment is private and can
be stopped while preserving its database. Later stages remain default-off features.
