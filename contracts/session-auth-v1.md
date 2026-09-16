# Contract: session-auth-v1

- **Status:** frozen v1
- **Owner:** accounts/workspaces module

## Exposes

Same-origin authenticated browser session and workspace authorization for every HTML
and JSON adapter. No JWT, public signup, machine credentials, or third-party API
authentication is defined by this contract.

## Consumes

Operator-provisioned active user, server-side session storage, and active owner
membership of the requested workspace. Stage 0 supplies one private workspace per
user, including two distinct owners/workspaces in isolation tests.

## Wire and behavior

- GET /login/ renders a CSRF-protected form. POST /login/ accepts username, password,
  and csrfmiddlewaretoken. Success rotates the session and redirects to /people/;
  failure renders a generic invalid-credentials message without revealing whether
  the username exists. Rate-limit failures by account and source address, returning
  429 with Retry-After when limited; Stage 0 pins the implementation and thresholds.
- POST /logout/ requires CSRF, invalidates the server session, and redirects to
  /login/. GET never logs out or mutates CRM records.
- Cookie: `sessionid`, HttpOnly, SameSite=Lax, Secure on deployed HTTPS, Path=/,
  host-only. Absolute lifetime 12 hours; no sliding renewal. CSRF is enforced on
  all unsafe browser operations, including JSON writes. No permissive cross-origin
  CORS policy; any login redirect target must be local and allowlisted.
- Membership is checked on every request, including existing sessions. Deactivating
  a user or membership takes effect on the next request. Password reset invalidates
  prior sessions using Django's session authentication mechanism.
- Unauthenticated HTML requests redirect to /login/. JSON requests return 401 with
  code unauthenticated. CSRF failures return 403 with code csrf_failed for JSON.
- An authenticated caller requesting another workspace's object receives 404 with
  code not_found. List/search omit other workspaces entirely. Forged related IDs
  yield a generic 400 validation_error and no writes; they never disclose existence.
- JSON error shape: {"error":{"code":"validation_error","message":"Invalid request",
  "fields":{}}}. Fields maps field names to arrays of safe messages; it is always
  present (possibly empty). Other error codes include conflict (409), not_found
  (404), unauthenticated (401), csrf_failed (403), and rate_limited (429).
- Product routes never grant a staff/superuser bypass. Operator administration is
  separate and cannot be used as the product's person workflow.

## Versioning

Frozen v1; additive-only. Shared workspaces, service tokens, or record-level ACLs
require separately specified contracts before use. Network restrictions supplement
these application checks and do not replace them.
