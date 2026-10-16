import unittest
from unittest.mock import patch
from decimal import Decimal
from PIL import ImageDraw
from server import app,plan_analysis
from server.corporate import plan_image
from server.plan_clients import color

def row(client='CLIENT TEST',**kw):return {**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','product':'PRODUS TEST','client':client,'planned':'10','handed':'2',**kw}
def payload(rows):return {'mode':'plan','week':'W42','date':'2026-10-13','incoming':'','rows':rows}
class PlanVisualTests(unittest.TestCase):
 def test_remaining_all_positions_and_stable_colors(self):
  raw=payload([row('SBT'),row('sbt',planned='1',handed='0'),row('NO',handed=''),row('OVER',planned='1',handed='2'),row('',handed='0')]);data=plan_analysis.build(app.process_plan(raw),raw)
  self.assertEqual(len(data['clients']),2);totals={r['client']:r['tons'] for r in data['clients']};self.assertEqual(totals['NO'],Decimal('10'));self.assertEqual(totals['SBT'],Decimal('9'))
  self.assertEqual(color(' SBT '),color('sbt'));self.assertEqual(len({color(x) for x in ['SBT','TUB','HELU','LEMAR','VEREX-EL','SONEPAR RW']}),6)
 def test_export_independent_rings_goods_separate_no_evolution(self):
  raw=payload([row(vane='0.5',cable='0',goods='2')]);report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  for theme in ['light','dark']:
   seen=[];arcs=[];original=ImageDraw.ImageDraw.text;arc=ImageDraw.ImageDraw.arc
   def record(draw,xy,text,*a,**kw):seen.append(text);return original(draw,xy,text,*a,**kw)
   def record_arc(draw,box,start,end,*a,**kw):arcs.append(end-start);return arc(draw,box,start,end,*a,**kw)
   with patch.object(ImageDraw.ImageDraw,'text',record),patch.object(ImageDraw.ImageDraw,'arc',record_arc):plan_image(report,theme,data,'summary')
   self.assertIn('REST DE PREDAT PLAN LANSAT',seen);self.assertIn('0.5 km',seen);self.assertIn('2 km',seen);self.assertIn('Marfă predată',seen);self.assertNotIn('EVOLUȚIE',seen);self.assertEqual(arcs,[360])
 def test_no_empty_client_section(self):
  raw=payload([row(planned='')]);data=plan_analysis.build(app.process_plan(raw),raw);self.assertEqual(data['clients'],[])

 def test_total_subtraction_after_grouping_not_per_row_clamping(self):
  raw=payload([row('SBT',planned='10',handed=''),row('sbt',planned='1',handed='2')]);data=plan_analysis.build(app.process_plan(raw),raw)
  self.assertEqual(data['clients'][0]['tons'],Decimal('9'))

 def test_wire_indicator_separate_from_kilometre_rings(self):
  raw=payload([row(vane='12.05',wire='15.05')]);report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  for theme in ['light','dark']:
   seen=[];original=ImageDraw.ImageDraw.text
   def record(draw,xy,text,*a,**kw):seen.append(text);return original(draw,xy,text,*a,**kw)
   with patch.object(ImageDraw.ImageDraw,'text',record):plan_image(report,theme,data,'summary')
   self.assertIn('Sârmă',seen);self.assertIn('15.05 t',seen);self.assertNotIn('Lită',seen);self.assertIn('12.05 km',seen)
 def test_client_remainder_reconciles_totals_with_unrecorded_handovers(self):
  raw=payload([row('SBT',planned='20',handed='5'),row('HELU',planned='10',handed=''),row('SBT',planned='3',handed='1')]);report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  self.assertEqual(sum(r['tons'] for r in data['clients']),data['planned']-data['handed'])
  self.assertEqual({r['client']:r['tons'] for r in data['clients']},{'SBT':Decimal('17'),'HELU':Decimal('10')})

 def test_fune_header_repairs_old_unmapped_history_without_mutation(self):
  for header in ['STOC FUNIE / BARA (KM)','STOC FUNII (KM)','STOC FUNE / BARĂ (KM)']:
   raw=payload([row()]);raw['sourceTable']={'version':1,'date':raw['date'],'header':0,'rows':[['PRODUS',header],['PRODUS TEST','2,6']],'columns':{'product':0},'records':[{'row':1,'material':'AL'}]}
   report=app.process_plan(raw);data=plan_analysis.build(report,raw)
   self.assertEqual(next(s['current'] for s in data['stages'] if s['key']=='bar'),Decimal('2.6'))
   self.assertNotIn('bar',raw['sourceTable']['columns']);self.assertEqual(raw['rows'][0]['bar'],'')
 def test_ambiguous_fune_headers_are_not_guessed(self):
  raw=payload([row()]);raw['sourceTable']={'version':1,'date':raw['date'],'header':0,'rows':[['PRODUS','STOC FUNIE (KM)','STOC BARA (KM)'],['PRODUS TEST','2','3']],'columns':{'product':0},'records':[{'row':1,'material':'AL'}]}
  data=plan_analysis.build(app.process_plan(raw),raw);self.assertIsNone(next(s['current'] for s in data['stages'] if s['key']=='bar'))

 def test_remaining_tonnes_exclude_closed_products_then_sum_open_differences(self):
  raw=payload([row('SBT'),row('SBT'),row('HELU')])
  raw['sourceTable']={'version':1,'date':raw['date'],'header':0,'rows':[['PRODUS','KM PORNITI','KM PREDATI'],['PRODUS TEST','10','9,5'],['PRODUS TEST','10','9.4999'],['PRODUS TEST','5','8']],'columns':{'product':0},'records':[{'row':1,'material':'AL'},{'row':2,'material':'AL'},{'row':3,'material':'AL'}]}
  report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  self.assertEqual({r['client']:r['tons'] for r in data['clients']},{'SBT':Decimal('8')})
  self.assertEqual(report['totals']['AL']['planned'],Decimal('30'));self.assertEqual(report['totals']['AL']['handed'],Decimal('6'))

 def test_empty_or_zero_started_cells_do_not_exclude_positions(self):
  raw=payload([row('SBT'),row('SBT')])
  raw['sourceTable']={'version':1,'date':raw['date'],'header':0,'rows':[['PRODUS','KM PORNITI','KM PREDATI'],['PRODUS TEST','',''],['PRODUS TEST','0','0']],'columns':{'product':0},'records':[{'row':1,'material':'AL'},{'row':2,'material':'AL'}]}
  data=plan_analysis.build(app.process_plan(raw),raw)
  self.assertEqual(data['clients'][0]['tons'],Decimal('16'))

 def test_remaining_client_override_is_saved_and_independent_of_stock(self):
  raw=payload([row('SBT',planned='10',handed='2',vane='1')]);raw['remainingOverrides']={'SBT':'7.4'}
  report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  self.assertEqual(data['clients'][0]['tons'],Decimal('7.4'));self.assertEqual(data['clients'][0]['calculatedTons'],Decimal('8'));self.assertEqual(data['remaining_total'],Decimal('7.4'))
  self.assertEqual(report['remainingOverrides']['SBT'],Decimal('7.4'));self.assertEqual(report['totals']['AL']['planned'],Decimal('10'))
 def test_explicit_remaining_total_is_exported_and_saved(self):
  raw=payload([row('SBT')]);raw['remainingOverrides']={'SBT':'7.4'};raw['remainingTotalOverride']='8.92'
  report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  self.assertEqual(data['remaining_total'],Decimal('8.92'));self.assertEqual(report['remainingTotalOverride'],Decimal('8.92'))
  seen=[];original=ImageDraw.ImageDraw.text
  def capture(draw,xy,value,*args,**kwargs):seen.append(value);return original(draw,xy,value,*args,**kwargs)
  with patch.object(ImageDraw.ImageDraw,'text',capture):plan_image(report,'light',data,'summary')
  self.assertIn('8.92 t',seen)

 def test_remaining_editor_rename_add_remove_and_saved_round_trip(self):
  raw=payload([row('SBT'),row('TUB')]);raw['remainingOverrides']={'SBT':'0','TUB':'0','Client redenumit':'7.4','Client nou':'2.3'}
  report=app.process_plan(raw);data=plan_analysis.build(report,raw)
  self.assertEqual({r['client']:r['tons'] for r in data['clients']},{'Client redenumit':Decimal('7.4'),'Client nou':Decimal('2.3')})
  self.assertEqual(data['remaining_total'],Decimal('9.7'))
  self.assertEqual(report['totals']['AL']['planned'],Decimal('20'))
