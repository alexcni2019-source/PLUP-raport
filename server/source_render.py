"""Render every imported cell, without a fixed business-column template."""
from datetime import date
from io import BytesIO
import re
from PIL import Image, ImageDraw
from server.render import font, png, wrapped
from server.km_completion import highlighted

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
 measure=ImageDraw.Draw(Image.new('RGB',(1,1)));body_font=font(20);head_font=font(16,True)
 highlights=highlighted(table) if report['mode']=='plan' else {}
 def raw_lines(value):return str(value).replace('\r\n','\n').replace('\r','\n').split('\n')
 widths=[]
 # Body values determine column width; long headings wrap rather than widening the image.
 for col in columns:
  values=[str(row[col]) for ri,row in enumerate(rows) if ri>header and col<len(row) and row[col]]
  key=next((k for k,v in table['columns'].items() if v==col),None)
  longest=max((measure.textlength(line,font=body_font) for v in values for line in raw_lines(v)),default=0)
  cap=280 if key in ('product','notes','measure') else 170 if key=='client' else 120
  minimum=230 if key=='product' else 125 if key=='client' else 50 if key=='material' else 86
  heading=str(rows[header][col]) if col<len(rows[header]) else ''
  word_width=max((measure.textlength(word,font=head_font) for word in heading.split()),default=0)
  widths.append(max(minimum,min(160,int(word_width)+24),min(cap,int(longest)+24)))
 content=sum(widths)
 if content<1612:
  extra=1612-content;widths=[v+extra//len(widths)+(1 if i<extra%len(widths) else 0) for i,v in enumerate(widths)]
 image_width=sum(widths)+60;start=102 if with_brand else 16
 layouts=[];heights=[]
 for ri,row in enumerate(rows):
  populated=[(i,row[c]) for i,c in enumerate(columns) if c<len(row) and row[c]]
  if ri<header and len(populated)==1:
   i,value=populated[0];layout={columns[i]:wrapped(measure,value,20,sum(widths[i:])-24)}
  else:
   layout={c:(wrapped(measure,row[c],16 if ri==header else 20,w-24,ri==header) if c<len(row) and str(row[c])!='' else []) for c,w in zip(columns,widths)}
  layouts.append(layout);heights.append(max(82 if ri==header else 44,18+max(map(len,layout.values()),default=0)*(24 if ri==header else 27)))
 image_height=start+sum(heights)+38
 if image_width>14000 or image_width*image_height>MAX_PIXELS:raise SourceRenderError('Tabelul este prea mare pentru o singură imagine lizibilă. Împarte-l în două rapoarte.')
 image=Image.new('RGB',(image_width,image_height),p['bg']);d=ImageDraw.Draw(image)
 if with_brand:
  title={'plan':'PLAN','forecast':'PREVIZ','weekday':'RAPORT','weekend':'RAPORT 3 ZILE'}[report['mode']]
  brand(d,image_width,stamp or date.fromisoformat(report['date']).strftime('%d.%m.%Y'),title,p)

 y=start
 for ri,(row,height) in enumerate(zip(rows,heights)):
  first=' '.join(row[:3]).strip().upper();total=first.startswith(('TOTAL','INTRARI','INTRĂRI'))
  fill=p['head'] if ri==header else p['yellow'] if total else p['stripe'] if ri%2 else p['paper']
  if report['mode'] in ('plan','forecast') and total:
   if first.startswith('TOTAL AL') and not first.startswith(('TOTAL AL +','TOTAL AL+')):fill=p['blue']
   elif first.startswith('TOTAL CU'):fill=p['green']
  d.rectangle((30,y,image_width-30,y+height),fill=fill)
  nonempty=[(i,row[c]) for i,c in enumerate(columns) if c<len(row) and row[c]]
  # Title rows in Excel are commonly merged. Preserve the title across empty cells.
  if ri<header and len(nonempty)==1:
   i,value=nonempty[0];x=30+sum(widths[:i])+12
   for n,line in enumerate(layouts[ri].get(columns[i],[])):d.text((x,y+9+n*27),line,font=body_font,fill=p['ink'])
  else:
   x=30
   for ci,w in zip(columns,widths):
    value=row[ci] if ci<len(row) else '';f=head_font if ri==header else body_font
    if report['mode'] in ('plan','forecast') and ri!=header and ci==table['columns'].get('material',0):
     token=str(value).strip().upper().rstrip(':')
     if token in ('AL','CU'):d.rectangle((x,y,x+w,y+height),fill=p['blue'] if token=='AL' else p['green'])
    if report['mode']=='forecast' and ri>header and ci==table['columns'].get('status') and re.match(r'^PREDAT(?:\s|$)',str(value).strip(),re.I):d.rectangle((x,y,x+w,y+height),fill=p['success_bg'])
    if ci in highlights.get(ri,set()):d.rectangle((x,y,x+w,y+height),fill=p['success_bg'])
    cell_lines=layouts[ri].get(ci,[])
    for n,line in enumerate(cell_lines):
     numeric=bool(re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?(?:\s*(?:t|km|%))?',line.strip(),re.I))
     left=x+w-12-d.textlength(line,font=f) if numeric and ri!=header else x+12
     d.text((left,y+(height-24*len(cell_lines))/2+n*24 if ri==header else y+9+n*27),line,font=f,fill=p['success'] if ci in highlights.get(ri,set()) else p['ink'])
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
