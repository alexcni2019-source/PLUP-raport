import unittest
from decimal import Decimal
from server.section_stock import build,image
from server import app,plan_analysis
class StockTests(unittest.TestCase):
 def test_process_sum_excludes_started_delivered_and_manual_persistence(self):
  row={**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':'1X240','bar':'2','vane':'1','wire':'3'}
  raw={'mode':'plan','date':'2026-10-15','week':'W42','incoming':'','rows':[row],'sectionStock':{'samples':'1,5','waste':'0.2','dead':''}}
  plan=app.process_plan(raw);data=plan_analysis.build(plan,raw);stock=data['section_stock']
  self.assertEqual(stock['clients'][0]['tons'],Decimal('4.80792'));self.assertEqual(stock['total'],Decimal('6.50792'))
  for theme in ['light','dark']:self.assertTrue(image(plan,data,theme).startswith(b'\x89PNG'))
 def test_missing_tonnes_never_silently_replaced_with_zero(self):
  result=build({'client_flow':[{'client':'SBT','stages':[{'label':'Vane','value':Decimal(2),'unit':'km','tons':None},{'label':'KM porniți','value':Decimal(100),'unit':'km','tons':Decimal(60)}]}]}, {'samples':None,'waste':None,'dead':None})
  self.assertIsNone(result['total']);self.assertEqual(result['missing'],['SBT · Vane'])
 def test_old_plans_and_invalid_manual_values(self):
  raw={'mode':'plan','date':'2026-10-15','week':'W42','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL'}]}
  self.assertEqual(app.process_plan(raw)['sectionStock'],{'samples':None,'waste':None,'dead':None})
  raw['sectionStock']={'samples':'-1','waste':'','dead':''}
  with self.assertRaises(ValueError):app.process_plan(raw)
 def test_manual_adjustment_recalculates_without_modifying_inventory_source(self):
  from server.section_stock import adjust
  source={'clients':[{'client':'SBT','tons':Decimal('10')},{'client':'TUB','tons':Decimal('2')}],'extras':{},'total':Decimal('12'),'missing':[],'basis':'inventory'}
  result=adjust(source,{'SBT':Decimal('15.5')})
  self.assertEqual(result['total'],Decimal('17.5'));self.assertEqual(result['referenceTotal'],Decimal('12'));self.assertEqual(source['clients'][0]['tons'],Decimal('10'))
