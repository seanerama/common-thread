# Common Thread

A relationship-first CRM that helps professionals remember what matters to people
and follow through on commitments.

Help people remember their clients as people: what matters to them, what has
happened in the relationship, and what they have promised to do next.

Initial use cases are a Realtor, a Pre-Sales Engineer working in networking,
compute, and AI, and an Attorney. These are the first tests of a general-purpose
product, not three separate products or a real-estate system with extra fields.

## Project status

Started September 15, 2026. The Stage 0 implementation supplies operator-provisioned
private workspaces, login, and persistent person creation/read in Django and PostgreSQL.
See [STATUS](STATUS.md) for observed CI and deployment evidence.

- [Coding agent handoff — start here](CODING_AGENT_HANDOFF.md)
- [Product brief and first milestone](docs/product-brief.md)
- [Architecture and Kelsey Knows Omaha integration proposal](docs/architecture.md)

The project is independent of `kcrealestate`. Kelsey Knows Omaha is intended to
become an integration consumer once the standalone foundation is useful.

Project identity is locked as `seanerama/common-thread` in `.verity/identity.json`.
The design selects Django and PostgreSQL in portable containers, with mini-hp01
as the testing target. Other projects can deploy an instance or integrate through
future versioned APIs; production hosting remains open.
See the [Architect handoff](docs/architect-handoff.md) for ADRs, frozen core
contracts, and the walking-skeleton definition. External integration contracts
remain deferred.

## Development and verification

Use Python 3.13, uv, Docker Compose, and real PostgreSQL 17. Install with
`uv sync --frozen`, provide `DATABASE_URL` and `DJANGO_SECRET_KEY` in your shell,
and run `uv run python manage.py migrate`. Provision a private owner with
`COMMON_THREAD_PASSWORD` supplied securely to
`uv run python manage.py provision_user --username <name> --workspace <name>`.
Existing passwords and memberships are preserved on repeated provisioning.
Run `uv run python manage.py runserver` for localhost development.

Install the browser with `uv run playwright install --with-deps chromium`.
`node .verity/run-gates.cjs` runs hygiene, locked installation, lint/format,
Django and migration checks, PostgreSQL integration, real browser, and amd64/arm64
container persistence/restore gates. Docker and browser dependencies are required;
missing gates fail. CI additionally scans Git history with Gitleaks.

See [the deployment runbook](docs/runbooks/deployment.md) for portable containers,
private testing-host deployment, operator smoke, backup, restore, and rollback.

The [initial backlog](docs/handoff/initial-backlog.md) links the stage specifications
and GitHub work items for Verity Build, starting with Stage 0.
