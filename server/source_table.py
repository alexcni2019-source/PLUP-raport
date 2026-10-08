"""Lossless, bounded source tables retained with a report's JSON payload."""
import json
from datetime import date

FIELDS = {
 'plan': {'material','client','product','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','notes'},
 'forecast': {'material','product','km','tons','client','measure','status','notes'},
 'report': {'date','al','cu','backlogAl','backlogCu','wasteAl','wasteCu','op_asumreal','op_status','op_plan','op_previz','op_backal','op_backcu','op_rigid1','op_rigid2','op_rigid3','op_multi1','op_multi2','op_niehoff','op_beta3','op_stocal','op_stoccu','obs'},
}

def validate(table, mode):
 if not isinstance(table,dict) or set(table)!={'version','header','rows','columns','records','date'} or table['version']!=1:
  raise ValueError('Structura tabelului sursă este invalidă.')
 rows=table['rows']
 if not isinstance(rows,list) or not 1<=len(rows)<=500 or any(not isinstance(r,list) or len(r)>40 for r in rows):
  raise ValueError('Tabelul poate avea maximum 500 rânduri și 40 coloane.')
 width=max(map(len,rows))
 if not width or type(table['header']) is not int or not 0<=table['header']<len(rows):raise ValueError('Antet invalid.')
 if any(not isinstance(v,str) or len(v)>1000 or any(ord(c)<32 and c not in '\n\r\t' for c in v) for r in rows for v in r):
  raise ValueError('O celulă din tabel conține text invalid sau depășește 1000 caractere.')
 if len(json.dumps(table,ensure_ascii=False).encode())>600000:raise ValueError('Tabel prea mare. Copiază doar zona raportului.')
 key=mode if mode in ('plan','forecast') else 'report'
 columns=table['columns']
 if not isinstance(columns,dict) or set(columns)-FIELDS[key] or any(type(c) is not int or not 0<=c<width for c in columns.values()):raise ValueError('Asociere de coloane invalidă.')
 if len(set(columns.values()))!=len(columns):raise ValueError('O coloană este asociată de două ori.')
 records=table['records']
 if not isinstance(records,list) or len(records)>(100 if key!='report' else 3):raise ValueError('Prea multe rânduri asociate.')
 used=set()
 for rec in records:
  expected={'row','material'} if key!='report' else {'row','day'}
  if not isinstance(rec,dict) or set(rec)!=expected or type(rec['row']) is not int or not table['header']<rec['row']<len(rows) or rec['row'] in used:raise ValueError('Rând asociat invalid.')
  used.add(rec['row'])
  if key!='report' and rec['material'] not in ('AL','CU'):raise ValueError('Material invalid.')
  if key=='report' and (type(rec['day']) is not int or not 0<=rec['day']<(3 if mode=='weekend' else 1)):raise ValueError('Zi asociată invalidă.')
 if not isinstance(table['date'],str) or not 2020<=date.fromisoformat(table['date']).year<=2100:raise ValueError('Data tabelului este invalidă.')
 return table

def split(payload):
 if not isinstance(payload,dict) or 'sourceTable' not in payload:return payload,None
 table=validate(payload['sourceTable'],payload.get('mode'))
 return {k:v for k,v in payload.items() if k!='sourceTable'},table

def attach(report,table):
 if table is not None:report['sourceTable']=table
 return report
