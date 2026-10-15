"""Compact client process summary; product-level calculations remain in analysis."""
from PIL import Image,ImageDraw
from decimal import Decimal
from server.render import font,amount,png,wrapped
from server.plan_clients import color

def pages(insights):
 return [(None,[])] if insights.get('client_flow') else []

def image(plan,insights,theme,page=0):
 from server.corporate import LIGHT,DARK,brand
 from server.source_render import MAX_PIXELS,SourceRenderError
 if page!=0:raise ValueError('Pagină invalidă.')
 p=DARK if theme=='dark' else LIGHT;groups=[]
 stock=insights.get('section_stock',{});lookup={r.get('sourceClient',r['client']):r for r in stock.get('clients',[])}
 from server.section_stock import PROCESS
 for original in insights.get('client_flow',[]):
  g={**original,'stages':[dict(r) for r in original['stages']]};entry=lookup.get(original['client'])
  if entry:
   g['client']=entry['client'];g['stockTons']=entry['tons']
   calculated=sum((r['value'] if r['unit']=='t' else r['tons'] for r in g['stages'] if r['label'] in PROCESS and (r['unit']=='t' or r['tons'] is not None)),Decimal(0))
   if entry['tons'] is not None and 'originalTons' in entry:
    delta=entry['tons']-calculated
    if delta:g['stages'].append({'label':'Ajustare stoc','value':delta,'unit':'t','tons':None})
  groups.append(g)
 columns=3;width=2400;card_width=750;row_heights=[]
 for i in range(0,len(groups),columns):
  row_heights.append(max(170+58*len(g['stages'])+(100 if g.get('allocated') else 0) for g in groups[i:i+columns]))
 height=max(700,300+sum(h+24 for h in row_heights))
 if width*height>MAX_PIXELS:raise SourceRenderError('Prea mulți clienți pentru o singură imagine.')
 im=Image.new('RGB',(width,height),p['bg']);d=ImageDraw.Draw(im)
 brand(d,width,'.'.join(reversed(plan['date'].split('-'))),'PLAN '+plan['week'],p)
 d.text((40,105),'SITUAȚIA PE FLUX · CLIENȚI',font=font(30,True),fill=p['ink'])
 y=170
 for offset,h in zip(range(0,len(groups),columns),row_heights):
  for j,g in enumerate(groups[offset:offset+columns]):
   x=40+j*785;ink=color(g['client'],theme=='dark')
   d.rounded_rectangle((x,y,x+card_width,y+h),18,fill=p['paper'])
   size=30
   while size>22 and d.textlength(g['client'],font=font(size,True))>690:size-=1
   d.text((x+24,y+22),g['client'],font=font(size,True),fill=p['ink'])
   maximum=max((float(r['value']) for r in g['stages'] if r['unit']=='km'),default=0) or 1
   for i,r in enumerate(g['stages']):
    ry=y+82+i*58;d.text((x+24,ry),r['label'],font=font(23),fill=p['ink'])
    value=amount(r['value'],2 if r['unit']=='t' else 3)+' '+r['unit']
    if r['tons'] is not None:value+=' · '+amount(r['tons'],2)+' t'
    d.text((x+card_width-24-d.textlength(value,font=font(24,True)),ry),value,font=font(24,True),fill=p['ink'])
    if r['unit']=='km':
     d.rounded_rectangle((x+24,ry+35,x+card_width-24,ry+42),3,fill=p['head']);length=(card_width-48)*float(r['value'])/maximum
     if length:d.rounded_rectangle((x+24,ry+35,x+24+max(2,length),ry+42),3,fill=ink)
   if g.get('stockTons') is not None:
    ry=y+82+len(g['stages'])*58+8;value=amount(g['stockTons'],2)+' t'
    d.text((x+24,ry),'METAL ÎN SECȚIE',font=font(24,True),fill=p['ink'])
    d.text((x+card_width-24-d.textlength(value,font=font(26,True)),ry),value,font=font(26,True),fill=p['success'])
   if g.get('allocated'):
    ry=y+140+len(g['stages'])*58+10
    for k,line in enumerate(wrapped(d,'Metal alocat, dar încă nu s-a pornit trefilarea produsului.',22,card_width-48)):
     d.text((x+24,ry+28*k),line,font=font(22),fill=p['muted'])
  y+=h+24
 if stock.get('total') is not None:
  parts=[label+': '+amount(value,2)+' t' for key,label in [('samples','Mostre'),('waste','Deșeu în secție'),('dead','Stoc mort')] if (value:=stock.get('extras',{}).get(key)) is not None]
  if parts:d.text((40,height-100),'   ·   '.join(parts),font=font(25),fill=p['muted'])
  total='TOTAL METAL ÎN SECȚIE: '+amount(stock['total'],2)+' t'
  d.text((40,height-60),total,font=font(30,True),fill=p['ink'])
 return png(im)
