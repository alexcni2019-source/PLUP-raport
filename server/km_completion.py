"""A visual near-completion rule; raw kilometre values are never modified."""
from decimal import Decimal,InvalidOperation
import re,unicodedata

def norm(value):
 value=''.join(c for c in unicodedata.normalize('NFKD',str(value)) if not unicodedata.combining(c))
 return re.sub(r'[^a-z0-9]+',' ',value.lower()).strip()

def columns(headers):
 def find(names):
  found=[i for i,v in enumerate(headers) if norm(v) in names]
  return found[0] if len(found)==1 else None
 return find({'km porniti','km pornit','kilometri porniti'}),find({'km predati','km predat','kilometri predati'})

def number(value):
 text=str(value or '').strip().lower();text=re.sub(r'\s','',text)
 if text.endswith('km'):text=text[:-2]
 if not re.fullmatch(r'\d+(?:[.,]\d+)?',text):return None
 try:return Decimal(text.replace(',','.'))
 except InvalidOperation:return None

def close(started,handed):
 a,b=number(started),number(handed)
 return a is not None and b is not None and a>0 and abs(a-b)<=Decimal('0.2')

def highlighted(table):
 a,b=columns(table['rows'][table['header']]);result={}
 if a is None or b is None:return result
 for ri,row in enumerate(table['rows']):
  if ri<=table['header'] or norm(' '.join(row[:3])).startswith(('total','intrari')):continue
  if max(a,b)<len(row) and close(row[a],row[b]):result[ri]={a,b}
 return result
