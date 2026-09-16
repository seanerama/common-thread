# Common Thread

A relationship-first CRM that helps professionals remember what matters to people
and follow through on commitments.

Help people remember their clients as people: what matters to them, what has
happened in the relationship, and what they have promised to do next.

Initial use cases are a Realtor, a Pre-Sales Engineer working in networking,
compute, and AI, and an Attorney. These are the first tests of a general-purpose
product, not three separate products or a real-estate system with extra fields.

## Project status

Started September 15, 2026. Product and architecture planning only; no application,
database, integration, or deployment has been implemented.

- [Coding agent handoff — start here](CODING_AGENT_HANDOFF.md)
- [Product brief and first milestone](docs/product-brief.md)
- [Architecture and Kelsey Knows Omaha integration proposal](docs/architecture.md)

The project is independent of `kcrealestate`. Kelsey Knows Omaha is intended to
become an integration consumer once the standalone foundation is useful.

Project identity is locked as `seanerama/common-thread` in `.verity/identity.json`.
The implementation stack and integration contracts remain open.

## Repository hygiene

Run `node .verity/run-gates.cjs` to validate the locked identity, required files,
and local documentation links. CI also scans Git history for secrets with Gitleaks.
These checks cover repository hygiene only; application tests will be added when
implementation begins.
