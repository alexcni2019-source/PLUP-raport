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
  result=build({'client_flow':[{'client':'SBT','stages':[{'label':'Vane','value':Decimal(2),'unit':'km','tons':None},{'label':'KM porniți','value':Decimal(100),'unit':'km','tons':Decimal(60)}]}]}, {'samples':None,'waste':None,'dead':None,'blocked':None})
  self.assertIsNone(result['total']);self.assertEqual(result['missing'],['SBT · Vane'])
 def test_old_plans_and_invalid_manual_values(self):
  raw={'mode':'plan','date':'2026-10-15','week':'W42','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL'}]}
  self.assertEqual(app.process_plan(raw)['sectionStock'],{'samples':None,'waste':None,'dead':None,'blocked':None,'bar95':None,'bar15':None})
  raw['sectionStock']={'samples':'-1','waste':'','dead':''}
  with self.assertRaises(ValueError):app.process_plan(raw)
 def test_manual_adjustment_recalculates_without_modifying_inventory_source(self):
  from server.section_stock import adjust
  source={'clients':[{'client':'SBT','tons':Decimal('10')},{'client':'TUB','tons':Decimal('2')}],'extras':{},'total':Decimal('12'),'missing':[],'basis':'inventory'}
  result=adjust(source,{'SBT':Decimal('15.5')})
  self.assertEqual(result['total'],Decimal('17.5'));self.assertEqual(result['referenceTotal'],Decimal('12'));self.assertEqual(source['clients'][0]['tons'],Decimal('10'))
 def test_client_name_can_change_without_changing_tonnes(self):
  from server.section_stock import adjust
  source={'clients':[{'client':'SBT','tons':Decimal('10')}],'extras':{'samples':Decimal('1')},'total':Decimal('11'),'missing':[]}
  result=adjust(source,{}, {'SBT':'CLIENT NOU'})
  self.assertEqual(result['clients'][0]['client'],'CLIENT NOU');self.assertEqual(result['total'],Decimal('11'));self.assertEqual(result['clients'][0]['sourceClient'],'SBT')

 def test_separate_subtotals_include_client_adjustments(self):
  from server.section_stock import adjust
  source={'clients':[{'client':'SBT','tons':Decimal('10')},{'client':'TUB','tons':Decimal('2')}],'extras':{'samples':Decimal('1'),'waste':Decimal('.2'),'dead':Decimal('.3')},'total':Decimal('13.5'),'missing':[]}
  original=adjust(source,{})
  self.assertEqual(original['clientsTotal'],Decimal('12'));self.assertEqual(original['otherTotal'],Decimal('1.5'))
  edited=adjust(source,{'SBT':Decimal('15')})
  self.assertEqual(edited['clientsTotal'],Decimal('17'));self.assertEqual(edited['total'],edited['clientsTotal']+edited['otherTotal'])

 def test_blocked_semifinished_stock_is_saved_and_added(self):
  raw={'mode':'plan','date':'2026-10-15','week':'W42','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL'}],'sectionStock':{'samples':'1','waste':'2','dead':'3','blocked':'4.5'}}
  plan=app.process_plan(raw);data=plan_analysis.build(plan,raw)['section_stock']
  self.assertEqual(plan['sectionStock']['blocked'],Decimal('4.5'));self.assertEqual(data['otherTotal'],Decimal('10.5'));self.assertEqual(data['total'],Decimal('10.5'))

 def test_add_delete_clients_persist_and_export(self):
  raw={'mode':'plan','date':'2026-10-16','week':'W43','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':'1X240','wire':'3'}],'stockAdjustments':{'SBT':'0','Nou':'7.4'},'stockNames':{'Nou':'Client nou'},'sectionStock':{'samples':'1','waste':'2','dead':'','blocked':'0.5'}}
  report=app.process_plan(raw);data=plan_analysis.build(report,raw);stock=data['section_stock']
  self.assertEqual([(r['client'],r['tons']) for r in stock['clients']],[('Client nou',Decimal('7.4'))])
  self.assertEqual(stock['clientsTotal'],Decimal('7.4'));self.assertEqual(stock['total'],Decimal('10.9'))
  self.assertEqual(report['stockAdjustments']['SBT'],Decimal('0'))
  for theme in ['light','dark']:self.assertTrue(image(report,data,theme).startswith(b'\x89PNG'))

 def test_bar_stock_sizes_saved_totalled_and_rendered(self):
  raw={'mode':'plan','date':'2026-10-16','week':'W43','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL'}],'sectionStock':{'samples':'1','waste':'2','dead':'','bar95':'3,25','bar15':'4.5'}}
  report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  self.assertEqual(report['sectionStock']['bar95'],Decimal('3.25'))
  self.assertEqual(report['sectionStock']['bar15'],Decimal('4.5'))
  self.assertEqual(data['section_stock']['otherTotal'],Decimal('10.75'))
  self.assertEqual(data['section_stock']['total'],Decimal('10.75'))
  for theme in ['light','dark']:self.assertTrue(image(report,data,theme).startswith(b'\x89PNG'))
