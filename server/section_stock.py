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

def image(plan,insights,theme):
 from server.corporate import LIGHT,DARK,brand
 p=DARK if theme=='dark' else LIGHT;data=build(insights,plan['sectionStock'])
 if data['missing']:raise ValueError('Nu pot completa tonele pentru: '+', '.join(data['missing'])+'. Verifică denumirile produselor și etapele din plan.')
 rows=[(r['client'],r['tons']) for r in data['clients']]+[(label,data['extras'][key]) for key,label in [('samples','Mostre'),('waste','Deșeu (doar ce e în secție)'),('dead','Stoc „mort”')]]+[('TOTAL',data['total'])]
 width=1400;height=260+70*len(rows);im=Image.new('RGB',(width,height),p['bg']);d=ImageDraw.Draw(im)
 brand(d,width,'.'.join(reversed(plan['date'].split('-'))),'METAL ÎN SECȚIE',p)
 d.text((40,112),'SITUAȚIA METALULUI ÎN SECȚIE',font=font(30,True),fill=p['ink'])
 d.rounded_rectangle((40,180,1360,236),10,fill=p['blue']);d.text((64,192),'CLIENT / CATEGORIE',font=font(25,True),fill=p['ink']);d.text((1170,192),'TONE',font=font(25,True),fill=p['ink'])
 for i,(name,value) in enumerate(rows):
  y=240+i*70;bold=i==len(rows)-1
  d.rectangle((40,y,1360,y+68),fill=p['green'] if bold else p['paper'] if i%2==0 else p['stripe'])
  d.text((64,y+18),name,font=font(27,bold),fill=p['ink'])
  if value is not None:
   text=amount(value,3);d.text((1300-d.textlength(text,font=font(29,bold)),y+16),text,font=font(29,bold),fill=p['ink'])
 return png(im)
