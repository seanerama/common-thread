# Contract: relationship-crm-workflow-v1

- **Status:** frozen v1
- **Owner:** party, relationship, interaction, commitment and person overview HTML adapters
- **Introduced by:** relationship workflow intake, stages 3–7

## Boundary and common behavior

Consumes crm-core-v1, session-auth-v1, runtime-v1 and the existing person workflows.
Adds same-origin HTML workflows to the existing Django application and PostgreSQL.
The five existing frozen contracts and Person JSON endpoints remain unchanged.
No machine API, shared workspace, job worker, notification delivery or AI is added.

All paths end in /. GET never mutates. Writes use POST and CSRF. UUIDs, workspace,
authorship, timestamps and resulting versions are server-assigned. Reject unknown
form fields and forged attribution; repeated values are allowed only for explicitly
multi-valued ID lists. New records start at version 1; updates and state changes
require positive expected_version. Stale submissions return 409 with submitted text
preserved and a reload/review instruction; no partial write. Ordinary field validation
returns 200 with escaped errors. Invalid/inaccessible related IDs submitted as form
fields return generic 400 without disclosing existence or writing anything, per
session-auth-v1. Missing/inaccessible URL targets return 404. Authentication,
revocation and staff/superuser behavior follow session-auth-v1 on every path.
Successful writes return 303 to the affected record's canonical detail route below.

Strings use the core contract's limits and reject NUL/surrogates; render escaped text.
Date fields use ISO YYYY-MM-DD, empty nullable dates/role/source reference mean null.
An edit form submits all of its editable fields; domain updates that omit an optional
field preserve it. Interaction times include an explicit UTC offset and normalize to
UTC; a datetime-local UI must label and explicitly convert its selected timezone.
Support the full 20,000-character interaction body through bounded Unicode HTML
requests; preserve the original JSON endpoint's 16 KiB cap.

Lists use page (positive integer, default 1), 50 records/page, stable ordering with UUID
as tie-breaker. Invalid query inputs return safe 400; out-of-range pages are empty.
Selectors search only the active workspace, paginate at 50 choices and exclude archived
parties for new links. Existing selected archived references remain labeled/readable.
Selectors may be rendered within forms; no new public JSON lookup endpoint is implied.

Every referenced CRM entity and revision has a same-workspace database constraint.
Participant/link rows have unique parent/party pairs. Person-only links also enforce
the Person subtype, not just an arbitrary Party UUID. Referenced users are retained.
Use additive migrations preserving stages 0–2; never reverse/drop existing data as a
feature toggle or deployment rollback. No user-facing hard deletes.

## Stage 3: organizations and households

For each prefix /organizations/ and /households/:

| Suffix | Method | Input/behavior |
| --- | --- | --- |
| (none) | GET | q (0–200 chars), archived=exclude/include/only (default exclude), page |
| new/ | GET, POST | display_name, is_client checkbox; create Party + matching subtype atomically |
| {id}/ | GET | Scoped detail, including archived records |
| {id}/edit/ | GET, POST | display_name, is_client, expected_version |
| {id}/archive/ | POST | expected_version; set archived_at |
| {id}/restore/ | POST | expected_version; clear archived_at |

Search matches display_name by case-insensitive substring and sorts by display_name,
id. Separate Organization and Household subtypes share the Party ID, as Person does.
Party kind is immutable and checked on each typed route. Archive/restore increment
version; editing an archived record requires restore. No implicit client status,
membership, person merge or mandatory organization/household hierarchy is introduced.
Organization/household contact-point editing is deferred; existing Person contacts
remain unchanged. Success redirects to /organizations/{id}/ or /households/{id}/.

## Stage 4: dated relationships

| Route | Method | Input/behavior |
| --- | --- | --- |
| /relationships/new/ | GET, POST | from_party_id, to_party_id, kind, role, starts_on, ends_on |
| /relationships/{id}/ | GET | Endpoints, role and effective dates |
| /relationships/{id}/edit/ | GET, POST | kind, role, starts_on, ends_on, expected_version |
| /relationships/{id}/close/ | POST | ends_on (required), expected_version |

Endpoints differ and remain immutable after creation. Use core kind vocabulary
employment, household_member, referral and other as suggestions; nonempty custom
kinds of 1–80 characters are valid. A relationship is directed from the first party to
the second; display that direction from either endpoint. For employment and household
membership, forms guide the user to select the person as the from endpoint.
Dates satisfy ends_on >= starts_on when both exist. Closing changes ends_on and
increments version, retaining the row. Correcting dates can reopen an affiliation by
clearing ends_on. Changing employer/household creates a new relationship, preserving
the old row. Duplicate endpoint pairs can represent distinct roles/periods; do not
merge people or collapse historical affiliations.

Show scoped relationships on both endpoints' detail pages, distinguishing future,
current and ended affiliations using UTC calendar date; starts_on/ends_on are inclusive.
Records with no bounds are current. Order current/future by starts_on (null first), id;
ended by ends_on descending, id. Paginate each collection. Ended and archived-endpoint
references remain readable; correction/closing existing links is allowed. New links
require both endpoints active. Success redirects to /relationships/{id}/.

## Stage 5: shared interactions

| Route | Method | Input/behavior |
| --- | --- | --- |
| /interactions/new/ | GET, POST | occurred_at, body, participant_ids (one or more distinct Party UUIDs) |
| /interactions/{id}/ | GET | One shared interaction and current participants |
| /interactions/{id}/edit/ | GET, POST | occurred_at, body, participant_ids, expected_version |
| /interactions/{id}/history/ | GET | Prior content, timestamp, participant sets and provenance |

