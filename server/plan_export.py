"""Plan exports from validated rows and the original spreadsheet cells."""
from datetime import date
from decimal import Decimal
from itertools import groupby
import re

from PIL import Image, ImageDraw

from server.export_marks import numeric
from server.km_completion import highlighted, norm
from server.render import font, png, wrapped
from server.source_render import MAX_PIXELS, SourceRenderError


METAL = ('AL', 'CU')
MATERIAL = {'AL': 'Aluminiu', 'CU': 'Cupru'}
LABELS = {
    'client': ('Comandă', 'Client'), 'product': ('Comandă', 'Produs'),
    'planned': ('Metal (t)', 'Planificat'), 'handed': ('Metal (t)', 'Predat'),
    'wire': ('Metal (t)', 'Sârmă'), 'spool': ('Metal (t)', 'Liță'),
    'bar': ('Stoc pe flux (km)', 'Bară / funie'), 'rope': ('Stoc pe flux (km)', 'Funie'),
    'vane': ('Stoc pe flux (km)', 'Vane'), 'cable': ('Stoc pe flux (km)', 'Cablat'),
    'mi': ('Stoc pe flux (km)', 'M.I.'), 'armored': ('Stoc pe flux (km)', 'Armat'),
    'mf': ('Stoc pe flux (km)', 'M.F.'), 'goods': ('Livrare (km)', 'Marfă predată'),
    'started': ('Livrare (km)', 'Porniți'), 'delivered': ('Livrare (km)', 'Predați'),
    'remaining': ('Livrare (km)', 'Rest de predat'), 'notes': ('', 'Observații'),
}
ALIASES = {
    'client': 'client', 'produs': 'product', 'metal planificat tone': 'planned',
    'metal predat tone': 'handed', 'sarma tone': 'wire', 'stoc lita tone': 'spool',
    'stoc bara re se km': 'bar', 'stoc bara km': 'bar', 'stoc funie km': 'rope',
    'stoc fune bara km': 'bar', 'stoc funie bara km': 'bar',
    'stoc vane km': 'vane', 'stoc cablat km': 'cable', 'stoc m i km': 'mi',
    'stoc armat km': 'armored', 'stoc armati km': 'armored', 'stoc m f km': 'mf',
    'marfa predata km': 'goods', 'km porniti': 'started', 'km pornit': 'started',
    'kilometri porniti': 'started', 'km predati': 'delivered', 'km predat': 'delivered',
    'kilometri predati': 'delivered', 'rest de predat km': 'remaining',
    'rest km': 'remaining', 'observatii': 'notes',
}
DATE_TITLE = re.compile(r'\d{1,2}[./]\d{1,2}[./]\d{4}\s*[-–·:]?\s*PLAN(?:\s+W[K]?\s*\d{1,2})?', re.I)
SOURCE_REST = re.compile(r'^\s*REST\s+DE\s+PREDAT(?:\s*\((?:TONE|T)\))?\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:TONE|T)\s*$', re.I)


def displayed(value):
    if isinstance(value, Decimal):
        fixed = format(value, 'f')
        value = fixed.rstrip('0').rstrip('.') if '.' in fixed else fixed
    return str(value).replace('.', ',') if numeric(value) else str(value)


def manual_source(plan):
    keys = ('client', 'product', 'planned', 'handed', 'wire', 'spool', 'bar', 'vane', 'cable', 'mi', 'armored', 'mf', 'goods', 'notes')
    rows = [[LABELS[key][1] for key in keys]]
    records = []
    for material in METAL:
        for row in plan['rows']:
            if row['material'] != material:
                continue
            records.append({'row': len(rows), 'material': material})
            rows.append([displayed(row[key]) if row[key] else '' for key in keys])
        totals = plan['totals'][material]
        rows.append(['TOTAL '+material, '', *[displayed(totals[key]) for key in ('planned', 'handed', 'wire')]])
    rows.append(['TOTAL GENERAL', '', *[displayed(sum(plan['totals'][m][key] for m in METAL)) for key in ('planned', 'handed', 'wire')]])
    if plan['incoming']:
        rows.append(['INTRĂRI METAL', '', displayed(plan['incoming'])])
    return {'header': 0, 'rows': rows, 'columns': dict(zip(keys, range(len(keys)))), 'records': records}


