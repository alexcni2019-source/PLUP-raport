# Apply a new table before saving or exporting

The table importer has a read/preview step followed by explicit application. Previously,
the main save/export actions remained available during preview and used the preceding
controller payload. A reproducible example shows a new W47 source table with blank
CU cabling cells alongside an export of the previous W46 plan with 9.2 km of cabling.
This explains a possible stale-data path; it does not establish the original request
sequence on the user's private production session.

The importer now marks new pasted, edited or uploaded input as pending. React shows
that state, withdraws old summary values and disables review/save/export until the
table is applied or explicitly discarded. Native save/export and analysis actions
also enforce the guard. A preview cannot be applied after its textarea was changed
without being read again. Late read responses are ignored after cancellation/replacement.
Loading another report clears its module's pending import.

Pending input is not autosaved as though the preceding controller payload were the
new import. Changes to report data withdraw generated PNG links and revoke their blob
URLs. Exports check the pending state between requests and after responses, preventing
an in-flight export from restoring old images after another paste.

Applying a replacement plan clears remaining-tonne overrides that belonged to the
preceding plan. Source cells and all original columns remain intact. The existing
combined Funie/Bară mapping also recognizes explicit `STOC BARA RE /SE (KM)` headers;
when Bară and Funie both exist, automatic inference selects only an unambiguous populated
column. It never shifts or sums adjacent columns. Explicit ambiguous mappings remain
available for review.

## Verification

- `python tests/browser_table_import.py`: isolated temporary SQLite database and a
  loopback server. Synthetic fixtures test a W46/9.2 previous plan, pending and modified
  previews, blocked native and React actions, applied W47 source fidelity, blank CU
  cabling, correct stocks, real PNG generation/save, cancellation, edited-source PNG
  invalidation and an export response arriving after a new paste.
- All 86 Python tests and the existing 28 browser workflow checks pass.
- TypeScript/Vite production build and JavaScript syntax checks pass.
- The separately supplied source table was checked locally through actual import,
  application, analysis and PNG download. Blank CU cabling cells remain absent from
  the diagram, and the source title, tonnes and stock columns are respected. Private
  source rows, totals and generated outputs were not committed as fixtures.

No production-history rows or database schema are changed. Existing downloaded PNGs
must be regenerated from the applied source table to reflect its current data.
