"""Landscape client pages with readable summaries and product stage detail."""
from PIL import Image,ImageDraw
from server.render import font,amount,png,wrapped
from server.plan_clients import color

def pages(insights):
 result=[]
 for group in insights.get('client_flow',[]):
  rows=[]
  for product in group.get('products',[]):
   for stage in product['stages']:rows.append({'product':product['product'],'material':product['material'],**stage})
  for item in group.get('allocated',[]):rows.append({'product':item['product'],'material':item['material'],'message':item['message']})
  for start in range(0,max(1,len(rows)),16):result.append((group,rows[start:start+16]))
 return result

def image(plan,insights,theme,page=0):
 from server.corporate import LIGHT,DARK,brand
 p=DARK if theme=='dark' else LIGHT;items=pages(insights)
 if page<0 or page>=max(1,len(items)):raise ValueError('Pagină invalidă.')
 im=Image.new('RGB',(2400,1350),p['bg']);d=ImageDraw.Draw(im)
 brand(d,2400,'.'.join(reversed(plan['date'].split('-'))),'PLAN '+plan['week'],p)
 if not items:return png(im)
 group,rows=items[page];ink=color(group['client'],theme=='dark')
 def write(x,y,value,size=28,bold=False,limit=None,fill=None):
  if limit:
   while size>22 and d.textlength(value,font=font(size,bold))>limit:size-=1
  d.text((x,y),value,font=font(size,bold),fill=fill or p['ink'])
 write(40,115,group['client'],40,True,limit=1800);write(2010,125,f'FLUX · {page+1}/{len(items)}',26,True)
 d.rounded_rectangle((40,205,610,1295),18,fill=p['paper']);write(65,230,'TOTAL PE CLIENT',26,True)
 maximum=max((float(r['value']) for r in group['stages'] if r['unit']=='km'),default=0) or 1
 for i,r in enumerate(group['stages']):
  y=300+i*96;write(65,y,r['label'],25)
  value=amount(r['value'],3)+' '+r['unit']
  if r['tons'] is not None:value+=' · '+amount(r['tons'],3)+' t'
  write(65,y+35,value,28,True)
  if r['unit']=='km':
   d.rounded_rectangle((65,y+73,575,y+82),4,fill=p['head']);length=510*float(r['value'])/maximum
   if length:d.rounded_rectangle((65,y+73,65+max(2,length),y+82),4,fill=ink)
 d.rounded_rectangle((640,205,2360,1295),18,fill=p['paper'])
 for x,label in [(670,'PRODUS'),(1580,'ETAPĂ'),(1950,'KM'),(2190,'TONE')]:write(x,235,label,25,True)
 for i,r in enumerate(rows):
  y=300+i*60
  if i%2==0:d.rectangle((655,y-5,2345,y+53),fill=p['stripe'])
  write(670,y,r['product']+' · '+r['material'],28,True,limit=870)
  if 'message' in r:
   for j,line in enumerate(wrapped(d,r['message'],22,740)):write(1580,y+j*26,line,22,fill=p['muted'])
   continue
  write(1580,y,r['label'],25,limit=345)
  if r['unit']=='km':write(1950,y,amount(r['value'],3),28)
  tons=r['tons'] if r['unit']=='km' else r['value']
  if tons is not None:write(2190,y,amount(tons,3),28)
 return png(im)