Store one Interaction plus unique InteractionParticipant links, never one copied
interaction per person. Creation and participant replacement are atomic and nonempty.
Attribution is the authenticated user and remains the original author on correction.
Every correction snapshots prior body, occurred_at, participant IDs, version and original
author, together with correcting editor and correction time, atomically before advancing
the current version. Historical participant references remain workspace-scoped even
when removed from the current set or archived. All current participants' detail pages
show the same record; removed participants no longer list it as a current interaction.
Within the private workspace, authorized users may still read its correction history.

New participants must be active. Retaining/removing an existing archived participant
is allowed, as is correcting historical interaction text; archiving a party does not
rewrite or hide history. Detail-page interaction lists order occurred_at descending, id,
with page size 50. Success redirects to /interactions/{id}/. ContextNote forms and their
source_interaction_id=null constraint remain unchanged in this release; linking an
existing note to an interaction requires a later intake.

## Stage 6: commitments

| Route | Method | Input/behavior |
| --- | --- | --- |
| /commitments/ | GET | status=open/completed/all (default open), due=all/overdue/today/undated (default all), page |
| /commitments/new/ | GET, POST | description, owed_by_party_id, owed_to_party_id, due_on, person_ids (nonempty distinct Person UUIDs), source_interaction_id |
| /commitments/{id}/ | GET | Description, direction, due date, status and linked people/source |
| /commitments/{id}/edit/ | GET, POST | Same editable fields as create plus expected_version |
| /commitments/{id}/complete/ | POST | expected_version; status=completed, completed_at=server UTC now |
| /commitments/{id}/reopen/ | POST | expected_version; status=open, completed_at=null |

Create status=open; callers cannot set created_by, status or completed_at through
create/edit forms. Attribution is server-assigned and retained. At least one linked
Person is mandatory independently of the owing/receiving parties' kinds. Do not infer
links from clients, employers or household membership. Changing participants and
content is atomic. No rule forces owed_by and owed_to to differ. Both must be explicit
CRM Party IDs; the authenticated account is not implicitly a CRM person.

Optional source_interaction_id references an existing interaction in the same workspace.
When INTERACTIONS_ENABLED is off, do not offer new/changed source links or expose source
content; preserve an existing source link when omitted. Clearing it is allowed. Existing
archived party/person links may be retained or removed and commitments completed/reopened;
newly linked parties/people must be active. Source selection never copies an interaction.

Person pages show commitments only via CommitmentPerson. Lists order due_on ascending
(null last), created_at, id. Overdue means open with due_on before today's UTC date;
today matches today's date and undated means due_on=null. Label the UTC date convention
in the UI. Valid state transitions increment version; requesting the current state is
an ordinary validation error with no version/timestamp change. A stale transition returns 409.
Success redirects to /commitments/{id}/. Completion history remains readable through
completed records; no notification, delivery, recurrence or immutable audit guarantee.

## Concurrency across shared records

Resolve and lock all involved Party rows in UUID order before locking the affected
relationship/interaction/commitment. For edits, include the union of old/new references.
If a reference set changes while gathering locks, revalidate under the record version
and return a safe conflict or retry without writing; never acquire late Party locks in
reverse order. Lock a referenced Interaction before a Commitment if both are needed.
Recheck workspace, current versions and archive state under locks. Existing Party
archive/restore operations must use the same Party locks. New-link creation either
commits before archive or fails without partial links afterward. Child writes increment
their own version; unlike the existing person contact/note creation contract, these
standalone multi-party creations do not increment Party versions or require client
submission of every Party version. Archiving retains historical references.

## Stage 7: unified person overview

Reuse GET /people/{id}/; no new write endpoint, schema or duplicate aggregate store.
Add a compact preparation summary above the existing sections: current relationships,
five latest interactions, and five open commitments (due date ascending, null last).
Show total counts and links to the full paginated sections, never silently omit excess
records. Full relationship sections use relationships_page and relationships_ended_page;
interactions use interactions_page; commitments use commitments_page and
commitments_status=open/completed/all (default open). These new query parameters follow
the common validation rules and are introduced with their owning stage's panel.
Stage 3 organization/household details use the same applicable panel parameters.
Existing notes/contact sections remain intact. No shared mutation form is reimplemented;
link to its owning workflow. Stage 7 improves arrangement, labels, empty states and
keyboard usability and validates end-to-end fictional scenarios for all three professions.
An archived person's prior records remain readable; no action bypasses new-link guards.

## Flags and compatibility

PARTY_DIRECTORY_ENABLED (stage 3), RELATIONSHIPS_ENABLED (4), INTERACTIONS_ENABLED (5),
COMMITMENTS_ENABLED (6), PERSON_OVERVIEW_ENABLED (7) are runtime booleans default false.
Each gates its new routes, controls and panels; disabled routes return 404 before CSRF
processing or mutation. Disabling preserves stored records. Overview off restores the
stage-6 layout; it never disables the underlying feature. Overview on renders only
panels whose own flags are enabled. Existing PEOPLE_MANAGEMENT_ENABLED and
CONTEXT_NOTES_ENABLED keep their exact meanings.

Feature flags are independent: a relationship/interaction/commitment can reference
existing authorized Party rows while the directory flag is off. Their scoped selectors
remain usable; render endpoint labels without links to disabled directory pages. Likewise
hide source links/content when interactions are off. Flags never bypass authorization.
Every flag change requires process restart/recreation; document this in the runbook.
Each stage tests off/on, independent combinations, data preservation and deployed smoke
against the exact CI-tested image, including restart and restored-database reads on
AMD64 and emulated ARM64. No new production target is selected.

## Versioning

Frozen v1. Later JSON/machine adapters, team sharing, reminders, note-to-interaction
linking or changed access semantics require explicit new contracts before implementation.
