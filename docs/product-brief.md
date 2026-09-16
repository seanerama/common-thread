# Product brief

## Agreed direction

Build a standalone CRM that can be used in any vertical. Keep the focus on
relationships and remembering clients as people. First use cases: Realtor,
Pre-Sales Engineer (networking, compute, and AI), and Attorney. Later incorporate
the CRM into Kelsey Knows Omaha.

The remainder of this brief proposes a starting scope for that direction.

## Core experience

Before a conversation, quickly answer:

- Who is this person, and how do we know each other?
- What matters to them, personally and professionally?
- What did we last discuss, and what has changed?
- What did I promise, and what needs attention next?

After a conversation, recording the meaningful details and next commitment
should be easy enough to become a habit.

## Relationship model

People are first-class records with contact details, preferences, interests,
goals, and history. Organizations and households supply context, with explicit
relationships rather than a mandatory company > household > person hierarchy.
A person can belong to a household, work at a company, and advise another company.
Roles and affiliations can change without losing their history.

A client can be a person or an organization. Being a contact, an employee, a
newsletter subscriber, or a household member does not automatically make someone
a client. Professional engagements link to their participating people and roles.

Capture notes and interactions with dates, authorship, and source context.
Distinguish recorded facts from interpretations. Users must be able to correct
records. Commitments track who owes what to whom, their due dates, and completion.

## First-use-case checks

| Use case | Relationship-centered scenario | Professional context |
| --- | --- | --- |
| Realtor | Remember each household member's priorities and follow through after a conversation | Home search, property, transaction |
| Pre-Sales Engineer | Remember technical concerns, personal priorities, and commitments to people across an account | Networking, compute, or AI initiative; evaluation |
| Attorney | Recall a client's concerns and communication preferences and honor a promised update | Matter and participant roles |

The shared experience should work for all three without embedding profession
names or mandatory industry-specific stages in the core schema.

## Proposed first milestone

A usable standalone application supporting:

1. Create, find, edit, and archive people, organizations, and households.
2. Connect people to one another and to organizations or households with roles.
3. Record an interaction involving several people and review it in their history.
4. Record meaningful personal context with its source and date.
5. Assign and complete a follow-up or commitment.
6. Open a person page that brings their context, relationships, recent history,
   and outstanding commitments together.

Validate this milestone with fictional examples from all three professions.
Success means a user can prepare for a conversation and record its follow-up
without needing a sales pipeline or an industry-specific workflow.

## Later scope

Professional extensions, imports and deduplication, application integrations,
and optional AI assistance follow the core experience. Full transaction
management, legal case management, sales forecasting, marketing automation, and
automatic communication are outside the first milestone.

AI may eventually help retrieve and summarize relationship history with links to
supporting records. The core must remain useful without AI.
