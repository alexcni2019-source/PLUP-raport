# PLUP smart workflows — 8 October 2026

## Included

- Dashboard: final reports for today, recent reports, resumable drafts, 7/30-day handed/backlog/waste figures, metric selector, chart and exact accessible table. Missing days are distinct from zero. Daily/weekend overlaps use the latest saved version for each actual date; drafts are excluded.
- Assistant: deterministic validation, backlog/handed inconsistencies, missing quantities, duplicate product/client rows, handed-versus-plan checks, indicative waste warning above 5% (explicitly not an approved production limit). Executive summary uses the validated totals; daily/weekend comparison with saved same-date plans is included only when all needed plans exist. Clipboard copy has manual selection fallback. Editing clears a stale summary.
- Catalog: product/client/measurement suggestions from saved plan/forecast history. Selection fills only the selected field and empty related fields. No quantity is guessed.
- Image comparison for plan/forecast: ephemeral source image beside extracted/current cells, uncertainty text and edit navigation. Images are not stored in drafts or history. OCR confirmation remains mandatory after draft recovery.
- Drafts: debounced SQLite synchronization plus local browser fallback, explicit resume, source metadata and history identity preserved. Final save removes the draft. Draft/report conflict checks prevent silent overwrites. This app uses its existing shared application identity; drafts are not per-user accounts.
- Version history: save/edit/restore revisions, exact human-readable differences, optimistic report version check. Restore creates a new revision. Old pre-feature reports retain their baseline on first edit. This is not a person-attributed audit trail.
- Direct Excel/TSV/CSV import into plan, forecast and production forms. Clipboard paste accepts tab-separated cells. XLSX sheet/header selection, explicit column mapping, preview and confirmation; remembered mapping requires the exact normalized header. Optional cells stay empty. Formula results use cached values with warnings; formulas/macros are never executed. CSV and XLSX data never go to an external AI service. Excel header copying provides a starting format.

## Operation

From the dashboard, select a module or continue a draft. Prefer copying the Excel table **including the header** and pasting it into the Excel box. Check the mapping, apply, review the values, run the assistant, then save/generate. Screenshots of plan/forecast still use the image import and comparison flow. This release does not claim instant or error-free screenshot OCR and does not add a general production-screenshot recognizer.

XLSX input limits: 6 MB input, 25 MB total uncompressed archive, 500 entries, 10 worksheets, 500 rows and 40 columns per sheet. App reports remain limited to 100 product rows. XML DTD/entities, macros and unsupported archive relationships are rejected. Old .xls files should be converted to .xlsx or copied as cells. Large/complex workbook areas can be copied separately.

## Validation

`PYTHONPATH=. python3 -m unittest discover -s tests -v`

Seven backend tests cover version restore/conflict, partial draft/conflict, analytics overlap and missing-versus-zero, deterministic warnings, TSV/XLSX cached formula behavior and authentication/CSRF/origin protection on new endpoints.

WebKit checks at 320, 390, 768 and 1440 CSS px in both themes cover all modules and absence of page overflow. Complete browser flows passed: draft reload/resume, stable report ID edits and restore, Excel mappings with empty cells, XLSX upload, clipboard table routing, summaries, catalog, image comparison/edit jump, status-hidden forecast PNG, selected-date production PNG and 4 weekend PNGs. Final saves were checked not to leave stale drafts.

Tests used separate temporary databases and synthetic workbook/image-import fixtures. They do not establish general OCR accuracy, physical-device compatibility or an independent security audit. Existing report image layouts and Python calculations were retained; no public domain, proxy or identity provider was added.

## Next reviews

Verify an actual backup restore for the production database, review per-user authorization before adding users, and validate recurring source file formats on real supplied examples. Version history remains on the same volume and does not replace an off-volume backup.
