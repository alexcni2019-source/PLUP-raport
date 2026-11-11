"""Resolve explicit AL/CU sections without guessing from cable or client names."""
import re
import unicodedata

def normalized(value):
    return re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', str(value)).encode('ascii','ignore').decode().lower()).strip()

def marker(value, subtotal=False):
    value=normalized(value)
    if subtotal:
        if not value.startswith('total '):return None
        value=value[6:]
    elif value.startswith('total '):return None
    value=re.sub(r'^(?:material|metal|produse|sectiune|rubrica)\s+','',value)
    value=re.sub(r'\s+(?:tone|tona|t|km)$','',value)
    if value in ('al','aluminiu','aluminium','al aluminiu','aluminiu al'):return 'AL'
    if value in ('cu','cupru','copper','cu cupru','cupru cu'):return 'CU'
    return None

def row_marker(row,columns,is_record=False):
    material=columns.get('material')
    if material is not None and material<len(row) and marker(row[material]):return marker(row[material])
    populated=[cell for cell in row if str(cell).strip()]
    if len(populated)==1:return marker(populated[0])
    # Section labels may occupy an unnamed column, not necessarily column A.
    product=columns.get('product',len(row))
    for i,cell in enumerate(row[:product]):
        if i not in columns.values() and marker(cell):return marker(cell)
    if not is_record:
        labels={marker(cell) for cell in row if marker(cell)}
        if len(labels)==1 and all(not str(cell).strip() or marker(cell) for cell in row):return labels.pop()
    return None

def classify(table,use_fallback=True):
    records={record['row']:record for record in table['records']}
    result={};pending=[];context=None
    def finish(subtotal=None):
        for row,explicit in pending:
            if explicit and subtotal and explicit!=subtotal:
                raise ValueError(f'Rândul {row+1}: materialul contrazice subtotalul {subtotal}. Verifică rubrica din tabel.')
            result[row]=explicit or subtotal or (records[row]['material'] if use_fallback else None)
        pending.clear()
    for i,row in enumerate(table['rows'][table['header']+1:],table['header']+1):
        totals={marker(cell,True) for cell in row if marker(cell,True)}
        if len(totals)>1:raise ValueError(f'Rândul {i+1}: subtotal de material ambiguu.')
        if totals:
            finish(totals.pop());context=None;continue
        material=row_marker(row,table['columns'],i in records)
        if material and material!=context:
            finish();context=material
        if i in records:pending.append((i,material or context))
    finish()
    return result

def repair(payload):
    if not isinstance(payload,dict) or payload.get('mode') not in ('plan','forecast') or not payload.get('sourceTable'):return payload
    table=payload['sourceTable']
    from server.source_table import validate
    validate(table,payload['mode'])
    if len(payload.get('rows',[]))!=len(table['records']):return payload
    resolved=classify(table)
    records=[{**record,'material':resolved[record['row']]} for record in table['records']]
    rows=[{**row,'material':record['material']} for row,record in zip(payload['rows'],records)]
    return {**payload,'rows':rows,'sourceTable':{**table,'records':records}}
