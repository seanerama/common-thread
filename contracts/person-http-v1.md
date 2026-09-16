# Contract: person-http-v1

- **Status:** frozen v1
- **Owner:** contacts HTTP adapter

## Exposes

The first, same-origin JSON seam. This is not yet an external integration API.
All paths include the trailing slash; unsafe methods must not depend on redirects.

| Method and path | Input | Success |
| --- | --- | --- |
| POST /api/v1/people/ | JSON {"display_name":"Alex Example"} | 201; Person envelope; Location points to its detail endpoint |
| GET /api/v1/people/{id}/ | UUID path parameter | 200; Person envelope |

Person envelope: `{"data":{"id":"<UUID>","display_name":"Alex Example",
"is_client":false,"created_at":"<UTC RFC3339>","updated_at":"<UTC RFC3339>",
"archived_at":null,"version":1}}`.

## Consumes

session-auth-v1 for session, CSRF, workspace scoping, and error envelopes;
crm-core-v1 for Person/Party identity and validation. The active workspace comes
from the authenticated server-side context, never from the request body.

## Schema / wire

Accept application/json for POST; other media types return 415 unsupported_media_type
in the standard error envelope. Invalid JSON or invalid/unknown input fields return
400 validation_error. A request exceeding 16 KiB returns 413 payload_too_large.
display_name is a required string trimmed at both ends, then 1–200 characters.
Clients cannot submit id, workspace_id, kind, version, or attribution fields.
Each successful POST creates a new UUID; retries are not idempotent. The form UI
redirects after success and prevents duplicate submission while a request is pending.

Responses use application/json and Cache-Control: no-store. Creation persists before
201 is sent. Missing, invalid UUID, or inaccessible detail IDs return the same 404.
Clients tolerate unknown response fields. Server-generated timestamps are UTC and
versions are JSON integers. Errors follow session-auth-v1, including 401, 403, and
safe 500 internal_error responses; diagnostic details remain server-side.

HTML Stage 0 routes: GET /people/ lists active workspace people; GET /people/new/
shows a form; POST /people/new/ validates using the same service and redirects with
303 to /people/{id}/ on success; GET /people/{id}/ renders the persisted person.
Invalid forms return 200 with field errors and no write. These views implement the
same validation and authorization as the JSON adapter.

## Versioning

Frozen v1; additive-only. Later list/edit/archive JSON endpoints must be specified
before implementation. Kelsey Knows Omaha authentication and integration ownership
remain a future contract, not an implied permission to call this session API.
