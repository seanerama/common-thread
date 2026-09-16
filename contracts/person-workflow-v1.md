# Contract: person-workflow-v1

- **Status:** frozen v1
- **Owner:** contacts/context HTML adapters

## Exposes

Additive HTML workflows for stages 1 and 2. Existing person-http-v1 JSON operations
remain unchanged. This is not a machine-to-machine integration seam.

## Consumes

crm-core-v1 domain validation/versioning, session-auth-v1 sessions/CSRF/workspace
checks, and existing /people/ and /people/{id}/ HTML views from person-http-v1.
Every lookup, related-object lookup, search, and history read is workspace-scoped.

## Routes and forms

All paths end in /. Unsafe actions use POST with csrfmiddlewaretoken. New edit
forms carry expected_version as a positive integer. GET never mutates. Successful
writes return 303 to the owning person's detail page. Validation errors return
200 with safe field errors; stale versions return 409 with a reload-and-review
message, preserving submitted text without committing it. Missing/inaccessible
objects return 404. Unauthenticated requests follow session-auth-v1.

| Route | Methods | Fields / behavior |
| --- | --- | --- |
| /people/ | GET | Optional q (0–200 characters), archived=exclude/include/only (default exclude), page (positive integer, default 1); 50 results/page |
| /people/{id}/edit/ | GET, POST | display_name, is_client (HTML checkbox), expected_version |
| /people/{id}/archive/ | POST | expected_version; set archived_at |
| /people/{id}/restore/ | POST | expected_version; clear archived_at |
| /people/{id}/contact-points/new/ | GET, POST | kind=email/phone, value, label (empty means null); expected_version of the parent Party |
| /people/{id}/contact-points/{point_id}/edit/ | GET, POST | kind, value, label; expected_version of ContactPoint |
| /people/{id}/contact-points/{point_id}/archive/ | POST | expected_version of ContactPoint |
| /people/{id}/notes/new/ | GET, POST | body, source; expected_version of the parent Party |
| /people/{id}/notes/{note_id}/edit/ | GET, POST | body, source; expected_version of ContextNote |
| /people/{id}/notes/{note_id}/history/ | GET | Prior body/source versions, authors/editors and timestamps |

q matches display_name or active contact-point value by case-insensitive substring;
results deduplicate people and sort by display_name then id. Invalid query values
return 400 with a safe message; out-of-range pages are empty. Search never searches
other workspaces or changes client status. Names and email addresses are not unique.

New contact-point/note writes lock and check the parent version, reject archived
parents, and increment the parent version atomically. Existing-child writes check
its own version and parent workspace/archive status inside the same transaction;
lock parent then child consistently to avoid archive races. An archived person's
existing data/history remains readable but edits require restoring the person.
Archived contact points are retained and excluded from active contact display/search.

Stage 2 stores source_interaction_id=null until interactions are implemented; no
form accepts an unsupported link. Attribution comes from the session. Note edits
atomically snapshot old body/source and version plus original author, editor, and
edit timestamp before incrementing the current version. HTML escapes all user text.

## Feature controls

PEOPLE_MANAGEMENT_ENABLED and CONTEXT_NOTES_ENABLED are runtime booleans, default
false. With the relevant flag off, hide its new controls and reject its new routes
with 404 before any mutation. PEOPLE_MANAGEMENT_ENABLED also disables the added
search/filter controls; the original Stage 0 list/detail/create behavior remains.
CONTEXT_NOTES_ENABLED gates new notes, edits, current-note panels, and history.
Disabling a flag preserves data and access protections. Deployments explicitly
turn flags on for acceptance smoke; tests cover both settings. No flags alter the
frozen JSON create/read contract or bypass authentication. Document restart needs
for environment changes; no dynamic flag service is required.

## Versioning

Frozen v1, additive-only. This adds routes and flags without editing existing
contracts. New JSON edit/search endpoints, interaction links, and team sharing need
explicit contracts before implementation.
