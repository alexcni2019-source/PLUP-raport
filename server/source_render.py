"""Render every imported cell, without a fixed business-column template."""
from datetime import date
from io import BytesIO
import re
from PIL import Image, ImageDraw
from server.render import font, png

MAX_PIXELS=40_000_000

class SourceRenderError(ValueError):
 pass

def source_image(report,palette,show_status=True,stamp=None,with_brand=True):
 from server.corporate import brand
 table=report['sourceTable'];rows=table['rows'];header=table['header'];width=max(map(len,rows));p=palette
 hidden=set()
 if report['mode']=='forecast' and not show_status:
  if 'status' in table['columns']:hidden.add(table['columns']['status'])
  for i,name in enumerate(rows[header]):
   if name.strip().casefold() in ('stadiu','status'):hidden.add(i)
 columns=[i for i in range(width) if i not in hidden]
 if not columns:raise SourceRenderError('Nu există coloane de afișat.')
 measure=ImageDraw.Draw(Image.new('RGB',(1,1)));body_font=font(16);head_font=font(14,True)
 def lines(value):return str(value).replace('\r\n','\n').replace('\r','\n').split('\n')
 widths=[]
 for col in columns:
  longest=0
  for ri,row in enumerate(rows):
   if ri<header and sum(bool(v) for v in row)==1:continue
   value=row[col] if col<len(row) else ''
   for line in lines(value):longest=max(longest,measure.textlength(line,font=head_font if ri==header else body_font))
  widths.append(max(50,int(longest)+24))
 content=sum(widths)
 if content<1612:
  extra=1612-content;widths=[v+extra//len(widths)+(1 if i<extra%len(widths) else 0) for i,v in enumerate(widths)]
 for row in rows[:header]:
  populated=[(i,row[c]) for i,c in enumerate(columns) if c<len(row) and row[c]]
  if len(populated)==1:
   i,value=populated[0];required=max(measure.textlength(line,font=body_font) for line in lines(value))+24
   widths[-1]+=max(0,int(required+1)-sum(widths[i:]))
 image_width=sum(widths)+60;start=102 if with_brand else 60
 heights=[max(34,14+max((len(lines(row[c] if c<len(row) else '')) for c in columns),default=1)*22) for row in rows]
 image_height=start+sum(heights)+38
 if image_width>14000 or image_width*image_height>MAX_PIXELS:raise SourceRenderError('Tabelul este prea mare pentru o singură imagine lizibilă. Împarte-l în două rapoarte.')
 image=Image.new('RGB',(image_width,image_height),p['bg']);d=ImageDraw.Draw(image)
 if with_brand:
  title={'plan':'PLAN','forecast':'PREVIZ','weekday':'RAPORT','weekend':'RAPORT 3 ZILE'}[report['mode']]
  brand(d,image_width,stamp or date.fromisoformat(report['date']).strftime('%d.%m.%Y'),title,p)
 else:d.text((30,22),'TABEL IMPORTAT INTEGRAL',font=font(16,True),fill=p['muted'])
 y=start
 for ri,(row,height) in enumerate(zip(rows,heights)):
  first=' '.join(row[:3]).strip().upper();total=first.startswith(('TOTAL','INTRARI','INTRĂRI'))
  fill=p['head'] if ri==header else p['yellow'] if total else p['stripe'] if ri%2 else p['paper']
  d.rectangle((30,y,image_width-30,y+height),fill=fill)
  nonempty=[(i,row[c]) for i,c in enumerate(columns) if c<len(row) and row[c]]
  # Title rows in Excel are commonly merged. Preserve the title across empty cells.
  if ri<header and len(nonempty)==1:
   i,value=nonempty[0];x=30+sum(widths[:i])+12
   for n,line in enumerate(lines(value)):d.text((x,y+7+n*22),line,font=body_font,fill=p['ink'])
  else:
   x=30
   for ci,w in zip(columns,widths):
    value=row[ci] if ci<len(row) else '';f=head_font if ri==header else body_font
    for n,line in enumerate(lines(value)):
     numeric=bool(re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?(?:\s*(?:t|km|%))?',line.strip(),re.I))
     left=x+w-12-d.textlength(line,font=f) if numeric and ri!=header else x+12
     d.text((left,y+7+n*22),line,font=f,fill=p['ink'])
    d.line((x,y,x,y+height),fill=p['line']);x+=w
   d.line((x,y,x,y+height),fill=p['line'])
  d.line((30,y+height,image_width-30,y+height),fill=p['line']);y+=height
 d.line((30,start,image_width-30,start),fill=p['line'])
 return image

def combined_image(chart,report,palette,stamp):
 table=source_image(report,palette,stamp=stamp,with_brand=False)
 width=max(chart.width,table.width);height=chart.height+table.height
 if width*height>MAX_PIXELS:raise SourceRenderError('Tabelul și diagramele depășesc dimensiunea unei imagini. Împarte sursa în rapoarte mai mici.')
 result=Image.new('RGB',(width,height),palette['bg']);result.paste(chart,((width-chart.width)//2,0));result.paste(table,((width-table.width)//2,chart.height));return png(result)
