import unittest
from io import BytesIO
from PIL import Image,ImageDraw
from unittest.mock import patch
from server import app
from server.forecast_clients import distribution
from server.corporate import forecast_image

class ForecastClientTests(unittest.TestCase):
 def fixture(self):
  rows=[]
  for client,tons in [('CLIENT A','2'),('client   a','3'),('CLIENT B','4'),('','1'),('CLIENT ZERO','0')]:
   rows.append({**dict.fromkeys(app.FORECAST_FIELDS,''),'material':'AL','product':'CABLU TEST','client':client,'tons':tons,'km':'1'})
  return app.process_forecast({'mode':'forecast','date':'2026-10-12','rows':rows})
 def test_aggregate_and_keep_unknown_clients(self):
  rows,note=distribution(self.fixture())
  self.assertEqual([r['tons'] for r in rows],[5,4,1]);self.assertEqual([r['percent'] for r in rows],[50,40,10]);self.assertEqual(rows[-1]['client'],'Client necompletat')
 def test_source_requires_associations(self):
  report=self.fixture();report['sourceTable']={'columns':{'tons':1}}
  rows,note=distribution(report);self.assertEqual(rows,[]);self.assertIn('Asociază',note)
 def test_chart_render_preserves_status_hiding_and_long_names(self):
  report=self.fixture();report['rows'][0]['client']='CLIENT CU NUME FOARTE LUNG '*8
  original=ImageDraw.ImageDraw.text
  for theme in ('light','dark'):
   seen=[]
   def record(draw,xy,text,*a,**kw):seen.append(text);return original(draw,xy,text,*a,**kw)
   with patch.object(ImageDraw.ImageDraw,'text',record):blob=forecast_image(report,theme,False)
   self.assertIn('DISTRIBUȚIA TONELOR PREVIZIONATE PE CLIENȚI',seen);self.assertNotIn('STADIU',seen)
   self.assertGreater(Image.open(BytesIO(blob)).height,800)