def row_kind(row):
    return norm(' '.join(row[:3]))


def table_image(plan, palette, with_brand=True, stamp=None):
    from server.corporate import brand
    source = plan.get('sourceTable') or manual_source(plan)
    rows, header = source['rows'], source['header']
    measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    widths, keys, labels, groups = [], [], [], []
    source_keys = {index: key for key, index in source['columns'].items()}
    for index in range(max(map(len, rows))):
        value = rows[header][index] if index < len(rows[header]) else ''
        original = norm(value)
        key = ALIASES.get(original, source_keys.get(index))
        group, label = LABELS.get(key, ('', value))
        # A mapped column can still have additional source wording worth keeping.
        if plan.get('sourceTable') and original not in ALIASES:
            label = value
            if key not in ('client', 'product', 'notes'):
                group = ''
        if key == 'bar' and original == 'stoc bara re se km':
            label = 'Bară RE / SE'
        elif key == 'bar' and original == 'stoc bara km':
            label = 'Bară'
        keys.append(key)
        labels.append(label)
        groups.append(group)
        widths.append({'material': 96, 'client': 200, 'product': 385, 'notes': 370,
                       'planned': 133, 'remaining': 137}.get(key, 190 if label and key is None else 105 if label else 60))
    width = max(1672, sum(widths) + 60)
    if width > sum(widths) + 60:
        widths[keys.index('product') if 'product' in keys else 0] += width - sum(widths) - 60

    highlights = highlighted(source)
    material_by_row = {item['row']: item['material'] for item in source.get('records', [])}
    layouts = []
    captions = []
    current_material = None
    for index, row in enumerate(rows):
        if index == header:
            continue
        nonempty = [cell for cell in row if cell.strip()]
        if index < header and (not nonempty or (with_brand and len(nonempty) == 1 and DATE_TITLE.fullmatch(nonempty[0].strip()))):
            continue
        if index < header and len(nonempty) == 1:
            captions.extend(wrapped(measure, nonempty[0], 24, width - 86))
            continue
        kind = row_kind(row)
        total = kind.startswith(('total', 'intrari'))
        material = material_by_row.get(index)
        if material is None and row:
            token = norm(row[source['columns'].get('material', 0)]) if source['columns'].get('material', 0) < len(row) else ''
            if token.upper() in METAL:
                material = token.upper()
        material_start = material if material and material != current_material else None
        if material:
            current_material = material
        marked = highlights.get(index, set())
        cells = []
        for col, cell in enumerate(row):
            if not cell.strip():
                continue
            cell = displayed(cell)
            bold = total or keys[col] in ('product', 'remaining') or col in marked
            span = widths[col]
            if total and not numeric(cell):
                next_used = next((j for j in range(col+1, len(row)) if row[j].strip()), len(widths))
                span = sum(widths[col:next_used])
            lines = wrapped(measure, cell, 24, span - 24, bold)
            cells.append((col, span, lines, bold, numeric(cell)))
        note = bool(marked and 'remaining' in keys)
        height = max(55, 20 + max((len(cell[2]) for cell in cells), default=1)*31 + (19 if note else 0))
        layouts.append((index, kind, total, material_start, marked, cells, height, note))

    heads = [wrapped(measure, label, 22, column-12, True) if label.strip() else [] for label,column in zip(labels,widths)]
    header_height = 22 + max(map(len,heads), default=1)*27
    group_runs = []
    for group, run in groupby(enumerate(groups), key=lambda pair: pair[1]):
        indexes = [index for index,_ in run]
        start_col, end_col = indexes[0], indexes[-1]+1
        span = sum(widths[start_col:end_col])
        lines = wrapped(measure, group, 21, span-14, True) if group else []
        group_runs.append((group,start_col,end_col,lines))
    group_height = 16 + 25*max((len(lines) for _,_,_,lines in group_runs),default=0) if any(groups) else 0
    start = 102 if with_brand else 20
    caption_height = 20 + 31*len(captions) if captions else 0
    height = start + caption_height + group_height + header_height + sum(h+(40 if m else 0) for _,_,_,m,_,_,h,_ in layouts) + 75
    if width * height > MAX_PIXELS:
        raise SourceRenderError('Tabelul este prea mare pentru o singură imagine lizibilă. Împarte-l în două rapoarte.')
    image = Image.new('RGB', (width,height), palette['bg'])
    d = ImageDraw.Draw(image)
    if with_brand:
        title = ('PLAN '+plan.get('week','').upper()).strip()
        brand(d, width, stamp or date.fromisoformat(plan['date']).strftime('%d.%m.%Y'), title, palette)

    xs = [30]
    for w in widths:
        xs.append(xs[-1]+w)
    y = start
    for index,line in enumerate(captions):
        d.text((width/2,y+10+index*31),line,font=font(24),fill=palette['muted'],anchor='mt')
    y += caption_height
    if group_height:
        for group,first,last,lines in group_runs:
            left, right = xs[first], xs[last]
            d.rectangle((left,y,right,y+group_height), fill=palette['blue'] if group in ('Metal (t)','Livrare (km)') else palette['head'])
            for i,line in enumerate(lines):
                d.text(((left+right)/2,y+group_height/2+(i-(len(lines)-1)/2)*25),line,
                       font=font(21,True),fill=palette['accent'],anchor='mm')
        y += group_height
    d.rectangle((xs[0],y,xs[-1],y+header_height), fill=palette['head'])
    for col,lines in enumerate(heads):
        center = (xs[col]+xs[col+1])/2
        for i,line in enumerate(lines):
            d.text((center,y+header_height/2+(i-(len(lines)-1)/2)*27),line,font=font(22,True),fill=palette['ink'],anchor='mm')
    y += header_height
    for index,kind,total,material,marked,cells,row_height,note in layouts:
        if material:
            d.rectangle((xs[0],y,xs[-1],y+40),fill=palette[material.lower()+'_bg'])
            d.text((xs[0]+12,y+20),material+' · '+MATERIAL[material],font=font(24,True),
                   fill=palette[material.lower()],anchor='lm')
            y += 40
        fill = palette['stripe'] if index%2 else palette['paper']
        if total:
            fill = palette['al_bg'] if kind.startswith('total al') and not kind.startswith('total al cu') else palette['cu_bg'] if kind.startswith('total cu') else palette['blue']
        d.rectangle((xs[0],y,xs[-1],y+row_height),fill=fill)
        for col in range(len(widths)):
            if col in marked or (keys[col]=='remaining' and note):
                d.rectangle((xs[col],y,xs[col+1],y+row_height),fill=palette['success_bg'])
            elif keys[col]=='remaining' and index>header and not total:
                d.rectangle((xs[col],y,xs[col+1],y+row_height),fill=palette['blue'])
            if not total and (col==0 or groups[col] != groups[col-1] or keys[col]=='remaining'):
                d.line((xs[col],y,xs[col],y+row_height),fill=palette['line'],width=2)
        for col,span,lines,bold,is_number in cells:
            anchor = 'rt' if is_number else 'lt'
            x = xs[col]+span-12 if is_number else xs[col]+12
            color = palette['success'] if col in marked else palette['accent'] if (total and is_number) or keys[col]=='remaining' else palette['ink']
            has_note = note and keys[col]=='remaining'
            top = y + (row_height - len(lines)*31 - (19 if has_note else 0))/2
            for i,line in enumerate(lines):
                d.text((x,top+i*31),line,font=font(24,bold),fill=color,anchor=anchor)
            if has_note:
                d.text((xs[col+1]-12,y+row_height-8),'Toleranță',font=font(16,True),fill=palette['success'],anchor='rb')
        y += row_height
        d.line((xs[0],y,xs[-1],y),fill=palette['line'])
    if 'mi' in keys or 'mf' in keys:
        d.text((30,y+23),'M.I. = manta intermediară  ·  M.F. = manta finală',font=font(21),fill=palette['muted'])
    return image


