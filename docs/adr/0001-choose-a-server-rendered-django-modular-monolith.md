# 0001. Choose a server-rendered Django modular monolith

- **Status:** Accepted
- **Date:** 2026-09-16

## Context

Common Thread needs forms, relationship history, shared interactions, commitments,
and reliable authorization before it needs a rich client or industry extensions.
There is no existing application stack to preserve. The Verity stack-and-topology
guide recommends server rendering, reproducible dependencies, and a modular monolith.

## Decision

Use Python 3.13, Django 5.2 LTS, Django templates, plain CSS, and small progressive
JavaScript enhancements only where needed. Use Django ORM/migrations and psycopg 3.
Use Gunicorn for the application process. Resolve current compatible security patch
versions and commit an exact dependency lock and container base digests in Stage 0.
Use uv for the Python lock, Ruff for lint/format, pytest with pytest-django for
integration tests, and Playwright's Python integration for real browser checks.

Deploy one application image, `ghcr.io/seanerama/common-thread`, plus PostgreSQL as
infrastructure. Modules: accounts/workspaces, contacts, relationships, interactions,
context, and commitments. HTML views and versioned JSON adapters call the same
workspace-authorized application services. Modules share one transactional database;
no module may bypass another's authorization rules through direct view-level ORM use.
No separate SPA, queue, cache, search server, or LLM service in the first milestone.
Portable containers are required; ADR 0004 selects mini-hp01 for testing and
keeps production hosting independent of the application runtime.

## Alternatives considered

- Django templates follows the guide and supplies forms, migrations, sessions, and
  authentication within one framework. Workspace authorization is still our work.
- TypeScript with Next.js and PostgreSQL is viable, especially for a highly interactive
  client, but adds frontend/client-state decisions unnecessary for this first workflow.
- FastAPI plus a frontend is viable for an API-first team, but requires assembling
  more of the authentication, forms, and administration stack.
- Multiple services add deployment and transaction boundaries without a scaling need.

## Consequences

A small operational surface and ordinary form submissions make the first workflow
straightforward to test. Rich offline or mobile UX would need additional design.
Server-rendered UI is a product implementation choice, not a restriction on future
integration APIs. Stage 0 must pin actual dependencies, not floating release ranges.

## Sources

[Django support policy](https://www.djangoproject.com/download/),
[Django PostgreSQL support](https://docs.djangoproject.com/en/5.2/ref/databases/).
