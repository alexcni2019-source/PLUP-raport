# Teal & Cream — editor-first release

Alexandru approved applying the demonstrated Teal & Cream direction to the real
private application. This release follows the existing approved palette and
self-hosted Source Sans 3, with a text-and-icon sidebar, compact report totals,
clearer hierarchy and quieter borders and shadows.

The Excel paste field remains permanently visible in all reporting modules.
Its shorter initial height and the compact header/summary bring it into the
first mobile viewport. The textarea remains resizable. Excel/CSV upload now
uses a native keyboard-accessible button opening the existing file picker.
Image import remains available through the existing disclosure.

The theme switch has an explicit accessible name on mobile, a visible focus
state and a correctly proportioned track. Dashboard metric units inherit the
high-contrast text color. Light/dark and reduced-motion behavior are retained.

Controllers, canonical Python calculations, source cells, report identity,
drafts, history, AL/CU grouping and export templates retain their existing
contracts. No sample values are introduced into production. The row-by-row
comparison, new report layouts, Teams integration and colleague invitations
remain separate proposals, not newly enabled features of this design release.

Verification uses an isolated temporary SQLite database: TypeScript/Vite build,
92 Python tests, the staged Excel import regression, 28 existing browser workflow
checks, plus 50 layout/theme/view combinations at 320/390/768/1024/1440 CSS px.
The layout check verifies Excel visibility in the first viewport, keyboard file
picker activation, review dialogs, retained blank CU values and live totals.
Screenshots were inspected at 390 and 1440 px. No physical-device testing is claimed.
