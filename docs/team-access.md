# Colleague access and owner control

Alexandru chose email/password for colleagues and manually shared invitation
links. The configured GitHub identity remains the sole owner. This feature
does not connect Microsoft/Teams, install an identity service, send email or
allow public self-registration.

## Owner workflow

Open **Echipă**, enter the colleague's email and optional name, choose **Cititor**
or **Editor**, then select Producție (daily and three days), Plan and/or Previz.
Create the link, copy it and send it personally to that colleague. Links expire
after 48 hours and are single-use. The invitation is bound to its email.
The colleague opens the link, chooses a password of 12–128 characters and signs in.

Only the owner can list accounts, issue invitations, change roles/modules,
revoke access and reset accounts. **Revocă accesul** invalidates sessions and
unused invitations without deleting saved reports. **Resetează accesul / link nou**
explicitly invalidates the old password, all sessions and old links, and returns
a new single-use activation link. Forgotten passwords use this owner workflow.
The link is returned only when issued; its raw value is not stored server-side.
The UI removes a consumed/revoked link after refreshing the account list.

Cititors can read history and export permitted reports, but cannot save reports,
drafts, imports or restored versions. Editors can work in their allowed modules.
Both are excluded from the user administration and backup APIs. Server checks
also cover report IDs, versions, latest templates, dashboards/catalogs, analyses,
imports, renders and direct API calls. Scope changes are checked on each request;
reload the UI to display the new permissions.

## Persistence and security

`members`, `member_invites`, `member_sessions`, `member_drafts` and `access_events`
are additional SQLite tables on the existing private volume. Existing reports,
report versions, owner drafts, GitHub configuration and ownership are retained.
Passwords use salted scrypt (N=32768, r=8, p=3), with bounded hash concurrency.
Session and invitation tokens are cryptographically random and stored as SHA-256
hashes. Colleague sessions expire after eight hours and survive process restarts;
revocation/reset is checked from the database. Cookies are Secure, HttpOnly,
SameSite=Lax, host-only and valid for the origin root.

Public login/activation JSON endpoints require same-origin requests, bounded
bodies and rate limits. Authenticated mutations retain CSRF validation. The
existing strict CSP, private static-file gate and configured GitHub owner allowlist
are preserved. Successful colleague login replaces the current browser identity,
so a previously logged-in owner's cookie cannot override a colleague's role.
Invitation secrets use URL fragments, are removed from the activation page's
address and never enter server request URLs or audit entries.

Owner drafts retain their existing table. Colleagues use drafts scoped by
member ID and mode; saving a colleague's report does not delete an owner's draft.
Browser fallback drafts are namespaced by account. Legacy owner drafts migrate
once; switching accounts clears the prior account's draft cache. Permission
changes are rechecked inside report/draft/default-write transactions too.

New access and report actions are attributed to their account in `access_events`;
the owner sees the latest 50 in Echipă. Existing historical versions are not
retroactively attributed. JSON report backups preserve account tables on restore;
the owner-only SQLite export includes the complete database. Do not put live
databases, password hashes or real invitation/session tokens in source archives.

## Verification

Backend tests cover scoped reads/writes and ID access, single-use/expired invites,
password hashing and resets, CSRF/origin/rate checks, session persistence/revocation,
owner protection, draft isolation, former-version module filtering and write-time
permission rechecks. Browser tests use a temporary SQLite database and local HTTPS
with a synthetic owner and colleague; no real colleagues or invitations are created.
They exercise creation, activation, read-only export, editor save, role change,
revocation and denied subsequent login, plus owner UI in both themes and
320/390/768/1440 CSS-pixel layouts. Existing report/import browser regressions run
separately. This is implementation verification, not an independent security audit.
