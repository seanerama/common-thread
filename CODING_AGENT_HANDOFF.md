# Coding agent handoff: Common Thread

Created: September 15, 2026

## What we are building

A standalone, general-purpose CRM focused on relationships and remembering
clients as people. The project identity is locked as `Common Thread`, with the
repository slug `common-thread` under GitHub owner `seanerama`.

The user's central requirement is: **keep the focus on the relationship—remembering
clients as people.** The product should help someone remember what matters to a
person, understand their shared history, and follow through on commitments.

The first three use cases are:

- A Realtor working with individuals and families.
- A Pre-Sales Engineer working with companies in networking, compute, and AI.
- An Attorney working with individuals and organizations.

These validate one reusable product. Do not build three separate applications or
make real estate the default domain. A company can be the client while its people
remain central to the relationship experience.

## Confirmed direction versus proposed implementation

The user has confirmed the standalone project, applicability across verticals,
the three initial use cases, the relationship-first emphasis, and eventual
integration with Kelsey Knows Omaha.

The model, milestone, and architecture below are proposed implementation guidance.
The user has not selected a framework, hosting model, or final UI.
Choose routine implementation details pragmatically and document assumptions;
surface consequential product decisions rather than presenting them as agreed.

## Repository and current state

- Project directory: `/home/smahoney/projects/relationship-crm`.
- Separate local Git repository, initialized on `main`.
- Documentation only. No application, database, tests, or deployment exists yet.
- Related application: `/home/smahoney/projects/kcrealestate`, which powers
  Kelsey Knows Omaha. This is context for later integration, not the new project's
  implementation directory.

Supporting documents:

- [Product brief](docs/product-brief.md)
- [Architecture proposal](docs/architecture.md)

## Primary user experience

Before a conversation, the user should quickly understand who someone is, how
they are connected, what matters to them, what was discussed last, and what is
still owed. Afterward, the user should easily record useful context and the next
commitment.

Make the person page the first complete workflow. Bring together contact details,
relationships, meaningful context, conversation history, and open follow-ups.
An organization page should expose its people and their roles, not just account
metrics. A household should preserve each person's individual identity and goals.

## Proposed core model

| Concept | Purpose |
| --- | --- |
| Person | Individual identity, name, contact points, preferences, and personal context |
| Organization | Company or other entity connected to people through roles |
| Household | A grouping of people with their individual identities preserved |
| Relationship | A typed connection, such as employment, household membership, or referral, with optional effective dates |
| Interaction | A dated conversation, meeting, or other touchpoint with linked participants and authored notes |
| Context note | Useful information about a person, with source, author, and date |
| Commitment | Who owes what to whom, optional due date, status, and related people or interaction |

Use stable identifiers. Email addresses are contact points, not permanent identity
keys. Shared or changed addresses must not force people to merge.

Avoid a strict organization > household > person hierarchy. A person may belong
to a household, work for one company, and advise another. Preserve past affiliations
when current roles change. Client status must be explicit: knowing someone or
subscribing to a newsletter does not establish a client relationship.

Store a multi-person interaction once and link its participants. Record facts
and their provenance; do not present inferred personal details as established
facts. Support corrections and archiving without breaking historical references.

## First implementation milestone

Build a locally runnable, persistent application that can:

1. Create, search, view, edit, and archive people, organizations, and households.
2. Add and update relationships and roles, including historical affiliations.
3. Record an interaction with multiple participants.
4. Capture and correct meaningful context about a person.
5. Create, view, and complete commitments and follow-ups.
6. Show a coherent person page combining those records.

Choose and document a maintainable stack before scaffolding. Prefer a modular
application with a relational database and migrations. Keep the domain independent
of industry-specific screens. Design for a future versioned integration API without
building a plugin platform or distributed services in the first milestone.

Define authentication and record-access behavior explicitly. Use fictional seed
data during development. Apply authorization to server reads and writes, not only
to visible UI controls.

## Acceptance scenarios

- **Realtor:** Create two people in one household, record their different home
  priorities, log a shared conversation, and add a promised follow-up. Each person
  page shows their own context and the shared interaction.
- **Pre-Sales Engineer:** Create a company with a technical lead and a business
  sponsor. Record their different concerns about an AI infrastructure evaluation
  and a promised networking design review. Change one person's employer while
  retaining their prior relationship history.
- **Attorney:** Create an individual client and an organizational contact. Record
  communication preferences, a conversation, and a promised update. This workflow
  must work without implementing a legal case-management system.
- **Shared behavior:** Editing a shared interaction updates it consistently for
  all participants. Completing a commitment removes it from outstanding work while
  preserving its history. Archiving a contact preserves earlier interactions.
- **Persistence and access:** Records survive an application restart. Unauthorized
  requests cannot read or modify protected records through direct API calls.

Use meaningful automated tests for persistence, relationship history, shared
interactions, commitments, and authorization. Include a browser-level verification
of the main person workflow. Provide exact local setup and test commands.

## Deferred scope

Defer full sales pipelines, real-estate transactions, legal case management,
marketing automation, bulk import, automatic messaging, and industry-specific
workflow engines. Professional engagements can be added later as typed extensions
referencing core records.

AI assistance is optional future functionality. The initial product must be useful
without it. Future summaries should cite underlying records and respect access
boundaries.

## Later integration with Kelsey Knows Omaha

Build and validate the standalone experience first. Kelsey Knows Omaha currently
has newsletter-oriented people and email records, not a complete CRM. No clients
have been imported, per the user.

Proposed integration boundary:

- The CRM owns relationship profiles, connections, notes, and commitments.
- Kelsey Knows Omaha retains ownership of newsletter consent, preferences,
  suppression, delivery, properties, and community events.
- An adapter maps existing local contact IDs to CRM IDs and uses an API rather
  than shared database tables.
- Matching a subscriber to a person must not automatically promote them to a
  client or change their consent.

Do not migrate or modify Kelsey Knows Omaha as part of the initial CRM milestone.
Specify field ownership, matching, failure behavior, and retry semantics when the
integration becomes an active implementation task.

## Starting instructions for the next coding session

Read this handoff and the supporting documents, inspect the current repository,
and propose a concise implementation sequence. Select and document the stack,
then deliver the person workflow end to end with persistence before broadening
the remaining screens. Keep implementation in this standalone repository.

At handoff, report what runs, setup instructions, validation results, remaining
limitations, and any product decisions that still need the user's input.
