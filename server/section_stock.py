"""Metal physically on flow: process stocks only, plus manual section stocks."""
from decimal import Decimal
from server.render import amount,font,png
from PIL import Image,ImageDraw
PROCESS={'Sârmă','Funie / bară','Vane','Cablat','Manta intermediară','Armat','Manta finală'}

def build(insights,extras):
 rows=[];missing=[]
 for group in insights.get('client_flow',[]):
  total=Decimal(0);present=False;valid=True
  for stage in group['stages']:
   if stage['label'] not in PROCESS or stage['value']<=0:continue
   present=True;tons=stage['value'] if stage['unit']=='t' else stage['tons']
   if tons is None:valid=False;missing.append(group['client']+' · '+stage['label'])
   else:total+=tons
  if present:rows.append({'client':group['client'],'tons':total if valid else None})
 total=sum((r['tons'] for r in rows if r['tons'] is not None),Decimal(0))+sum((v for v in extras.values() if v is not None),Decimal(0))
 return {'clients':rows,'extras':extras,'total':None if missing else total,'missing':missing}

def subtotals(data):
 clients_total=None if any(r['tons'] is None for r in data['clients']) else sum((r['tons'] for r in data['clients']),Decimal(0))
 other_total=sum((v for v in data['extras'].values() if v is not None),Decimal(0))
 return {**data,'clientsTotal':clients_total,'otherTotal':other_total}

def adjust(data,overrides,names=None):
 names=names or {}
 if not overrides and not names:return subtotals(data)
 data={**data,'clients':[{**r} for r in data['clients']],'referenceTotal':data['total']}
 for row in data['clients']:
  original=row['client'];row['sourceClient']=original
  if original in overrides:row['originalTons']=row['tons'];row['tons']=overrides[original]
  if original in names:row['client']=names[original]
 existing={r.get('sourceClient',r['client']) for r in data['clients']}
 for name,value in overrides.items():
  if name not in existing:data['clients'].append({'client':names.get(name,name),'sourceClient':name,'tons':value})
 data['clients']=[r for r in data['clients'] if r['tons'] is None or r['tons']>0]
 missing=[r['client'] for r in data['clients'] if r['tons'] is None]
 data['missing']=missing
 data['total']=None if missing else sum((r['tons'] for r in data['clients']),Decimal(0))+sum((v for v in data['extras'].values() if v is not None),Decimal(0))
 return subtotals(data)

def image(plan,insights,theme):
 from server.corporate import LIGHT,DARK,brand
 p=DARK if theme=='dark' else LIGHT;data=insights.get('section_stock') or build(insights,plan['sectionStock'])
 if data.get('basis')=='inventory':plan={**plan,'date':data['date']}
 if data['missing']:raise ValueError('Nu pot completa tonele pentru: '+', '.join(data['missing'])+'. Verifică denumirile produselor și etapele din plan.')
 data=subtotals(data)
 rows=[(r['client'],r['tons'],'client') for r in data['clients']]+[('TOTAL CLIENȚI',data['clientsTotal'],'subtotal')]
 if data.get('basis')!='inventory':
  rows += [(label,data['extras'].get(key),'manual') for key,label in [('samples','Mostre'),('waste','Deșeu (doar ce e în secție)'),('dead','Stoc „mort”'),('blocked','Semifabricate blocate'),('bar95','Stoc bară 9,5 mm'),('bar15','Stoc bară 15 mm')]]
  rows += [('TOTAL MOSTRE, DEȘEU ȘI ALTE STOCURI',data['otherTotal'],'subtotal')]
 rows += [('TOTAL GENERAL',data['total'],'grand')]
 width=1400;height=300+76*len(rows);im=Image.new('RGB',(width,height),p['bg']);d=ImageDraw.Draw(im)
 from server.plan_clients import color
 brand(d,width,'.'.join(reversed(plan['date'].split('-'))),'METAL ÎN SECȚIE',p)
 d.text((48,120),'Metal aflat în secție',font=font(38,True),fill=p['ink'])
 d.text((76,200),'CLIENT / CATEGORIE',font=font(23,True),fill=p['muted'])
 d.text((1210,200),'TONE',font=font(23,True),fill=p['muted'])
 for i,(name,value,kind) in enumerate(rows):
  y=245+i*76;bold=kind in ('subtotal','grand')
  fill=p['green'] if kind=='grand' else p['blue'] if kind=='subtotal' else p['head'] if kind=='manual' else p['paper']
  d.rounded_rectangle((48,y-4,1352,y+66),10,fill=fill)
  if kind=='client':d.ellipse((76,y+22,89,y+35),fill=color(name,theme=='dark'))
  d.text((110 if kind=='client' else 76,y+14),name,font=font(27,bold),fill=p['ink'])
  if value is not None:
   text=amount(value,3);d.text((1318-d.textlength(text,font=font(30,True)),y+12),text,font=font(30,True),fill=p['success'] if kind=='grand' else p['ink'])
 return png(im)
