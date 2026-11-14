"""Lay out imported tables for report export."""
from datetime import date
from io import BytesIO
import re
from PIL import Image, ImageDraw
from server.render import font, png
from server.km_completion import norm
from server.export_marks import numeric, priority_dot
from server.forecast_totals import aligned_tonnage, tonnage_column, total_label
from server.materials import marker

MAX_PIXELS=40_000_000

class SourceRenderError(ValueError):
 pass

def source_image(report,palette,show_status=True,stamp=None,with_brand=True):
 from server.corporate import brand
 if report['mode']=='plan':
  from server.plan_export import table_image
  return table_image(report, palette, with_brand, stamp)
 table=report['sourceTable'];rows=table['rows'];header=table['header'];p=palette
 ton_col=product=priority=None
 hidden=set()
 product_inset=44
 if report['mode']=='forecast':
  from server.forecast_order import source_rows
  rows=source_rows(table)
  headings=rows[header]
  mapping=table['columns']
  unmapped={i:norm(name).removesuffix(' optional') for i,name in enumerate(headings) if i not in mapping.values()}
  priority_columns={i for i,name in unmapped.items() if name in ('prioritate','priority','urgenta')}
  hidden={i for i,name in unmapped.items() if name in ('metri pe tambur','metrii pe tambur','metri tambur','m tambur','lungime tambur')}
  if 'priority' in mapping:priority_columns.add(mapping['priority'])
  if 'drumLength' in mapping:hidden.add(mapping['drumLength'])
  hidden.update(priority_columns)
  priority=mapping.get('priority')
  if priority is None and len(priority_columns)==1:priority=next(iter(priority_columns))
  product=mapping.get('product')
  if product is None:
   candidates=[i for i,name in unmapped.items() if name in ('produs','produse','product')]
   if len(candidates)==1:product=candidates[0]
  ton_col=tonnage_column(table,headings)
  if ton_col is not None:
   rows=aligned_tonnage(rows,table,ton_col)
 width=max(map(len,rows))
 if report['mode']=='forecast' and not show_status:
  if 'status' in table['columns']:hidden.add(table['columns']['status'])
  for i,name in enumerate(rows[header]):
   if name.strip().casefold() in ('stadiu','status'):hidden.add(i)
 columns=[i for i in range(width) if i not in hidden]
 if not columns:raise SourceRenderError('Nu există coloane de afișat.')
 measure=ImageDraw.Draw(Image.new('RGB',(1,1)));body_font=font(24);head_font=font(20,True)
 def is_total(row):
  if report['mode']=='forecast':
   return any(total_label(value) for value in row) or norm(' '.join(row[:3])).startswith('intrari')
  return norm(' '.join(row[:3])).startswith(('total','intrari'))
 def header_lines(value):
  words=str(value).split()
  if len(words)<2:return [' '.join(words)] if words else []
  choices=[[' '.join(words[:i]),' '.join(words[i:])] for i in range(1,len(words))]
  return min(choices,key=lambda parts:max(measure.textlength(t,font=head_font) for t in parts))
 def body_line(value):return ' '.join(str(value).replace('\r','\n').splitlines())
 widths=[]
 # Every body cell stays on one line, including total labels and observations.
 for col in columns:
  values=[body_line(row[col]) for ri,row in enumerate(rows) if ri>header and col<len(row) and row[col]]
  key=next((k for k,v in table['columns'].items() if v==col),None)
  heading=str(rows[header][col]) if col<len(rows[header]) else ''
  header_width=max((measure.textlength(t,font=head_font) for t in header_lines(heading)),default=0)
  body_width=max((measure.textlength(v,font=body_font) for v in values),default=0)
  bold_width=max((measure.textlength(body_line(row[col]),font=font(24,True))
                  for ri,row in enumerate(rows) if ri>header and col<len(row) and is_total(row)),default=0)
  body_width=max(body_width,bold_width)
  minimum=300 if col==product else 150 if key=='client' else 66 if key=='material' else 110
  body_padding=product_inset+17 if col==product else 33
  widths.append(max(minimum,int(header_width)+33,int(body_width)+body_padding))
 content=sum(widths)
 if content<2340:
  extra=2340-content;widths=[v+extra//len(widths)+(1 if i<extra%len(widths) else 0) for i,v in enumerate(widths)]
 image_width=sum(widths)+60;start=102 if with_brand else 16
 layouts=[];heights=[]
 for ri,row in enumerate(rows):
  populated=[(i,row[c]) for i,c in enumerate(columns) if c<len(row) and row[c]]
  if ri<header and len(populated)==1:
   i,value=populated[0];layout={columns[i]:[body_line(value)]}
  else:
   layout={}
   for c,w in zip(columns,widths):
    value=row[c] if c<len(row) else ''
    layout[c]=([' '.join(str(value).split())] if measure.textlength(' '.join(str(value).split()),font=head_font)<=w-32 else header_lines(value)) if ri==header else [body_line(value)] if str(value)!='' else []
  layouts.append(layout);heights.append(max(96 if ri==header else 60,24+max(map(len,layout.values()),default=0)*(28 if ri==header else 32)))
 image_height=start+sum(heights)+38
 if image_width>14000 or image_width*image_height>MAX_PIXELS:raise SourceRenderError('Tabelul este prea mare pentru o singură imagine lizibilă. Împarte-l în două rapoarte.')
 image=Image.new('RGB',(image_width,image_height),p['bg']);d=ImageDraw.Draw(image)
 if with_brand:
  title={'plan':'PLAN','forecast':'PREVIZ','weekday':'RAPORT','weekend':'RAPORT 3 ZILE'}[report['mode']]
  if report['mode']=='plan' and report.get('week'):title+=' '+report['week'].upper()
  brand(d,image_width,stamp or date.fromisoformat(report['date']).strftime('%d.%m.%Y'),title,p)

 y=start
 for ri,(row,height) in enumerate(zip(rows,heights)):
  if not height:continue
  total=ri>header and is_total(row)
  fill=p['head'] if ri==header else p['yellow'] if total else p['stripe'] if ri%2 else p['paper']
  if report['mode']=='forecast' and total:
   group=next((kind for value in row if (kind:=total_label(value))),None)
   if group=='AL':fill=p['blue']
   elif group=='CU':fill=p['green']
  d.rectangle((30,y,image_width-30,y+height),fill=fill)
  nonempty=[(i,row[c]) for i,c in enumerate(columns) if c<len(row) and row[c]]
  # Title rows in Excel are commonly merged. Preserve the title across empty cells.
  if ri<header and len(nonempty)==1:
   i,value=nonempty[0];x=30+sum(widths[:i])+(sum(widths[i:])-d.textlength(body_line(value),font=body_font))/2
   for n,line in enumerate(layouts[ri].get(columns[i],[])):d.text((x,y+(height-32)/2+n*32),line,font=body_font,fill=p['ink'])
  else:
   x=30
   for ci,w in zip(columns,widths):
    value=row[ci] if ci<len(row) else '';f=head_font if ri==header else font(24,total)
    if report['mode']=='forecast' and ri!=header and ci==table['columns'].get('material',0):
     token=str(value).strip().upper().rstrip(':')
     if token in ('AL','CU'):d.rectangle((x,y,x+w,y+height),fill=p['blue'] if token=='AL' else p['green'])
    if report['mode']=='forecast' and ri>header and ci==table['columns'].get('status') and re.match(r'^PREDAT(?:\s|$)',str(value).strip(),re.I):d.rectangle((x,y,x+w,y+height),fill=p['success_bg'])
    cell_lines=layouts[ri].get(ci,[])
    is_product=ci==product and ri>header and not total and str(value).strip() and not marker(value)
    if is_product:
     priority_value=row[priority] if priority is not None and priority<len(row) else ''
     priority_dot(d,(x+24,y+height/2),priority_value,p,6)
    for n,line in enumerate(cell_lines):
     left=x+16 if total and ci!=ton_col and not numeric(line) else x+(w-d.textlength(line,font=f))/2
     if is_product:left=x+product_inset
     color=p['accent'] if total and (ci==ton_col or numeric(line)) else p['ink']
     d.text((left,y+(height-28*len(cell_lines))/2+n*28 if ri==header else y+(height-32)/2+n*32),line,font=f,fill=color)
    x+=w
  d.line((30,y+height,image_width-30,y+height),fill=p['line']);y+=height
 d.line((30,start,image_width-30,start),fill=p['line'])
 return image

def combined_image(chart,report,palette,stamp):
 table=source_image(report,palette,stamp=stamp,with_brand=False)
 width=max(chart.width,table.width);height=chart.height+table.height
 if width*height>MAX_PIXELS:raise SourceRenderError('Tabelul și diagramele depășesc dimensiunea unei imagini. Împarte sursa în rapoarte mai mici.')
 result=Image.new('RGB',(width,height),palette['bg']);result.paste(chart,((width-chart.width)//2,0));result.paste(table,((width-table.width)//2,chart.height));return png(result)
