# AL/CU input and analytics separation

Corrected material loss when source tables place section headings outside the first column, or distinguish unlabelled sections only with material subtotals.

- `web/materials.js` and `server/materials.py` resolve explicit AL/CU labels and subtotals, including Aluminiu/Cupru synonyms. Product and client names are never used to guess metal. A conflicting section/subtotal requires review.
- New table imports without a material column, heading or subtotal require an explicit material choice. Existing saved records with no structural material evidence retain their recorded material.
- Rendering an old source-backed report repairs identifiable material assignments in memory. It does not rewrite archived reports or create a data migration. Reopening and explicitly saving is still a user action.
- Plan analysis and its summary PNG separate stages, clients and kilometre-to-tonne estimates by material. The same client can have AL and CU entries. Remaining-tonne edits use scoped material/client keys; old overall totals are not arbitrarily apportioned across metals.
- Forecast client distributions keep material and client together, and show the material in every chart label. The percentage in each material's row refers to that material's total. Combined overall totals remain available separately.

Verification: 86 Python tests, including eight new material-regression tests; browser checks of actual Excel/clipboard imports into Plan and Previz, shared-client AL 12 t / CU 5 t, scoped remaining edits, successful saving and PNG exports, and explicit choice for unlabelled input. These checks do not establish OCR accuracy for an unseen photograph.
