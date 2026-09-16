# 0004. Choose a portable container and mini-hp01 testing deployment

- **Status:** Accepted
- **Date:** 2026-09-16

## Context

The owner confirmed that Common Thread will be used in other projects, must run
in a container, and may use the recommended mini-hp01 target for testing. The
Verity topology guide recommends minimizing service and deployment surfaces.
The global deployment catalog provides this host; it is not a production commitment.

## Decision

The deployment unit is an OCI application image at
`ghcr.io/seanerama/common-thread`, with PostgreSQL supplied separately. Publish
linux/amd64 and linux/arm64 variants from the same source and dependency lock,
with immutable release tags and recorded platform digests. Build and smoke-test
both variants in Stage 0; emulated ARM testing is acceptable when identified as such.
Do not claim native ARM deployment verification until it has actually occurred.

Use Docker Compose for a reproducible application-plus-database testing deployment
on mini-hp01, reached over the owner's Tailscale network. The catalog method is
mini-hp01-systemd; a host systemd unit can manage the Compose lifecycle if needed,
while the application itself always runs in its container. Use a separate Compose
project and database volume; never reuse another project's database or service.
Keep deployment access and credential locations in the gitignored access file.
Provisioning, TLS ingress, capacity and port checks are Stage 0 work, not completed
in this architecture phase. No host changes or deployment are performed here.

The container must run as a non-root user, include its runtime and static assets,
and require no source bind mount, host Python, developer home directory, or Tailscale
client inside the image. Runtime configuration follows runtime-v1. Secrets are
injected at runtime; no credentials, database files, or environment-specific URLs
are baked into image layers. PostgreSQL is reachable over a private container network
or an explicitly configured external database endpoint; no public database port.

Persist application data in PostgreSQL outside the application container. Use named
volumes for the test database, documented backup/restore, health checks, and an
explicit migration command executed from the same release image. Supply an ordinary
portable Compose definition and a separate host overlay for ingress/environment
wiring. TLS terminates outside the app; only the selected trusted proxy can supply
forwarded protocol information. Prefer private tailnet HTTPS for the testing target.
The app needs no host-specific rebuild when its hostname or deployment method changes.

Other projects may deploy their own Common Thread instance or integrate with an
existing instance through versioned APIs. Domain code remains profession-neutral.
Direct database coupling, copying internal modules into consuming projects, and
implicit sharing of customer data are not integration contracts. Existing browser
session endpoints serve the first slice; machine authentication, scopes, external-ID
mapping and ownership must be specified before a project's first API integration.
Container portability is required in Stage 0; integration implementation remains a
later stage. The production host is intentionally unselected.

## Alternatives considered

- Host-installed Python/systemd application: simple but violates the explicit
  portable-container requirement and couples releases to host runtime state.
- Coolify or another container host: a valid later destination for the same images;
  selecting it for production is unnecessary to prove the testing deployment.
- Cloudflare Workers: a distinct execution model, unnecessary for this container app.
- In-process embeddable library: not selected; it would couple consumers to this
  framework and lifecycle. Revisit if a consumer requires that deployment model.

## Consequences

Stage 0 must prove an actual image runs, persists data across container replacement,
and supports both target architectures. mini-hp01 is one deployment configuration,
not part of the product runtime. Consumers need explicit authorization and API
contracts even if their containers share a physical server.
