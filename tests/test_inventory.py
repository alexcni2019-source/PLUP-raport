import unittest,base64,zipfile,json,tempfile
from io import BytesIO
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from server import inventory,app,plan_analysis
from server.section_stock import image

def fixture():
 out=BytesIO()
 def cell(address,value,formula=''):
  if isinstance(value,str):return '<c r="'+address+'" t="inlineStr"><is><t>'+value+'</t></is></c>'
  return '<c r="'+address+'">'+('<f>'+formula+'</f>' if formula else '')+'<v>'+str(value)+'</v></c>'
 def sheet(cells):return '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">'+''.join(cells)+'</row></sheetData></worksheet>'
 with zipfile.ZipFile(out,'w') as z:
  z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="SITUATIE" sheetId="1" r:id="r1"/><sheet name="ALUMINIU" sheetId="2" r:id="r2"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
  z.writestr('xl/worksheets/sheet1.xml',sheet([cell('A1','2026-10-15'),cell('A3','BARA'),cell('C3',300,'ALUMINIU!G6'),cell('A7','FUNII'),cell('C7',800,'ALUMINIU!G12'),cell('C22',1100,'C21-C19-C18')]))
  z.writestr('xl/worksheets/sheet2.xml',sheet([cell('E6','9.5'),cell('G6',300),cell('E10','1X240'),cell('G10',500),cell('J10','SBT'),cell('E11','1X120'),cell('G11',300),cell('G12',800,'SUM(G10:G11)')]))
 return {'name':'test.xlsx','file':base64.b64encode(out.getvalue()).decode()}
class InventoryTests(unittest.TestCase):
 def test_cached_inventory_reconciles_and_preserves_unassigned(self):
  data=inventory.read(fixture());self.assertEqual(Decimal(data['total']),Decimal('1.1'))
  summary=inventory.summary(data,{'clients':[{'client':'SBT','tons':Decimal('.4')}]},'2026-10-15',[{'product':'1X120','client':'TUB'}])
  self.assertEqual(sum(r['tons'] for r in summary['clients']),Decimal('1.1'))
  self.assertEqual(next(r for r in summary['clients'] if r['client']=='TUB')['tons'],Decimal('.3'))
  self.assertEqual(next(r for r in summary['comparison'] if r['client']=='SBT')['difference'],Decimal('.1'))
  self.assertEqual(len(summary['records']),3)
 def test_saved_inventory_total_cannot_disagree_with_detail(self):
  data=inventory.read(fixture());data['total']='2'
  with self.assertRaises(ValueError):inventory.validate(data)
 def test_plan_persistence_and_inventory_png(self):
  data=inventory.read(fixture());raw={'mode':'plan','date':'2026-10-15','week':'W42','incoming':'','inventory':data,'rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':'1X240','bar':'1'}]}
  plan=app.process_plan(raw);analysis=plan_analysis.build(plan,raw)
  self.assertEqual(analysis['section_stock']['basis'],'inventory');self.assertEqual(analysis['section_stock']['total'],Decimal('1.1'))
  self.assertTrue(image(plan,analysis,'light').startswith(b'\x89PNG'))
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'DB_PATH',Path(folder)/'db.sqlite3'):
   conn=app.database();conn.execute('INSERT INTO reports VALUES (?,?,?,?,?)',('test','weekday','2026-10-15','now',json.dumps({'mode':'weekday','date':'2026-10-15','values':{'2026-10-15':{}}})));conn.commit();conn.close()
   result=app.plan_insights(plan,raw);self.assertEqual(len(result['section_stock']['productionContext']),1)
