"""Lay out imported forecast totals without changing the saved spreadsheet."""
from decimal import Decimal
import re

from server.materials import marker, normalized, row_marker


AMOUNT = re.compile(r'(\d{1,7}(?:[.,]\d{1,12})?)\s*(tone?|tonă|t|km)?', re.I)
TONS_HEADERS = {'tone', 'tona', 't', 'cantitate tone', 'cantitate t'}
TOTAL_LABELS = {'TOTAL AL': 'AL', 'TOTAL CU': 'CU', 'TOTAL AL + CU': 'all'}


def tonnage_column(table, headings):
    if 'tons' in table['columns']:
        return table['columns']['tons']
    mapped = table['columns'].values()
    candidates = [i for i, value in enumerate(headings)
                  if i not in mapped and normalized(value) in TONS_HEADERS]
    return candidates[0] if len(candidates) == 1 else None


def total_label(value):
    label = re.split(r'[:=]', value, maxsplit=1)[0]
    material = marker(label, subtotal=True)
    if material:
        return material
    if normalized(label) in ('total', 'total general', 'total al cu', 'total tone', 'total previz'):
        return 'all'
    return None


def amount_text(amount):
    text = format(amount, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text.replace('.', ',')


def _text_amount(value):
    match = AMOUNT.fullmatch(value.strip())
    if match and (match[2] or '').lower() != 'km':
        return Decimal(match[1].replace(',', '.'))
    return None


def aligned_tonnage(rows, table, col):
    """Align legacy totals and derive trusted totals from the displayed product rows."""
    records = {record['row']: record['material'] for record in table['records']}
    groups = {'AL': [], 'CU': [], 'all': []}
    total_rows = {}
    incomplete = False
    header = table['header']
    product = table['columns'].get('product')
    for index, row in enumerate(rows[header + 1:], header + 1):
        labels = [(i, kind) for i, value in enumerate(row) if (kind := total_label(value))]
        if labels and index not in records:
            total_rows[index] = labels[0]
        elif index in records:
            value = row[col] if col < len(row) else ''
            entry = (index, value, _text_amount(value))
            groups[records[index]].append(entry)
            groups['all'].append(entry)
        elif product is not None and product < len(row) and row[product].strip() and not row_marker(row, table['columns']):
            # A product outside the reviewed mapping might contribute to the total.
            incomplete = True

    amounts = {}
    for kind, entries in groups.items():
        known = [amount for _, _, amount in entries if amount is not None]
        if known and not incomplete and all(
            amount is not None or value.strip() in ('', '-', '—', '–')
            for _, value, amount in entries
        ):
            amounts[kind] = sum(known, Decimal(0))

    existing_groups = {group for _, group in total_rows.values()}
    insert_after = {}
    for title, kind in TOTAL_LABELS.items():
        if kind in amounts and kind not in existing_groups:
            anchor = groups[kind][-1][0]
            if kind == 'all':
                anchor = max(anchor, *total_rows) if total_rows else anchor
            insert_after.setdefault(anchor, []).append((title, kind))

    result = []
    for index, original in enumerate(rows):
        if index in total_rows:
            label_col, kind = total_rows[index]
            row = list(original) + [''] * max(0, col + 1 - len(original))
            explicit = [
                i for i, value in enumerate(row) if i not in (label_col, col)
                and (match := AMOUNT.fullmatch(value.strip())) and match[2]
                and match[2].lower() != 'km'
            ]
            embedded = re.split(r'[:=]', row[label_col], maxsplit=1)
            embedded_value = _text_amount(embedded[1]) if len(embedded) == 2 else None
            current = row[col]
            if col != label_col and (not current.strip() or _text_amount(current) is not None):
                if kind in amounts:
                    row[col] = amount_text(amounts[kind])
                elif not current.strip() and len(explicit) == 1:
                    row[col] = row[explicit[0]]
                elif not current.strip() and embedded_value is not None:
                    row[col] = amount_text(embedded_value)
                if row[col].strip():
                    if len(explicit) == 1:
                        row[explicit[0]] = ''
                    # A legacy row can have an unlabelled, duplicated tonnage.
                    # Keep a numeric KM subtotal and unrelated source values.
                    if not current.strip() and kind in amounts and not explicit:
                        duplicates = [i for i, value in enumerate(row)
                                      if i not in (label_col, col, table['columns'].get('km'))
                                      and _text_amount(value) == amounts[kind]]
                        if len(duplicates) == 1:
                            row[duplicates[0]] = ''
                    if embedded_value is not None:
                        row[label_col] = embedded[0]
            result.append(row)
        else:
            result.append(original)
        for title, kind in insert_after.get(index, ()):
            label_col = product if product is not None else (0 if col != 0 else 1)
            row = [''] * (max(label_col, col) + 1)
            row[label_col] = title
            row[col] = amount_text(amounts[kind])
            result.append(row)
    return result
