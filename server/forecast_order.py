"""Execution order for forecast exports, without rewriting the imported source."""
import re
from server.materials import marker, normalized


def order_key(value):
    value = str(value or '').strip()
    return (0, int(value)) if re.fullmatch(r'[1-9]\d{0,2}', value) else (1, 0)


def products(rows):
    """Stable numeric ordering; legacy rows without an order retain their sequence."""
    return sorted(rows, key=lambda row: order_key(row.get('order')))


def source_rows(table):
    rows = table['rows']
    headings = rows[table['header']]
    columns = table['columns']
    order = columns.get('order')
    if order is None:
        candidates = [i for i, name in enumerate(headings)
                      if normalized(name) in ('ordine', 'ordine de executie', 'ordine executie', 'pozitie')]
        if len(candidates) != 1:
            return rows
        order = candidates[0]
    records = {record['row']: record for record in table.get('records', [])}
    view = list(rows)
    group = []

    def flush():
        if len(group) > 1:
            selected = sorted(group, key=lambda ri: order_key(rows[ri][order] if order < len(rows[ri]) else ''))
            for destination, original in zip(group, selected):
                view[destination] = list(rows[original])
            # An AL:/CU: section label belongs at the start of the material group,
            # rather than following whichever product originally occupied that row.
            material = records[group[0]]['material']
            label_columns = {
                i for i in range(columns.get('product', 0))
                if i not in columns.values() and
                (not headings[i].strip() or normalized(headings[i]) in ('material', 'metal', 'al cu'))
            }
            if 'material' in columns:
                label_columns.add(columns['material'])
            for col in label_columns:
                cells = [rows[ri][col] if col < len(rows[ri]) else '' for ri in group]
                labelled = [cell for cell in cells if marker(cell) == material]
                if len(labelled) != 1 or not all(not cell.strip() or marker(cell) == material for cell in cells):
                    continue
                for ri in group:
                    if col < len(view[ri]) and marker(view[ri][col]) == material:
                        view[ri][col] = ''
                while len(view[group[0]]) <= col:
                    view[group[0]].append('')
                view[group[0]][col] = labelled[0]
        group.clear()

    for ri in range(table['header'] + 1, len(rows)):
        if ri in records:
            if group and records[group[0]]['material'] != records[ri]['material']:
                flush()
            group.append(ri)
        elif any(cell.strip() for cell in rows[ri]):
            # Keep subtotals, captions and other structural rows in their places.
            flush()
    flush()
    return view
