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
  self.assertEqual(metal_per_km('1X240','AL','vane'),Decimal('0.59616'))
  self.assertEqual(metal_per_km('3X240+120','AL','cable'),Decimal('2.08656'))
  self.assertEqual(metal_per_km('3X240+120','CU','armored'),Decimal('6.95268'))
  self.assertIsNone(metal_per_km('3X240+120','AL','vane'))
 def test_per_product_aggregation_and_ambiguous_products(self):
  rows=[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':p,'mf':km} for p,km in [('1X240','2'),('3X240+120','3')]]
  raw={'mode':'plan','date':'2026-10-14','week':'W42','incoming':'','rows':rows}
  item=build(app.process_plan(raw),raw)[0]['stages'][0]
  self.assertEqual(item['value'],Decimal('5'));self.assertEqual(item['tons'],Decimal('7.45200'))
  rows[1]['product']='UNKNOWN';group=build(app.process_plan(raw),raw)[0];item=group['stages'][0];self.assertIsNone(item['tons']);self.assertEqual(group['warnings'][0]['product'],'UNKNOWN');self.assertEqual(group['warnings'][0]['row'],2)
