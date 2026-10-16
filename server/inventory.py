"""Read the established inventory workbook using saved Excel results, no formula execution."""
import base64,zipfile,re,unicodedata
from io import BytesIO
from decimal import Decimal,InvalidOperation
from server import table_import

def norm(value):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFKD',str(value).lower()) if not unicodedata.combining(c)))
def numeric(value):
 try:v=Decimal(str(value).replace(',','.'))
 except InvalidOperation:raise ValueError('Valoare numerică lipsă sau invalidă în inventar. Recalculează și salvează fișierul în Excel.')
 if not v.is_finite() or v<0:raise ValueError('Valoare negativă sau nevalidă în inventar.')
 return v

def read(body):
 if not isinstance(body,dict) or set(body)!={'file','name'}:raise ValueError('Import inventar invalid.')
 name=body['name']
 if not isinstance(name,str) or not name.lower().endswith('.xlsx') or len(name)>150:raise ValueError('Încarcă inventarul .xlsx.')
 parsed=table_import.read({'file':body['file']});sheets={norm(s['name']):s for s in parsed['sheets']}
 if 'situatie' not in sheets or 'aluminiu' not in sheets:raise ValueError('Lipsesc foile SITUATIE sau ALUMINIU.')
 def cell(sheet,address):
  m=re.fullmatch(r'([A-Z]+)(\d+)',address);col=0
  for c in m[1]:col=col*26+ord(c)-64
  rows=sheet['rows'];r=int(m[2])-1
  return rows[r][col-1] if r<len(rows) and col<=len(rows[r]) else ''
 # The same validated archive; retain formulas only as traceable references.
 formulas={}
 with zipfile.ZipFile(BytesIO(base64.b64decode(body['file'],validate=True))) as z:
  wb=table_import.xml(z.read('xl/workbook.xml'));rels={r.attrib['Id']:r.attrib['Target'] for r in table_import.xml(z.read('xl/_rels/workbook.xml.rels'))}
  for sheet in wb.findall('m:sheets/m:sheet',table_import.N):
   key=norm(sheet.attrib['name'])
   if key not in ('situatie','aluminiu'):continue
   path=rels[sheet.attrib['{'+table_import.N['r']+'}id']];path=path.lstrip('/') if path.startswith('/') else 'xl/'+path
   if '..' in path:raise ValueError('Cale Excel invalidă.')
   formulas[key]={};shared={}
   for c in table_import.xml(z.read(path)).findall('m:sheetData/m:row/m:c',table_import.N):
    formula=c.find('m:f',table_import.N)
    if formula is None:continue
    address=c.attrib['r'];expression=formula.text or ''
    if formula.get('t')=='shared':
     si=formula.get('si')
     if expression:shared[si]=(address,expression)
     elif si in shared:
      origin,expression=shared[si];delta=int(re.search(r'\d+',address)[0])-int(re.search(r'\d+',origin)[0])
      expression=re.sub(r'(\$?[A-Z]{1,3})(\$?)(\d+)',lambda m:m[1]+m[2]+str(int(m[3])+(0 if m[2] else delta)),expression)
    formulas[key][address]=expression
 situation=sheets['situatie'];al=sheets['aluminiu']
 if re.sub(r'[$\s]','',formulas['situatie'].get('C22','')).upper()!='C21-C19-C18':raise ValueError('Formula C22 diferă de șablonul confirmat. Verifică inventarul înainte de import.')
 total=numeric(cell(situation,'C22'))/1000;records=[];seen=set()
 for r in range(3,18):
  ref=formulas['situatie'].get('C'+str(r),'').replace('$','');category=cell(situation,'A'+str(r));category_value=numeric(cell(situation,'C'+str(r)) or '0')/1000
  if not category_value:continue
  match=re.fullmatch(r"'?ALUMINIU'?!G(\d+)",ref,re.I)
  if not match:raise ValueError('Nu pot urmări categoria '+category+' în ALUMINIU.')
  target=int(match[1]);summation=formulas['aluminiu'].get('G'+str(target),'').replace('$','')
  span=re.fullmatch(r'SUM\(G(\d+):G(\d+)\)',summation,re.I)
  indices=range(int(span[1]),int(span[2])+1) if span else [target]
  subtotal=Decimal(0)
  for n in indices:
   value=cell(al,'G'+str(n))
   if not value:continue
   tons=numeric(value)/1000
   if not tons:continue
   if n in seen:raise ValueError('Poziție inventar inclusă de două ori.')
   seen.add(n);subtotal+=tons
   records.append({'client':cell(al,'J'+str(n)).strip() or 'Fără client alocat','product':cell(al,'E'+str(n)).strip(),'process':category.strip(),'tons':str(tons),'source':'ALUMINIU!G'+str(n),'formula':formulas['aluminiu'].get('G'+str(n),'Valoare introdusă în Excel')})
  if abs(subtotal-category_value)>Decimal('0.000001'):raise ValueError('Detaliul nu corespunde totalului pentru '+category+'. Recalculează și salvează Excelul.')
 if abs(sum((numeric(r['tons']) for r in records),Decimal(0))-total)>Decimal('0.000001'):raise ValueError('Detaliul inventarului nu se reconciliază cu C22.')
 result={'version':1,'name':name,'date':cell(situation,'A1'),'reference':'SITUATIE!C22','total':str(total),'records':records}
 return validate(result)

def validate(data):
 if not isinstance(data,dict) or set(data)!={'version','name','date','reference','total','records'} or data['version']!=1 or data['reference']!='SITUATIE!C22':raise ValueError('Inventar salvat invalid.')
 from datetime import date
 date.fromisoformat(data['date'])
 if not isinstance(data['name'],str) or len(data['name'])>150 or not isinstance(data['records'],list) or len(data['records'])>500:raise ValueError('Inventar prea mare.')
 total=numeric(data['total']);summed=Decimal(0)
 for row in data['records']:
  if not isinstance(row,dict) or set(row)!={'client','product','process','tons','source','formula'} or any(not isinstance(v,str) or len(v)>150 for v in row.values()):raise ValueError('Rând inventar invalid.')
  summed+=numeric(row['tons'])
 if abs(summed-total)>Decimal('0.000001'):raise ValueError('Inventarul salvat nu se reconciliază.')
 return data

def summary(data,plan_stock,plan_date,plan_rows=()):
 clients={};matches={};details=[]
 for row in plan_rows:
  if row['product'].strip() and row['client'].strip():matches.setdefault(norm(row['product']),set()).add(row['client'].strip())
 for row in data['records']:
  client=row['client'];candidates=matches.get(norm(row['product']),set())
  if client=='Fără client alocat' and len(candidates)==1:client=next(iter(candidates))
  clients[client]=clients.get(client,Decimal(0))+numeric(row['tons']);details.append({**row,'resolvedClient':client})
 plan_clients={norm(r['client']):r['tons'] for r in plan_stock['clients']};comparisons=[]
 for client,value in clients.items():
  old=plan_clients.get(norm(client));comparisons.append({'client':client,'inventory':value,'plan':old,'difference':value-old if old is not None else None})
 for row in plan_stock['clients']:
  if norm(row['client']) not in {norm(c) for c in clients}:comparisons.append({'client':row['client'],'inventory':None,'plan':row['tons'],'difference':None})
 return {'clients':[{'client':c,'tons':v} for c,v in sorted(clients.items())],'extras':{},'total':numeric(data['total']),'missing':[],'basis':'inventory','reference':data['reference'],'date':data['date'],'sameDate':data['date']==plan_date,'comparison':comparisons,'records':details}