def overview_image(plan, insights, palette):
    width = 840
    source = plan.get('sourceTable', {})
    source_rows = source.get('rows', [])
    notes = [cell.strip() for row in source_rows[source.get('header',0)+1:]
             if row_kind(row).startswith(('total','intrari')) for cell in row
             if norm(cell).startswith(('stoc ', 'intrari metal')) and ':' in cell]
    provided = {match.group(1).replace(',', '.') for row in source_rows for cell in row
                if (match := SOURCE_REST.fullmatch(cell))}
    remaining = plan.get('remainingTotalOverride')
    remaining_label = 'Valoare introdusă manual' if remaining is not None else 'Din pozițiile rămase deschise'
    if remaining is None and len(provided)==1:
        remaining = Decimal(next(iter(provided)))
        remaining_label = 'Valoare din raportul sursă'
    if remaining is None and insights['by_material']:
        remaining = insights['remaining_total']
    if not notes:
        for key,label in [('bar95','Stoc bară 9,5 mm'),('bar15','Stoc bară 15 mm')]:
            value = plan.get('sectionStock',{}).get(key)
            if value is not None:
                notes.append(label+' · '+displayed(value)+' t')
        if plan.get('incoming'):
            notes.append('Intrări metal · '+displayed(plan['incoming'])+' t')
    measure = ImageDraw.Draw(Image.new('RGB',(1,1)))
    notes_layout = [wrapped(measure,note,31,706) for note in notes]
    groups = [(key, insights['by_material'][key]) for key in METAL if key in insights['by_material']]
    height = 376 + 174*len(groups) + (74+sum(20+42*len(lines) for lines in notes_layout) if notes_layout else 0)
    if height*width>MAX_PIXELS:
        raise SourceRenderError('Sinteza planului depășește dimensiunea maximă a imaginii.')
    image = Image.new('RGB',(width,height),palette['bg'])
    d = ImageDraw.Draw(image)

    def text(x,y,value,size,color=None,bold=False):
        d.text((x,y),value,font=font(size,bold),fill=color or palette['ink'],anchor='lt')

    text(40,36,'NRG Cables · PLUP',34,palette['accent'],True)
    text(40,93,'Plan de producție',52,bold=True)
    stamp = date.fromisoformat(plan['date']).strftime('%d.%m.%Y')
    text(40,161,stamp+('  ·  '+plan['week'].upper() if plan.get('week') else ''),30,palette['muted'])
    d.rounded_rectangle((40,214,800,358),radius=16,fill=palette['hero'])
    text(64,231,'Rest de predat',30,palette['hero_ink'],True)
    text(64,270,displayed(remaining)+' t' if remaining is not None else '—',52,palette['hero_ink'],True)
    if remaining is not None:
        text(64,327,remaining_label,23,palette['hero_ink'])
    y = 376
    for material,data in groups:
        color = palette[material.lower()]
        d.rounded_rectangle((40,y,800,y+154),radius=14,fill=palette[material.lower()+'_bg'])
        text(64,y+15,material+' · '+MATERIAL[material],32,color,True)
        for x,label,key in [(64,'Planificat','planned'),(430,'Predat','handed')]:
            text(x,y+63,label,25,palette['muted'])
            text(x,y+96,displayed(data[key])+' t' if data[key] is not None else '—',40,bold=True)
        y += 174
    if notes_layout:
        text(40,y,'Stoc și intrări',36,bold=True)
        y += 58
        for lines in notes_layout:
            for line in lines:
                text(40,y,line,31)
                y += 42
            d.line((40,y+4,800,y+4),fill=palette['line'])
            y += 20
    return png(image)
