# Contract: crm-core-v1

- **Status:** frozen v1
- **Owner:** CRM application services

## Exposes

Logical record semantics shared by HTML views, persistence adapters, and future API
adapters. This freezes domain invariants, not physical SQL table names or a promise
that every entity exists in Stage 0. Services receive an authenticated user and
workspace context per session-auth-v1; callers cannot bypass that context.

## Consumes

Active workspace membership, transactional PostgreSQL storage, server UTC clock,
and server-generated UUIDs. Authentication users are not CRM Person records.

## Schema

All CRM entities have UUID `id`, UUID `workspace_id`, UTC RFC3339 `created_at` and
`updated_at`, nullable UTC `archived_at`, and positive integer `version` (starts at 1).
Strings are Unicode text, displayed as escaped text. Dates are ISO YYYY-MM-DD.
Nullable fields are explicit null; omission in updates preserves the existing value.

| Entity | Required fields beyond common fields | Optional/default fields |
| --- | --- | --- |
| Party | kind: person, organization, or household; display_name (trimmed, 1–200 characters) | is_client boolean, default false |
| ContactPoint | party_id; kind: email or phone; value (1–320 characters) | label nullable string |
| Relationship | from_party_id; to_party_id; kind (1–80 characters) | role nullable string; starts_on/ends_on nullable dates |
| Interaction | occurred_at UTC timestamp; body (1–20000 characters); authored_by user UUID | none |
| InteractionParticipant | interaction_id; party_id | none |
| ContextNote | person_id; body (1–20000 characters); source (1–500 characters); authored_by user UUID | source_interaction_id nullable UUID |
| Commitment | description (1–2000 characters); owed_by_party_id; owed_to_party_id; created_by user UUID | due_on nullable date; source_interaction_id nullable UUID; status open/completed, default open; completed_at nullable timestamp |
| CommitmentPerson | commitment_id; person_id | none |

Party IDs identify subtypes without separate competing identities. A Party's kind is
immutable. Person names need not be split into first/last fields. An email/phone may
be shared by multiple parties, and changing it never changes Party identity.

Relationship endpoints must differ, and ends_on cannot precede starts_on. Closing
an affiliation retains it; a new affiliation creates another row. No mandatory
company > household > person hierarchy. Initial kind vocabulary includes employment,
household_member, referral, and other; clients tolerate additional kinds.

An Interaction has at least one unique participant and exists only once, regardless
of participant count. Editing it updates every participant's view. Creation and
participant changes are atomic. ContextNotes reference Person parties only; their
source is required and inferences must be labeled by the author rather than stored
as verified facts. Commitments require at least one linked Person; completing one
sets completed_at using the server clock. Reopening clears it. The person page
shows commitments via CommitmentPerson, not by inferring contact/client status.

All referenced entities and revision rows are in the same workspace. Attribution is
server-assigned; referenced actor accounts are retained when deactivated. Ownership
of a professional relationship never establishes consent for external newsletters.

## Mutation and history rules

Updates include expected_version. The service atomically compares it, applies the
change, and increments version; a mismatch returns a conflict without mutation.
Invalid fields/references fail the entire transaction. Archived parties remain
resolvable in historical records but are excluded from default search and cannot
receive new links until explicitly restored. Archive and restore are versioned
mutations. No user-facing hard-delete operation is part of v1.

Corrections to notes and interactions preserve the previous version, author, editor,
and edit time. Membership checks cover history as well as current records. Revision
storage must not introduce a separate data-access path.

## Versioning

Frozen at v1. Optional fields and new operations may be additive; changing existing
field meaning, required inputs, access scope, or removal semantics needs a NEW
contract. SQL migrations remain internal but must preserve these logical guarantees.
