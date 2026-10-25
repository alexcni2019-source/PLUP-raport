# PLUP product quality review — 8 October 2026

Applied selected official Apple Human Interface Guidelines to the existing web app, adapted to Android, iOS and desktop. This is a web implementation, not an Apple certification or a native app conversion. NRG report layouts, charts, exact data, blank detail cells and Python rendering remain unchanged.

## Changes

- Semantic light/dark surfaces and system appearance, readable mobile inputs, 44 px minimum buttons, safe-area spacing, keyboard focus and reduced motion.
- Inline loading/error feedback, double-submit guards, stale navigation-response protection and a selected-date/theme/value snapshot for multi-page export.
- Plan history editing updates the same record instead of creating another. One-row undo for plans and forecasts.
- Unsaved-change protection when replacing forms or leaving the page. A successful PNG export does not falsely count as a saved history record.
- Plan image import review is enforced before export, matching save and forecast behavior. Invalid decimals explain the accepted format.

## Verification

WebKit browser tests at 320, 390, 768 and 1440 CSS px: all four modules fit without horizontal page overflow; numeric fields render at 16 px or larger; system/manual appearance switching works. Save, history PUT with stable ID and changed date, delete/undo, PNG download date, single-day PNG selected date, OCR draft review gate and failed-save value retention passed. All frontend JavaScript syntax checks passed.

Tests used a separate temporary SQLite database on localhost. OCR review tests used a deterministic draft response; this does not establish general OCR accuracy. Browser emulation is not a physical iPhone/Android test. This scoped review is not an independent security or accessibility audit.

Railway live configuration was checked: existing private Dockerfile source, persistent /data volume, configured session/password variable names, no staged changes. Existing Tailscale Serve configuration was retained; no public domain or Funnel was added. Secret values were not read.

## Recommended next steps

1. Rehearse a backup restore into an isolated database and record recovery time before relying on this as the sole production archive. This review did not verify existing backups or a restore.
2. Before expanding access, independently review Tailscale identity/ACLs, app sessions/CSRF, import endpoints and per-user permissions. Do not change access automatically.
3. Add history filters by date/type and a visible edited timestamp to make finding and reviewing reports faster.

## Sources

https://developer.apple.com/design/human-interface-guidelines

Selected official chapters: design principles, accessibility, layout, typography, buttons, text fields, motion, dark mode, progress indicators, privacy and alerts. Verified 8 October 2026. Standing workflow is saved in the personal apple-hig-product-quality skill.
