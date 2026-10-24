"""Part-to-whole kilometre donut and remaining-tonne client shares."""
from decimal import Decimal
from server.render import font,wrapped,amount
COLORS={'bar':'#4e82cf','vane':'#319da6','cable':'#ed4698','mi':'#ef9b35','armored':'#709e43','mf':'#9578c9'}
def stages(insights):return [r for r in insights['stages'] if r['key']!='goods' and r['current'] is not None and r['current']>0]
def stocks(insights):return [(k,label,insights['ton_stocks'][k]) for k,label in [('wire','Sârmă'),('spool','Lită')] if insights['ton_stocks'][k] is not None]
def goods(insights):return next((r['current'] for r in insights['stages'] if r['key']=='goods'),None)
def client_layout(draw,insights):
 return [(r,wrapped(draw,r['client'],18,245),max(58,26*len(wrapped(draw,r['client'],18,245))+16)) for r in insights.get('clients',[])]
def height(insights,draw):
 flow=420 if stages(insights) else 48 if goods(insights) is not None or stocks(insights) else 0
 if stocks(insights):flow+=94
 if goods(insights) is not None:flow+=80
 return max(flow+20 if flow else 0,135+sum(h for _,_,h in client_layout(draw,insights)) if insights.get('clients') else 0)

def draw(draw,left,top,insights,p,theme):
 def text(x,y,value,size=18,color=None,bold=False):draw.text((left+x,y),str(value),font=font(size,bold),fill=color or p['ink'])
 rows=stages(insights);handed=goods(insights);clients=client_layout(draw,insights);stock=stocks(insights)
 if rows or handed is not None:
  text(30,top,'SITUAȚIA PE FLUX · KM',18,bold=True)
 if rows:
  cx=215;cy=top+225;total=sum((r['current'] for r in rows),Decimal(0));start=-90
  box=(left+cx-150,cy-150,left+cx+150,cy+150)
  for i,r in enumerate(rows):
   share=float(r['current']/total);arc=360*share
   draw.arc(box,start=start,end=start+arc,fill=COLORS[r['key']],width=44);start+=arc
   y=top+55+i*50;draw.ellipse((left+410,y+5,left+422,y+17),fill=COLORS[r['key']]);text(435,y,r['label'],17);text(435,y+22,amount(r['current'],2)+' km',20,bold=True);text(710,y+22,amount(Decimal(str(share*100)),2)+'%',16,p['muted'])
  text(435,top+370,'Total · '+amount(total,2)+' km',19,bold=True)
  for value,y,size,color in [('PRODUSE',cy-24,12 if len(rows)>5 else 16,p['ink']),('(STADII)',cy-5,11 if len(rows)>5 else 14,p['ink']),('km',cy+16,12,p['muted'])]:
   w=draw.textlength(value,font=font(size,True));draw.text((left+cx-w/2,y),value,font=font(size,True),fill=color)
 y=top+420 if rows else top+48
 if stock:
  card_width=(766-16*(len(stock)-1))/len(stock)
  for i,(key,label,value) in enumerate(stock):
   x=30+i*(card_width+16);ink=({'wire':'#77b4cb','spool':'#b29dd5'} if theme=='dark' else {'wire':'#3b7a93','spool':'#8a74af'})[key]
   draw.rounded_rectangle((left+x,y,left+x+card_width,y+80),radius=10,fill=p['paper'],outline=p['line'])
   draw.rounded_rectangle((left+x+24,y+22,left+x+31,y+59),radius=3,fill=ink);draw.rounded_rectangle((left+x+57,y+22,left+x+64,y+59),radius=3,fill=ink)
   draw.rectangle((left+x+31,y+29,left+x+57,y+52),outline=ink,width=2)
   for offset in range(34,57,5):draw.line((left+x+offset,y+29,left+x+offset,y+52),fill=ink,width=2)
   text(x+86,y+13,label,17,p['muted']);text(x+86,y+40,amount(value,2)+' t',24,ink,True)
  y+=94
 if handed is not None:
  draw.rounded_rectangle((left+30,y,left+796,y+66),radius=10,fill=p['blue']);text(48,y+22,'Marfă predată',18);text(560,y+18,amount(handed,2)+' km',24,p['accent'],True)
 if clients:
  x=876;text(x,top,'REST DE PREDAT PLAN LANSAT',18,bold=True);maximum=float(insights.get('remaining_total',sum((r['tons'] for r,_,_ in clients)))) or 1;y=top+55
  for row,lines,h in clients:
   for j,line in enumerate(lines):text(x,y+(h-len(lines)*26)/2+j*26,line,18)
   center=y+h/2;draw.rounded_rectangle((left+x+265,center-7,left+x+535,center+7),radius=5,fill=p['head'])
   width=270*min(1,float(row['tons'])/maximum);draw.rounded_rectangle((left+x+265,center-7,left+x+265+max(2,width),center+7),radius=5,fill=row['darkColor'] if theme=='dark' else row['color'])
   text(x+550,center-12,amount(row['tons'],2)+' t',20,bold=True);text(x+675,center-10,amount(Decimal(str(100*float(row['tons'])/maximum)),2)+'%',16,p['muted']);y+=h

  draw.rounded_rectangle((left+x,y+10,left+x+755,y+62),radius=9,fill=p['blue'])
  text(x+16,y+26,'TOTAL REST DE PREDAT',18,bold=True)
  total=insights.get('remaining_total',sum((r['tons'] for r,_,_ in clients)))
  text(x+550,y+23,amount(total,2)+' t',22,bold=True)
