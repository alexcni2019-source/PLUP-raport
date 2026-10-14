"""Read explicit conductor sections; never treat voltage or model digits as sections."""
from decimal import Decimal
import re
NUM=r'\d+(?:[.,]\d+)?'
SUFFIX=r'(?:RM|SM|SE|RE|RMC|SMC)?'
TERM=rf'(?:(\d+)\s*[X×*]\s*)?({NUM})\s*{SUFFIX}'
START=re.compile(rf'(?<![A-Z\d.,])(\d+)\s*[X×*]\s*({NUM})',re.I)
EXPR=re.compile(rf'{TERM}(?:\s*\+\s*{TERM})*',re.I)
PART=re.compile(TERM,re.I)

def sections(product):
 text=str(product).upper();starts=list(START.finditer(text))
 if not starts:return None
 start=starts[0].start();match=EXPR.match(text,start)
 if not match:return None
 end=match.end();tail=text[end:].lstrip()
 # Slash alternatives or an unfinished addition cannot be safely interpreted.
 if tail.startswith(('+','/','X','×','*')) or any(m.start()>=end for m in starts):return None
 total=Decimal(0);count=0
 for part in re.split(r'\s*\+\s*',match.group()):
  term=PART.fullmatch(part.strip())
  if not term:return None
  n=int(term.group(1) or '1');area=Decimal(term.group(2).replace(',','.'))
  if not 1<=n<=100 or not 0<area<=2500:return None
  count+=n;total+=n*area
 return total,count

def metal_per_km(product,material,stage):
 spec=sections(product)
 if spec is None or material not in ('AL','CU'):return None
 area,count=spec
 allowed={'bar','vane','mf','started','delivered'} if count==1 else {'cable','armored','mi','mf','started','delivered'}
 if stage not in allowed:return None
 factor=Decimal('2.7')*Decimal('0.92') if material=='AL' else Decimal('8.9')*Decimal('0.93')
 return area*factor/Decimal('1000')
