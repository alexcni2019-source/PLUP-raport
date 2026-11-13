# Forecast product-list execution order

Generated forecast product lists sort numerically by `Ordine de execuție` inside
each AL/CU group. Urgent/Normal remains a separate attribute. Material groups,
subtotals, other structural rows and all product-cell contents are preserved.

`server/forecast_order.py` supplies stable ordering for standard product lists and
source-backed Excel tables. Sparse AL:/CU: labels follow the start of their group.
Unmapped client/other text is never treated as a material label. Legacy tables
without execution numbers retain their sequence. Editable sources and stored
payloads are not reordered: sorting applies when rendering the generated list.

Verification: six regression tests cover numeric 1/2/10 ordering, both materials,
subtotal positions, labels, unknown columns, complete product notes, source
immutability, legacy inputs and standard/source PNGs in both themes with and without
status. A real browser export was compared byte-for-byte with the verified PNG.
