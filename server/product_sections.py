"""Read explicit conductor sections; never treat voltage or model digits as sections."""
from decimal import Decimal
import re
NUM=r'\d+(?:[.,]\d+)?'
SUFFIX=r'(?:RM|SM|SE|RE|RMC|SMC)?'
TERM=rf'(?:(\d+)\s*[X×*]\s*)?({NUM})\s*{SUFFIX}'
START=re.compile(rf'(?<![A-Z\d.,])(\d+)\s*[X×*]\s*({NUM})',re.I)
EXPR=re.compile(rf'{TERM}(?:\s*\+\s*{TERM})*',re.I)
PART=re.compile(TERM,re.I)

def conductor_terms(product):
 text=str(product).upper();starts=list(START.finditer(text))
 if not starts:return None
 start=starts[0].start();match=EXPR.match(text,start)
 if not match:return None
 end=match.end();tail=text[end:].lstrip()
 # Slash alternatives or an unfinished addition cannot be safely interpreted.
 if tail.startswith(('+','/','X','×','*')) or any(m.start()>=end for m in starts):return None
 terms=[]
 for part in re.split(r'\s*\+\s*',match.group()):
  term=PART.fullmatch(part.strip())
  if not term:return None
  n=int(term.group(1) or '1');area=Decimal(term.group(2).replace(',','.'))
  if not 1<=n<=100 or not 0<area<=2500:return None
  terms.append((n,area))
 return terms

def sections(product):
 terms=conductor_terms(product)
 return (sum((n*area for n,area in terms),Decimal(0)),sum(n for n,area in terms)) if terms else None

def metal_per_km(product,material,stage):
 spec=sections(product)
 if spec is None or material not in ('AL','CU'):return None
 area,count=spec
 allowed={'bar','vane','mf','started','delivered'} if count==1 else {'bar','vane','cable','armored','mi','mf','started','delivered'}
 if stage not in allowed:return None
 if stage in ('bar','vane'):
  terms=conductor_terms(product)
  if len(terms)==1:area=terms[0][1]
  elif len(terms)==2 and terms[0][0]==3 and terms[1][0]==1:area=terms[0][1]*Decimal('0.90')
  else:return None
 factor=Decimal('2.7')*Decimal('0.93') if material=='AL' else Decimal('8.9')*Decimal('0.93')
 return area*factor/Decimal('1000')
