"""Plan snapshots: compare identifiable common rows without mixing tonnes and kilometres."""
from collections import Counter
from decimal import Decimal
import json,re

STAGES=[('bar','Funie / bară'),('vane','Vane'),('cable','Cablat'),('mi','Manta intermediară'),('armored','Armat'),('mf','Manta finală'),('goods','Marfă predată')]
ZERO=Decimal('0')

def identity(row):
 return tuple(re.sub(r'\s+',' ',str(row.get(k,'')).strip()).casefold() for k in ('material','client','product'))

def entered(payload,key):
 table=payload.get('sourceTable')
 if table:
  col=table['columns'].get(key)
  return col is not None and any(str(table['rows'][r['row']][col] if col<len(table['rows'][r['row']]) else '').strip() not in ('','-','—') for r in table['records'])
 return any(str(r.get(key,'')).strip() not in ('','-','—') for r in payload['rows'])

def build(plan,payload,previous=None,previous_payload=None):
 from server.source_table import repair_fune
 payload=repair_fune(payload)
 rows=plan['rows'];groups={}
 for material in ('AL','CU'):
  selected=[r for r in rows if r['material']==material]
  groups[material]={key:sum((r[key] for r in selected),ZERO) for key in ('planned','handed')}
 planned=sum((r['planned'] for r in rows),ZERO);handed=sum((r['handed'] for r in rows),ZERO)
 result={'date':plan['date'],'groups':groups,'planned':planned if entered(payload,'planned') else None,'handed':handed if entered(payload,'handed') else None,'percent':handed/planned*100 if planned and entered(payload,'handed') else None,'stages':[{'key':k,'label':label,'current':sum((r[k] for r in rows),ZERO) if entered(payload,k) else None} for k,label in STAGES],'group_present':{m:{k:any(r.get('material')==m and r.get(k) is not None and str(r.get(k,'')).strip() not in ('','-','—') for r in payload['rows']) for k in ('planned','handed')} for m in ('AL','CU')},'comparison':None,'ton_stocks':{k:sum((r[k] for r in rows),ZERO) if entered(payload,k) else None for k in ('wire','spool')}}
 from server.plan_clients import build as client_build
 result['clients']=client_build(plan,payload)
 from server.client_flow import build as flow_build
 result['client_flow']=flow_build(plan,payload)
 from server.client_flow_render import pages
 from server.section_stock import build as stock_build
 result['section_stock']=stock_build(result,plan.get('sectionStock',{}))
 if plan.get('inventory'):
  from server.inventory import summary as inventory_summary
  estimate=stock_build({'client_flow':flow_build(plan,payload,'AL')},{})
  result['section_stock']=inventory_summary(plan['inventory'],estimate,plan['date'],plan['rows'])
  result['section_stock']['planEstimate']=estimate['total']
 result['flow_pages']=[{'client':'Toți clienții','page':0}] if pages(result) else []
 if previous is None:return result
 old=previous['rows'];nc=Counter(identity(r) for r in rows);oc=Counter(identity(r) for r in old)
 current={identity(r):r for r in rows if r['product'].strip() and nc[identity(r)]==1};prior={identity(r):r for r in old if r['product'].strip() and oc[identity(r)]==1}
 common=set(current)&set(prior)
 comparison={'date':previous['date'],'common':len(common),'new':len(set(current)-set(prior)),'missing':len(set(prior)-set(current)),'ambiguous':sum(n for n in nc.values() if n>1)+sum(n for n in oc.values() if n>1),'metrics':[]}
 for key,label,unit in [('handed','Metal predat','t'),('wire','Sârmă','t'),('spool','Lită','t')]+[(k,label,'km') for k,label in STAGES]:
  paired={ident for ident in common if all(any(identity(r)==ident and r.get(key) is not None and str(r.get(key,'')).strip() not in ('','-','—') for r in raw['rows']) for raw in (payload,previous_payload))}
  usable=bool(paired)
  now=sum((current[k][key] for k in paired),ZERO) if usable else None
  before=sum((prior[k][key] for k in paired),ZERO) if usable else None
  comparison['metrics'].append({'label':label,'unit':unit,'current':now,'previous':before,'delta':now-before if usable else None,'positions':len(paired)})
 result['comparison']=comparison;return result

def previous(conn,stamp,validator):
 # Only dates strictly before this plan; never compare to a future or same-day version.
 rows=conn.execute("SELECT report_date,payload,0 AS priority,created_at AS sort_time FROM reports WHERE mode='plan' AND report_date<? UNION ALL SELECT report_date,payload,1 AS priority,'' AS sort_time FROM plan_snapshots WHERE report_date<? ORDER BY report_date DESC,priority DESC,sort_time DESC LIMIT 100",(stamp,stamp))
 for row in rows:
  try:
   payload=json.loads(row['payload']);return validator(payload),payload
  except (ValueError,KeyError,TypeError):continue
 return None,None
