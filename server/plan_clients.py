"""Remaining tonnes per client: total planned minus total handed over."""
from decimal import Decimal
import colorsys,hashlib,re
from server.km_completion import highlighted

def color(name,dark=False):
 key=re.sub(r'\s+',' ',name.strip()).casefold()
 palette={'verex-el':'#4e82cf','sonepar rw':'#399e9a','sbt':'#8d77c4','helu':'#c18240','tub':'#b86f86','lemar':'#6c9950'}
 if key in palette:
  value=palette[key]
  if not dark:return value
  rgb=tuple(int(value[i:i+2],16)/255 for i in (1,3,5));h,_,sat=colorsys.rgb_to_hls(*rgb);rgb=colorsys.hls_to_rgb(h,.67,sat)
  return '#'+''.join(f'{round(v*255):02x}' for v in rgb)
 hue=int.from_bytes(hashlib.sha256(key.encode()).digest()[:4],'big')/2**32
 rgb=colorsys.hls_to_rgb(hue,.66 if dark else .48,.55)
 return '#'+''.join(f'{round(v*255):02x}' for v in rgb)

def build(plan,payload):
 clients={}
 source=plan.get('sourceTable') or payload.get('sourceTable')
 green=highlighted(source) if source else {}
 closed={i for i,record in enumerate(source.get('records',[])) if record['row'] in green} if source else set()
 for i,row in enumerate(plan['rows']):
  if i in closed:continue
  name=re.sub(r'\s+',' ',row['client'].strip())
  if not name:continue
  key=name.casefold()
  if key not in clients:clients[key]={'client':name,'tons':Decimal('0'),'color':color(name),'darkColor':color(name,True)}
  clients[key]['tons']+=row['planned']-row['handed']
 for name,value in plan.get('remainingOverrides',{}).items():
  key=re.sub(r'\s+',' ',name.strip()).casefold()
  if key in clients:clients[key]['calculatedTons']=clients[key]['tons'];clients[key]['tons']=value
 return sorted((r for r in clients.values() if r['tons']>0),key=lambda r:(-r['tons'],r['client'].casefold()))
