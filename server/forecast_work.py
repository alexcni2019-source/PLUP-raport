"""Execution instructions and exact drum planning for forecast rows."""
from decimal import Decimal
import re

FIELDS={'order','priority','drumLength'}

def decimal_text(v):
 text=format(v,'f')
 return text.rstrip('0').rstrip('.') if '.' in text else text

def drum_plan(row):
 length=row.get('drumLength')
 source='explicit'
 if length is None:
  match=re.fullmatch(r'\s*(\d{1,7})\s*M\s*/\s*(?:TB|TAMBUR)\s*',row.get('measure',''),re.I)
  length=Decimal(match[1]) if match else None;source='measure'
 if not length or row['km']<=0:return None
 metres=row['km']*1000;full=int(metres//length);rest=metres-full*length
 parts=[]
 if full:parts.append(f'{full} × {decimal_text(length)} m')
 if rest:parts.append(f'1 × {decimal_text(rest)} m')
 return {'count':full+(1 if rest else 0),'full':full,'length':length,'remainder':rest,'text':' + '.join(parts),'source':source}

def build(rows):
 entries=[]
 for i,row in enumerate(rows):
  drums=drum_plan(row)
  entries.append({'order':int(row.get('order') or i+1),'priority':row.get('priority') or 'normal','material':row['material'],'product':row['product'],'client':row['client'],'km':row['km'],'tons':row['tons'],'measure':row['measure'],'notes':row['notes'],'drums':drums,'drumHint':'Completează m/tambur pentru calcul.' if row['km']>0 and drums is None else ''})
 return sorted(entries,key=lambda r:r['order'])
