import unittest
from decimal import Decimal
from server import app
from server.client_flow import build
from server.product_sections import sections,metal_per_km
class ClientFlowTests(unittest.TestCase):
 def test_section_extraction(self):
  for name,total in [('YAKXS 1X240RM','240'),('NA2XBY 3X240SM+120SM','840'),('NFA2X/T2X 50/80L-AL+3X95+2X25','335'),('CYY 5x1,5RE','7.5'),('NAYY 3×150+1×70','520'),('CYY 4*25','100')]:
   self.assertEqual(sections(name)[0],Decimal(total))
  for name in ['ACSR 70/12','UNKNOWN','NAYY 3X240+','NAYY 3X240/120','3X240 2X95']:
   self.assertIsNone(sections(name))
 def test_material_and_stage_formulas(self):
  self.assertEqual(metal_per_km('1X240','AL','vane'),Decimal('0.60264'))
  self.assertEqual(metal_per_km('3X240+120','AL','cable'),Decimal('2.10924'))
  self.assertEqual(metal_per_km('3X240+120','CU','armored'),Decimal('6.95268'))
  self.assertEqual(metal_per_km('3X240+120','AL','vane'),Decimal('0.45198'))
  self.assertEqual(metal_per_km('3X240+95','AL','bar'),Decimal('0.45198'))
  self.assertEqual(metal_per_km('3X240+95','AL','mf'),Decimal('2.046465'))
  self.assertEqual(metal_per_km('3X240','AL','vane'),Decimal('0.60264'))
  self.assertEqual(metal_per_km('3X70RM+54.6','AL','bar')*42,Decimal('5.536755'))
  self.assertEqual(metal_per_km('3X70RM+54.6','CU','vane')*42,Decimal('18.250785'))
 def test_per_product_aggregation_and_ambiguous_products(self):
  rows=[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':p,'mf':km} for p,km in [('1X240','2'),('3X240+120','3')]]
  raw={'mode':'plan','date':'2026-10-14','week':'W42','incoming':'','rows':rows}
  item=build(app.process_plan(raw),raw)[0]['stages'][0]
  self.assertEqual(item['value'],Decimal('5'));self.assertEqual(item['tons'],Decimal('7.53300'))
  rows[1]['product']='UNKNOWN';group=build(app.process_plan(raw),raw)[0];item=group['stages'][0];self.assertIsNone(item['tons']);self.assertEqual(group['warnings'][0]['product'],'UNKNOWN');self.assertEqual(group['warnings'][0]['row'],2)
 def test_third_png_contains_client_process_km_and_tonnes(self):
  from server.corporate import plan_image
  from server.plan_analysis import build as analyze
  from PIL import ImageDraw,Image
  from unittest.mock import patch
  from io import BytesIO
  raw={'mode':'plan','date':'2026-10-14','week':'W42','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':'3X240+120','mf':'3','wire':'2'}]}
  report=app.process_plan(raw);insights=analyze(report,raw)
  for theme in ['light','dark']:
   seen=[];original=ImageDraw.ImageDraw.text
   def capture(draw,xy,value,*args,**kwargs):seen.append(value);return original(draw,xy,value,*args,**kwargs)
   with patch.object(ImageDraw.ImageDraw,'text',capture):result=plan_image(report,theme,insights,'clients')
   self.assertIn('SBT',seen);self.assertIn('Manta finală',seen);self.assertIn('3 km · 6.328 t',seen);self.assertIn('2 t',seen)
   self.assertEqual(Image.open(BytesIO(result)).width,2400)

 def test_closed_products_removed_from_client_totals_and_details(self):
  rows=[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':client,'product':'1X240','vane':'2'} for client in ['RW','SBT','SBT']]
  raw={'mode':'plan','date':'2026-10-14','week':'W42','incoming':'','rows':rows,'sourceTable':{'version':1,'date':'2026-10-14','header':0,'rows':[['PRODUS','KM PORNITI','KM PREDATI','STOC VANE'],['1X240','10','11','2'],['1X240','10','9.5','2'],['1X240','10','9.499','2']],'columns':{'product':0,'vane':3},'records':[{'row':i,'material':'AL'} for i in [1,2,3]]}}
  result=build(app.process_plan(raw),raw)
  self.assertEqual([g['client'] for g in result],['SBT']);self.assertEqual(len(result[0]['products']),1)
  self.assertEqual(next(s for s in result[0]['stages'] if s['label']=='Vane')['value'],Decimal('2'))
