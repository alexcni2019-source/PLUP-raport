"""Independent kilometre rings and client remaining-tonne bars."""
from server.render import font,wrapped,amount
COLORS={'bar':'#4e82cf','vane':'#319da6','cable':'#6c82df','mi':'#a179bc','armored':'#c17c33','mf':'#29916a'}
def stages(insights):return [r for r in insights['stages'] if r['key']!='goods' and r['current'] is not None]
def goods(insights):return next((r['current'] for r in insights['stages'] if r['key']=='goods'),None)
def client_layout(draw,insights):
 return [(r,wrapped(draw,r['client'],18,245),max(58,26*len(wrapped(draw,r['client'],18,245))+16)) for r in insights.get('clients',[])]
def height(insights,draw):
 flow=bool(stages(insights)) or goods(insights) is not None
 return max(510 if flow else 0,75+sum(h for _,_,h in client_layout(draw,insights)) if insights.get('clients') else 0)
def draw(draw,left,top,insights,p,theme):
 def text(x,y,value,size=18,color=None,bold=False):draw.text((left+x,y),str(value),font=font(size,bold),fill=color or p['ink'])
 rows=stages(insights);handed=goods(insights);clients=client_layout(draw,insights)
 if rows or handed is not None:
  text(30,top,'SITUAȚIA PE FLUX · KM',18,bold=True)
 if rows:
  cx=230;cy=top+225;maximum=max((float(r['current']) for r in rows),default=0) or 1
  for i,r in enumerate(rows):
   radius=155-i*22;box=(left+cx-radius,cy-radius,left+cx+radius,cy+radius)
   draw.ellipse(box,outline=p['head'],width=14)
   arc=360*float(r['current'])/maximum
   if arc:draw.arc(box,start=-90,end=-90+arc,fill=COLORS[r['key']],width=14)
   y=top+65+i*58;draw.ellipse((left+430,y+5,left+442,y+17),fill=COLORS[r['key']]);text(455,y,r['label'],17);text(455,y+24,amount(r['current'],2)+' km',21,bold=True)
  for value,y,size,color in [('FLUX',cy-19,18,p['ink']),('km',cy+8,14,p['muted'])]:
   w=draw.textlength(value,font=font(size,True));draw.text((left+cx-w/2,y),value,font=font(size,True),fill=color)
 if handed is not None:
  y=top+430 if rows else top+48;draw.rounded_rectangle((left+30,y,left+796,y+66),radius=10,fill=p['blue']);text(48,y+22,'Marfă predată',18);text(560,y+18,amount(handed,2)+' km',24,p['accent'],True)
 if clients:
  x=876;text(x,top,'RĂMAS DE PREDAT · CLIENȚI',18,bold=True);maximum=max(float(r['tons']) for r,_,_ in clients);y=top+55
  for row,lines,h in clients:
   for j,line in enumerate(lines):text(x,y+(h-len(lines)*26)/2+j*26,line,18)
   center=y+h/2;draw.rounded_rectangle((left+x+265,center-7,left+x+615,center+7),radius=5,fill=p['head'])
   width=350*float(row['tons'])/maximum;draw.rounded_rectangle((left+x+265,center-7,left+x+265+max(2,width),center+7),radius=5,fill=row['darkColor'] if theme=='dark' else row['color'])
   text(x+635,center-12,amount(row['tons'],2)+' t',20,bold=True);y+=h
