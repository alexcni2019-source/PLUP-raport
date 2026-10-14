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
