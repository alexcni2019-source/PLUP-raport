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

def adjust(data,overrides):
 if not overrides:return data
 data={**data,'clients':[{**r} for r in data['clients']],'referenceTotal':data['total']}
 for row in data['clients']:
  if row['client'] in overrides:row['originalTons']=row['tons'];row['tons']=overrides[row['client']]
 missing=[r['client'] for r in data['clients'] if r['tons'] is None]
 data['missing']=missing
 data['total']=None if missing else sum((r['tons'] for r in data['clients']),Decimal(0))+sum((v for v in data['extras'].values() if v is not None),Decimal(0))
 return data

def image(plan,insights,theme):
 from server.corporate import LIGHT,DARK,brand
 p=DARK if theme=='dark' else LIGHT;data=insights.get('section_stock') or build(insights,plan['sectionStock'])
 if data.get('basis')=='inventory':plan={**plan,'date':data['date']}
 if data['missing']:raise ValueError('Nu pot completa tonele pentru: '+', '.join(data['missing'])+'. Verifică denumirile produselor și etapele din plan.')
 rows=[(r['client'],r['tons']) for r in data['clients']]+([] if data.get('basis')=='inventory' else [(label,data['extras'][key]) for key,label in [('samples','Mostre'),('waste','Deșeu (doar ce e în secție)'),('dead','Stoc „mort”')]])+[('TOTAL',data['total'])]
 width=1400;height=390+76*len(rows);im=Image.new('RGB',(width,height),p['bg']);d=ImageDraw.Draw(im)
 from server.plan_clients import color
 brand(d,width,'.'.join(reversed(plan['date'].split('-'))),'METAL ÎN SECȚIE',p)
 d.text((48,120),'Metal aflat în secție',font=font(38,True),fill=p['ink'])
 d.rounded_rectangle((48,195,1352,282),16,fill=p['green'])
 d.text((76,219),'TOTAL GENERAL',font=font(25,True),fill=p['ink'])
 total_text=amount(data['total'],3)+' t'
 d.text((1318-d.textlength(total_text,font=font(38,True)),210),total_text,font=font(38,True),fill=p['success'])
 d.text((76,310),'CLIENT / CATEGORIE',font=font(23,True),fill=p['muted'])
 d.text((1210,310),'TONE',font=font(23,True),fill=p['muted'])
 for i,(name,value) in enumerate(rows[:-1]):
  y=355+i*76;manual=i>=len(data['clients'])
  if manual:d.rounded_rectangle((48,y-4,1352,y+66),10,fill=p['head'])
  else:d.rounded_rectangle((48,y-4,1352,y+66),10,fill=p['paper'])
  if not manual:d.ellipse((76,y+22,89,y+35),fill=color(name,theme=='dark'))
  d.text((110 if not manual else 76,y+14),name,font=font(28),fill=p['ink'])
  if value is not None:
   text=amount(value,3);d.text((1318-d.textlength(text,font=font(30,True)),y+12),text,font=font(30,True),fill=p['ink'])
 return png(im)
