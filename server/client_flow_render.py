"""Third plan PNG: independent process amounts by client."""
from PIL import Image,ImageDraw
from server.render import font,amount,png,wrapped
from server.plan_clients import color

def image(plan,insights,theme):
 from server.corporate import LIGHT,DARK,brand
 from server.source_render import MAX_PIXELS,SourceRenderError
 p=DARK if theme=='dark' else LIGHT;groups=insights.get('client_flow',[])
 width=2400;card_width=1140;heights=[]
 measure=ImageDraw.Draw(Image.new('RGB',(1,1)))
 for offset in range(0,len(groups),2):
  pair=groups[offset:offset+2]
  heights.append(max(150+len(g['stages'])*62+len(wrapped(measure,g['client'],30,1000))*38 for g in pair))
 height=200+sum(h+28 for h in heights)
 if width*height>MAX_PIXELS:raise SourceRenderError('Prea mulți clienți pentru o singură imagine. Împarte planul înainte de export.')
 im=Image.new('RGB',(width,max(height,350)),p['bg']);d=ImageDraw.Draw(im)
 brand(d,width,'.'.join(reversed(plan['date'].split('-'))),'PLAN '+plan['week'],p)
 d.text((40,108),'SITUAȚIA PE FLUX · CLIENȚI',font=font(30,True),fill=p['ink'])
 y=180
 for offset,h in zip(range(0,len(groups),2),heights):
  for j,g in enumerate(groups[offset:offset+2]):
   x=40+j*1180;ink=color(g['client'],theme=='dark')
   d.rounded_rectangle((x,y,x+card_width,y+h),radius=18,fill=p['paper'])
   lines=wrapped(d,g['client'],30,1000)
   for k,line in enumerate(lines):d.text((x+28,y+24+38*k),line,font=font(30,True),fill=p['ink'])
   top=y+40+38*len(lines);maximum=max((float(r['value']) for r in g['stages'] if r['unit']=='km'),default=0) or 1
   for i,r in enumerate(g['stages']):
    ry=top+i*62;d.text((x+28,ry),r['label'],font=font(23),fill=p['ink'])
    if r['unit']=='km':
     d.rounded_rectangle((x+320,ry+12,x+680,ry+25),radius=6,fill=p['head'])
     length=360*float(r['value'])/maximum
     if length>0:d.rounded_rectangle((x+320,ry+12,x+320+max(2,length),ry+25),radius=6,fill=ink)
    value=amount(r['value'],3)+' '+r['unit']
    if r['tons'] is not None:value+=' · '+amount(r['tons'],3)+' t'
    d.text((x+card_width-28-d.textlength(value,font=font(23,True)),ry),value,font=font(23,True),fill=p['ink'])
  y+=h+28
 return png(im)
