import unittest
from decimal import Decimal
from server import app
from server.client_flow import build
class ClientFlowTests(unittest.TestCase):
 def test_product_coefficients_and_missing_data(self):
  rows=[]
  for planned,vane in [('10','2'),('20','3')]:
   rows.append({**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':'TEST','planned':planned,'vane':vane})
  payload={'mode':'plan','date':'2026-10-14','week':'W42','incoming':'','rows':rows,'sourceTable':{'version':1,'date':'2026-10-14','header':0,'rows':[['PRODUS','KM PORNITI','KM PREDATI','STOC VANE'],['TEST','10','1','2'],['TEST','5','2','3']],'columns':{'product':0,'vane':3},'records':[{'row':1,'material':'AL'},{'row':2,'material':'AL'}]}}
  result=build(app.process_plan(payload),payload)[0]['stages'];vane=next(x for x in result if x['label']=='Vane')
  self.assertEqual(vane['value'],Decimal('5'));self.assertEqual(vane['tons'],Decimal('14'))
  payload['sourceTable']['rows'][2][1]='';result=build(app.process_plan(payload),payload)[0]['stages']
  self.assertIsNone(next(x for x in result if x['label']=='Vane')['tons'])
