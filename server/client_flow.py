"""Experimental per-client stage amounts; estimate metal per product."""
from decimal import Decimal
from server.km_completion import columns,number,highlighted
from server.plan_analysis import STAGES
from server.product_sections import metal_per_km

def build(plan,payload):
 source=plan.get('sourceTable') or payload.get('sourceTable');groups={}
 pair=columns(source['rows'][source['header']]) if source else (None,None)
 records=source.get('records',[]) if source else []
 closed=highlighted(source) if source else {}
 for i,row in enumerate(plan['rows']):
  if i<len(records) and records[i]['row'] in closed:continue
  name=row['client'].strip()
  if not name:continue
  raw=payload['rows'][i];cells=source['rows'][records[i]['row']] if i<len(records) else []
  values=[]
  for field,label in STAGES:
   if field=='goods':continue
   col=source['columns'].get(field) if source else None
   value=number(cells[col]) if col is not None and col<len(cells) else (number(raw.get(field)) if not source else None)
   values.append((field,label,value,'km'))
  for field,label,col in [('started','KM porniți',pair[0]),('delivered','KM predați',pair[1])]:
   values.append((field,label,number(cells[col]) if col is not None and col<len(cells) else None,'km'))
  values.append(('wire','Sârmă',number(raw.get('wire')),'t'))
  if not any(value is not None and value>0 and field!='started' for field,label,value,unit in values):
   key=name.casefold();group=groups.setdefault(key,{'client':name,'stages':{},'warnings':[],'products':[],'allocated':[]})
   group['allocated'].append({'product':row['product'],'material':row['material'],'message':'Metal alocat, dar încă nu s-a pornit trefilarea produsului.'})
   continue
  key=name.casefold();group=groups.setdefault(key,{'client':name,'stages':{},'warnings':[],'products':[],'allocated':[]})
  product={'product':row['product'],'material':row['material'],'stages':[]}
  for field,label,value,unit in values:
   if value is None:continue
   item=group['stages'].setdefault(field,{'label':label,'value':Decimal(0),'unit':unit,'tons':Decimal(0),'estimable':True})
   item['value']+=value
   calculated=None
   if unit=='km':
    ratio=metal_per_km(row['product'],row['material'],field)
    if ratio is None and value>0:
     item['estimable']=False
     group['warnings'].append({'product':row['product'],'stage':label,'row':i+1,'message':'Nu pot calcula tonele: secțiunea produsului sau configurația pentru această etapă nu este recunoscută.'})
    elif ratio is not None:
     calculated=value*ratio;item['tons']+=calculated
   if value>0:product['stages'].append({'label':label,'value':value,'unit':unit,'tons':calculated})
  if product['stages']:group['products'].append(product)
 for group in groups.values():
  group['stages']=[{**v,'tons':v['tons'] if v['unit']=='km' and v.pop('estimable') else None} for v in group['stages'].values()]
 return sorted(groups.values(),key=lambda g:g['client'].casefold())
