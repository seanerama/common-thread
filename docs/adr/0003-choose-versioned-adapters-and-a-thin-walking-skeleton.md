# 0003. Choose versioned adapters and a thin walking skeleton

- **Status:** Accepted
- **Date:** 2026-09-16

## Context

The product's first milestone is larger than the infrastructure proof. The Verity
contracts-first guide recommends frozen seams, and the topology guide requires a
real deployed slice before feature stages. Existing CI proves documentation hygiene
and secret scanning only; its bootstrap run 35043837915 succeeded on 2026-09-16 UTC.

## Decision

Freeze logical CRM semantics, session authorization, two Person JSON endpoints, and
runtime health behavior in contracts/. Do not freeze an unneeded external API or
expose the database to integrations. Breaking changes create a new contract.

Stage 0 implements login, create person, read person, PostgreSQL persistence,
workspace isolation, and a tested deployment. The full person page with context,
relationships, shared interactions, and commitments follows Stage 0. Keep one
application deployment; defer Kelsey Knows Omaha integration and AI assistance.

## Alternatives considered

- Implement the entire first milestone before deployment: too much unvalidated work
  accumulates above an unproven deployment/database/authentication foundation.
- Health endpoint alone: deployable but does not prove user input or persistence.
- Freeze every future REST operation now: prematurely fixes unused API choices.
- Call HTML views from later integrations: couples consumers to presentation and
  browser session credentials instead of an explicit future integration contract.

## Consequences

Stage 0 has real browser and PostgreSQL tests but is not a complete CRM. The Planner
must extend gates as code appears, and feature work remains blocked until the
skeleton passes CI and a deployed persistence smoke check. Frozen contracts describe
requirements; they do not claim those requirements have been implemented.
