"""Distribution of forecast (not handed-over) tonnes by client."""
from decimal import Decimal
import re

def distribution(forecast):
 source=forecast.get('sourceTable')
 if source and not {'client','tons'}<=set(source['columns']):
  return [],'Asociază coloanele Client și Tone pentru a calcula distribuția.'
 clients={}
 for row in forecast['rows']:
  label=re.sub(r'\s+',' ',row['client'].strip());key=label.casefold() if label else None
  value=row['tons']
  if value<=0:continue
  item=clients.setdefault(key,{'client':label or 'Client necompletat','tons':Decimal('0'),'unknown':not bool(label)})
  item['tons']+=value
 total=sum((r['tons'] for r in clients.values()),Decimal('0'))
 result=sorted(clients.values(),key=lambda r:(-r['tons'],r['client'].casefold()))
 for row in result:row['percent']=row['tons']/total*100
 return result,'Pondere din tonele previzionate. Cantitățile fără client sunt păstrate separat.' if result else 'Nu există cantități pozitive în tone pentru această diagramă.'
