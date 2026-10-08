"""Private product helpers: deterministic checks, drafts and version history."""
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import json
import re

MODES=('weekday','weekend','plan','forecast')

def stamp():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

def bootstrap(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS report_versions (version INTEGER PRIMARY KEY AUTOINCREMENT, report_id TEXT NOT NULL, created_at TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS versions_report ON report_versions(report_id,version DESC)')
    conn.execute('CREATE TABLE IF NOT EXISTS drafts (mode TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL, metadata TEXT NOT NULL)')

def revision(conn,identifier,payload,action):
    cur=conn.execute('INSERT INTO report_versions(report_id,created_at,action,payload) VALUES (?,?,?,?)',(identifier,stamp(),action,json.dumps(payload,ensure_ascii=False)))
    return cur.lastrowid

def latest_version(conn,identifier):
    return conn.execute('SELECT COALESCE(MAX(version),0) FROM report_versions WHERE report_id=?',(identifier,)).fetchone()[0]

def draft_validate(body):
    if not isinstance(body,dict) or set(body)-{'payload','metadata','expected'} or not {'payload','metadata'}<=set(body):raise ValueError('Ciornă invalidă.')
    p=body['payload'];meta=body['metadata']
    if not isinstance(p,dict) or p.get('mode') not in MODES:raise ValueError('Tip de ciornă invalid.')
    if not isinstance(p.get('date'),str) or not 2020<=date.fromisoformat(p['date']).year<=2100:raise ValueError('Data ciornei este invalidă.')
    row_fields={'material','client','product','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','notes'} if p['mode']=='plan' else {'material','product','km','tons','client','measure','status','notes'}
    if p['mode'] in ('plan','forecast'):
        allowed={'mode','date','rows','week','incoming'} if p['mode']=='plan' else {'mode','date','rows'}
        if set(p)!=allowed or not isinstance(p['rows'],list) or len(p['rows'])>100:raise ValueError('Structura ciornei este invalidă.')
        for row in p['rows']:
            if not isinstance(row,dict) or set(row)-row_fields or row.get('material') not in ('AL','CU'):raise ValueError('Rând invalid.')
            for val in row.values():text(val)
        if p['mode']=='plan':text(p['week']);text(p['incoming'])
    else:
        fields={'al','cu','backlogAl','backlogCu','wasteAl','wasteCu','op_asumreal','op_status','op_plan','op_previz','op_backal','op_backcu','op_rigid1','op_rigid2','op_rigid3','op_multi1','op_multi2','op_niehoff','op_beta3','op_stocal','op_stoccu','obs'}
        if set(p)!={'mode','date','values'} or not isinstance(p['values'],dict) or len(p['values'])>3:raise ValueError('Structura ciornei este invalidă.')
        start=date.fromisoformat(p['date'])
        if p['mode']=='weekend' and start.weekday()!=4:raise ValueError('Raportul de 3 zile începe vineri.')
        allowed={(start+timedelta(days=i)).isoformat() for i in range(3 if p['mode']=='weekend' else 1)}
        for day,values in p['values'].items():
            if day not in allowed:raise ValueError('Ciorna conține date din afara perioadei.')
            if not isinstance(values,dict) or set(values)-fields:raise ValueError('Câmp invalid.')
            for val in values.values():text(val)
    if not isinstance(meta,dict) or set(meta)-{'id','needsReview','review','showStatus','selectedDate','version'}:raise ValueError('Metadate invalide.')
    if meta.get('id') is not None and not re.fullmatch(r'[a-f0-9-]{36}',str(meta['id'])):raise ValueError('Raport invalid.')
    if 'needsReview' in meta and not isinstance(meta['needsReview'],bool):raise ValueError('Confirmare invalidă.')
    if 'showStatus' in meta and not isinstance(meta['showStatus'],bool):raise ValueError('Opțiune invalidă.')
    if meta.get('version') is not None and (type(meta['version']) is not int or meta['version']<0):raise ValueError('Versiune invalidă.')
    review=meta.get('review',[])
    if not isinstance(review,list) or len(review)>1500 or any(not isinstance(v,str) or not re.fullmatch(r'\d{1,3}:[a-zA-Z]+',v) for v in review):raise ValueError('Verificări invalide.')
    if meta.get('selectedDate'):date.fromisoformat(meta['selectedDate'])
    return p,meta

def text(val):
    if not isinstance(val,str) or len(val)>120 or any(ord(c)<32 for c in val):raise ValueError('Text invalid în ciornă.')

def draft_save(conn,body):
    p,meta=draft_validate(body);updated=stamp()
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        current=conn.execute('SELECT updated_at FROM drafts WHERE mode=?',(p['mode'],)).fetchone()
        if 'expected' in body and body['expected']!=(current['updated_at'] if current else None):raise ValueError('Ciorna a fost modificată pe alt dispozitiv. Copia locală este păstrată; reîncarcă lista de ciorne.')
        conn.execute('INSERT INTO drafts VALUES (?,?,?,?) ON CONFLICT(mode) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload,metadata=excluded.metadata',(p['mode'],updated,json.dumps(p,ensure_ascii=False),json.dumps(meta)))
    return {'updated_at':updated}

def number(value):
    try:return Decimal(str(value or '0').replace(',','.'))
    except Exception:return Decimal(0)

def checks(payload,validate,conn=None):
    report=validate(payload);warnings=[];mode=report['mode']
    def add(message,field=''):warnings.append({'message':message,'field':field})
    if date.fromisoformat(report['date'])>datetime.now(ZoneInfo("Europe/Bucharest")).date():add('Data este în viitor. Verifică dacă acesta este raportul dorit.','date')
    if mode in ('weekday','weekend'):
        for day in report['days']:
            prefix=day['date']+': '
            for metal,back in [('al','backlogAl'),('cu','backlogCu')]:
                if day['values'][back]>day['values'][metal]:add(prefix+'Backlogul depășește cantitatea predată pentru '+('aluminiu.' if metal=='al' else 'cupru.'),back)
            if day['percent']>5:add(prefix+'Deșeul depășește 5% din materialul procesat. Prag orientativ, nu limită aprobată de producție.','wasteAl')
            raw=payload['values'].get(day['date'],{})
            if not any(str(raw.get(k,'')).strip() for k in ('al','cu','wasteAl','wasteCu')):add(prefix+'Cantitățile principale nu sunt completate.')
        totals=report['total'];summary=f"Predat: {totals['handed']} t; backlog: {totals['backlog']} t; procesat: {totals['processed']} t; deșeu: {totals['waste']} t ({totals['percent']:.2f}%)."
        if totals['handed']:summary+=f" Backlogul reprezintă {totals['backlog']/totals['handed']*100:.2f}% din totalul predat."
        if conn is not None:
            plans=[]
            for day in report['days']:
                saved=conn.execute("SELECT payload FROM reports WHERE mode='plan' AND report_date=? ORDER BY created_at DESC,id DESC LIMIT 1",(day['date'],)).fetchone()
                if not saved:break
                plan=validate(json.loads(saved['payload']));plans.append(sum(t['planned'] for t in plan['totals'].values()))
            if len(plans)==len(report['days']) and sum(plans)>0:
                planned=sum(plans);summary+=f" Față de planurile salvate pentru aceleași zile: {planned} t planificate, {totals['handed']/planned*100:.2f}% realizat, diferență predat − plan {totals['handed']-planned} t."

    else:
        seen=set()
        for i,row in enumerate(payload['rows']):
            product=row.get('product','').strip();key=(row['material'],product,row.get('client','').strip())
            if not product:add(f'Rândul {i+1}: produsul lipsește.','product')
            elif key in seen:add(f'Rândul {i+1}: aceeași combinație produs/client apare de mai multe ori. Verifică dacă este intenționat.','product')
            seen.add(key)
            amount=('planned','handed') if mode=='plan' else ('km','tons')
            if product and not any(str(row.get(k,'')).strip() for k in amount):add(f'Rândul {i+1}: produsul nu are cantități completate.',amount[0])
            if mode=='plan' and number(row.get('handed'))>number(row.get('planned')):add(f'Rândul {i+1}: metalul predat depășește planul.','handed')
        if mode=='plan':
            planned=sum(t['planned'] for t in report['totals'].values());handed=sum(t['handed'] for t in report['totals'].values())
            summary=f"Plan: {planned} t; predat: {handed} t; diferență predat − plan: {handed-planned} t."
            if planned:summary+=f' Realizat: {handed/planned*100:.2f}% din plan.'
        else:
            tons=sum(t['tons'] for t in report['totals'].values());km=sum(t['km'] for t in report['totals'].values())
            summary=f"Previz: {len(report['rows'])} produse, {tons} t și {km} km. Stadiile sunt cele completate în formular."
    return {'warnings':warnings,'summary':summary,'basis':'Rezumat calculat din valorile formularului. Nu include explicații sau cauze deduse.'}

def dashboard(conn,end,days,validate):
    finish=date.fromisoformat(end)
    if not 2020<=finish.year<=2100:raise ValueError('Data invalidă.')
    start=finish-timedelta(days=days-1);prior=start-timedelta(days=days)
    records=conn.execute("SELECT *,COALESCE((SELECT MAX(created_at) FROM report_versions v WHERE v.report_id=reports.id),created_at) AS updated_at FROM reports ORDER BY updated_at,id").fetchall()
    daily={};catalog={};recent=[]
    for record in records:
        p=json.loads(record['payload']);recent.append({'id':record['id'],'mode':record['mode'],'date':record['report_date'],'updated_at':record['updated_at']})
        if record['mode'] in ('plan','forecast'):
            for row in p.get('rows',[]):
                if row.get('product','').strip():
                    key=(row['material'],row['product'].strip(),row.get('client','').strip())
                    previous=catalog.get(key,{})
                    catalog[key]={'material':key[0],'product':key[1],'client':key[2],'measure':row.get('measure',previous.get('measure','')),'date':record['report_date'],'report_id':record['id']}
        if record['mode'] not in ('weekday','weekend'):continue
        try:result=validate(p)
        except ValueError:continue
        for d in result['days']:
            if prior<=date.fromisoformat(d['date'])<=finish:
                raw=p.get('values',{}).get(d['date'],{})
                filled=any(str(raw.get(k,'')).strip() for k in ('al','cu','backlogAl','backlogCu','wasteAl','wasteCu'))
                daily[d['date']]=d if filled else None
    def total(lo,hi):
        parts=[d for day,d in daily.items() if d is not None and lo<=date.fromisoformat(day)<=hi]
        sums={k:sum((d[k] for d in parts),Decimal(0)) for k in ('handed','backlog','waste','processed')};sums['percent']=sums['waste']/sums['processed']*100 if sums['processed'] else Decimal(0);sums['count']=len(parts);return sums
    current=total(start,finish);previous=total(prior,start-timedelta(days=1))
    series=[{'date':(start+timedelta(days=i)).isoformat(),**({k:daily[(start+timedelta(days=i)).isoformat()][k] for k in ('handed','backlog','waste','percent')} if daily.get((start+timedelta(days=i)).isoformat()) is not None else {'handed':None,'backlog':None,'waste':None,'percent':None})} for i in range(days)]
    return {'current':current,'previous':previous,'series':series,'recent':list(reversed(recent))[:8],'today':[r for r in reversed(recent) if r['date']==end][:4],'catalog':list(catalog.values())[-1000:],'start':start.isoformat(),'end':end,'note':'O singură înregistrare per zi: ultima versiune salvată, fără dublarea rapoartelor zilnice și de weekend. Zilele fără raport sunt marcate ca lipsă.'}
