"""Portable validated backups, consistent SQLite snapshots and atomic data restore."""
import csv,hashlib,io,json,sqlite3,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
TABLES={'reports':['id','mode','report_date','created_at','payload'],'report_defaults':['mode','payload'],'plan_snapshots':['report_date','payload'],'report_versions':['version','report_id','created_at','action','payload'],'drafts':['mode','updated_at','payload','metadata']}

def snapshot(conn):
 conn.execute('BEGIN')
 try:return {'format':'plup-backup','version':1,'tables':{t:[dict(zip(cols,row)) for row in conn.execute('SELECT '+','.join(cols)+' FROM '+t+' ORDER BY '+cols[0])] for t,cols in TABLES.items()}}
 finally:conn.rollback()
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate(data,validator):
 if not isinstance(data,dict) or data.get('format')!='plup-backup' or data.get('version')!=1 or set(data.get('tables',{}))!=set(TABLES):raise ValueError('Backup PLUP incompatibil.')
 for table,cols in TABLES.items():
  rows=data['tables'][table]
  if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Prea multe înregistrări.')
  keys=set()
  for row in rows:
   if not isinstance(row,dict) or set(row)!=set(cols):raise ValueError('Structură invalidă: '+table)
   key=row[cols[0]]
   if key in keys:raise ValueError('Înregistrări duplicate: '+table)
   keys.add(key)
   for col,value in row.items():
    if col=='version':
     if type(value) is not int or value<=0:raise ValueError('Versiune invalidă.')
    elif not isinstance(value,str) or len(value)>1048576:raise ValueError('Valoare invalidă.')
   if 'payload' in row:
    payload=json.loads(row['payload'])
    if not isinstance(payload,dict):raise ValueError('Date raport invalide.')
    if table in ('reports','report_defaults','plan_snapshots','report_versions'):validator(payload)
   if table=='drafts':
    if row['mode'] not in ('weekday','weekend','plan','forecast') or not isinstance(json.loads(row['metadata']),dict):raise ValueError('Ciornă invalidă.')
   if table=='reports' and (row['mode']!=payload.get('mode') or row['report_date']!=payload.get('date')):raise ValueError('Metadate raport incompatibile.')
 ids={r['id'] for r in data['tables']['reports']}
 if any(r['report_id'] not in ids for r in data['tables']['report_versions']):raise ValueError('Istoric fără raport asociat.')
 return data

def preview(conn,data):
 current=snapshot(conn);existing={r['id']:r for r in current['tables']['reports']};incoming=data['tables']['reports']
 return {'counts':{t:len(rows) for t,rows in data['tables'].items()},'add':sum(r['id'] not in existing for r in incoming),'duplicates':sum(existing.get(r['id'])==r for r in incoming),'conflicts':sum(r['id'] in existing and existing[r['id']]!=r for r in incoming),'expected':digest(current),'backupHash':digest(data)}

def sqlite_bytes(conn):
 with tempfile.TemporaryDirectory() as folder:
  path=Path(folder)/'backup.sqlite3';dest=sqlite3.connect(path)
  try:conn.backup(dest)
  finally:dest.close()
  return path.read_bytes()

def csv_bytes(conn):
 data=snapshot(conn);out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
  for table,cols in TABLES.items():
   stream=io.StringIO();writer=csv.writer(stream);writer.writerow(cols)
   for row in data['tables'][table]:writer.writerow([("'"+row[c]) if isinstance(row[c],str) and row[c].lstrip().startswith(('=','+','-','@')) else row[c] for c in cols])
   archive.writestr(table+'.csv',stream.getvalue().encode('utf-8-sig'))
 return out.getvalue()

def restore(conn,data,action,expected,db_path):
 if action not in ('restore','merge'):raise ValueError('Acțiune invalidă.')
 # Backup before any mutation; never overwrite the live SQLite file.
 backup=sqlite_bytes(conn);folder=Path(db_path).parent/'backups';folder.mkdir(exist_ok=True)
 path=folder/('before-import-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3');path.write_bytes(backup);path.chmod(0o600)
 conn.execute('BEGIN IMMEDIATE')
 try:
  current={'format':'plup-backup','version':1,'tables':{t:[dict(zip(cols,row)) for row in conn.execute('SELECT '+','.join(cols)+' FROM '+t+' ORDER BY '+cols[0])] for t,cols in TABLES.items()}}
  if digest(current)!=expected:raise ValueError('Datele s-au schimbat. Verifică backupul din nou înainte de import.')
  if action=='restore':
   for t in reversed(TABLES):conn.execute('DELETE FROM '+t)
   for t,cols in TABLES.items():
    conn.executemany('INSERT INTO '+t+' ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[[r[c] for c in cols] for r in data['tables'][t]])
   added=len(data['tables']['reports'])
  else:
   existing={r['id'] for r in current['tables']['reports']};new={r['id'] for r in data['tables']['reports'] if r['id'] not in existing};cols=TABLES['reports']
   conn.executemany('INSERT INTO reports VALUES (?,?,?,?,?)',[[r[c] for c in cols] for r in data['tables']['reports'] if r['id'] in new])
   for r in data['tables']['report_versions']:
    if r['report_id'] in new:conn.execute('INSERT INTO report_versions (report_id,created_at,action,payload) VALUES (?,?,?,?)',tuple(r[c] for c in ['report_id','created_at','action','payload']))
   added=len(new)
  conn.commit();return {'added':added,'safetyBackup':path.name}
 except Exception:conn.rollback();raise
