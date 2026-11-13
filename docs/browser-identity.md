# Browser-only private access

GitHub authorization-code flow with state, browser-binding cookie, PKCE S256 and a server-only client secret. No scopes are requested. Each sign-in fetches the authenticated GitHub identity and matches its immutable numeric ID to `PLUP_GITHUB_ALLOWED_ID`. Other accounts are refused. GitHub receives no reports, screenshots or spreadsheet contents.

Enable only after registration of a dedicated OAuth app:

- `PLUP_AUTH_MODE=github`
- `PLUP_PUBLIC_ORIGIN=https://<reserved Railway domain>`
- `PLUP_GITHUB_ALLOWED_ID=330319987` (verified connected account alexcni2019-source)
- `PLUP_GITHUB_CLIENT_ID` from the OAuth registration
- `PLUP_GITHUB_CLIENT_SECRET` directly into Railway Variables; never into chat or git
- Existing `PLUP_SESSION_SECRET` must remain configured.

OAuth registration homepage: public origin. Exact callback: public origin + `/auth/callback`. Leave device flow disabled. The app is for sign-in only; do not grant repository scopes.

Before activation, reserve the Railway domain pointing to unused port 9099. Do not route it to app port 8080 until GitHub mode is configured, deployed and tested. Tailnet access continues during preparation. Activating GitHub mode requires fresh identity login for all clients; use the new public origin on phones as well. Then route the domain to port 8080. No Funnel or public database port is needed. Keep `/data` volume and its reports untouched.

Missing identity configuration fails closed. No password fallback, local development fallback or static app access exists in GitHub mode. Health returns only `ok`. API reads require identity sessions, mutations additionally require CSRF and check Origin. Host-prefixed Secure/HttpOnly cookies; OAuth uses SameSite=Lax for the cross-site callback. Sessions expire after eight hours and server restart; explicit logout revokes server session. Access tokens are never retained in application storage, browser or logs. Pending OAuth states expire after ten minutes, bind to the starting browser, and are consumed once. Session and pending-state maps are bounded and thread-locked. This currently supports one service replica, like the existing SQLite deployment.

The sign-in page adapts to light/dark system theme. Session renewal opens a separate tab so unsaved form content remains in the original tab. Logout clears application-prefixed local storage in that browser; this is not a secure purge of downloaded reports. On shared PCs use a private browser window and explicitly sign out.

Validation: eleven backend tests (including four identity tests) cover browser-binding, PKCE transmission, callback replay, wrong immutable ID, unexpected OAuth scopes, expiry, missing config, static/API/password bypass, mutation CSRF and logout. Real GitHub exchange requires the user's OAuth registration and credentials. Browser emulation is not a physical device test or independent security audit.

Rollback: remove public domain routing before disabling GitHub identity. Never disable the identity gate while the domain routes to the app. Existing Tailscale mode can then be restored. Recommended next check: independent review of public-facing authentication and backup restore; no external auditor has been granted access.
