"""Readable execution instructions for shift two, with no status leakage."""
from PIL import Image,ImageDraw
from server.render import font,wrapped
from server.forecast_work import decimal_text

def work_image(entries,p,width=1672):
 if not entries:return None
 measure=ImageDraw.Draw(Image.new('RGB',(1,1)));layouts=[]
 for entry in entries:
  title=f"{entry['order']}. {entry['material']} · {entry['product']}"+(f" · {entry['client']}" if entry['client'] else '')
  headline=wrapped(measure,title,18,width-290,True)
  quantities=[decimal_text(entry[k])+' '+unit for k,unit in [('km','km'),('tons','t')] if entry[k]]
  lines=['Cantitate: '+' · '.join(quantities)] if quantities else []
  if entry['measure']:lines.append('Măsurări: '+entry['measure'])
  if entry['notes']:lines.append('Instrucțiuni: '+entry['notes'])
  if entry['drums']:
   calc=entry['drums'];lines.append(f"Tamburi: {calc['count']} · {calc['text']}")

  body=[line for text in lines for line in wrapped(measure,text,16,width-110)]
  height=30+26*len(headline)+24*len(body);layouts.append((entry,headline,body,height))
 height=55+sum(h+10 for _,_,_,h in layouts)
 image=Image.new('RGB',(width,height),p['bg']);d=ImageDraw.Draw(image)
 d.text((30,10),'LISTA DE EXECUȚIE · SCHIMBUL 2',font=font(19,True),fill=p['ink']);y=55
 for entry,headline,body,h in layouts:
  urgent=entry['priority']=='urgent';accent='#f0a58d' if p['bg']=='#151619' else '#b42318'
  d.rounded_rectangle((30,y,width-30,y+h),radius=10,fill=p['paper'],outline=p['line'])
  d.rectangle((30,y+9,34,y+h-9),fill=accent if urgent else p['accent'])
  for i,line in enumerate(headline):d.text((50,y+14+i*26),line,font=font(18,True),fill=p['ink'])
  d.text((width-190,y+17),'URGENT' if urgent else 'NORMAL',font=font(15,True),fill=accent if urgent else p['muted'])
  yy=y+18+26*len(headline)
  for i,line in enumerate(body):d.text((50,yy+i*24),line,font=font(16),fill=p['ink'])
  y+=h+10
 return image
