import unittest
from io import BytesIO
from unittest.mock import patch
from PIL import Image,ImageDraw
from server import app,corporate,plan_analysis

class SplitExportTests(unittest.TestCase):
 def text_render(self,fn):
  seen=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*args,**kwargs):seen.append(text);return original(draw,xy,text,*args,**kwargs)
  with patch.object(ImageDraw.ImageDraw,'text',record):image=Image.open(BytesIO(fn()))
  return seen,image
 def test_forecast_splits_work_and_charts_from_table_in_both_themes(self):
  raw={'mode':'forecast','date':'2026-10-12','rows':[{**dict.fromkeys(app.FORECAST_FIELDS,''),'material':'AL','product':'CABLU TEST','km':'2.8','tons':'3','client':'CLIENT TEST','measure':'1000 M/TB','status':'SCH2','priority':'urgent'}]}
  report=app.process_forecast(raw)
  for theme in ['light','dark']:
   with patch.object(corporate,'_forecast_table_image',side_effect=AssertionError('Summary must not render table')):
    seen,image=self.text_render(lambda:corporate.forecast_image(report,theme,False,'summary'))
   self.assertIn('LISTA DE EXECUȚIE · SCHIMBUL 2',seen);self.assertIn('DISTRIBUȚIA TONELOR PE CLIENȚI',seen);self.assertNotIn('STADIU',seen);self.assertEqual(image.width,1672)
   seen,_=self.text_render(lambda:corporate.forecast_image(report,theme,False,'table'))
   self.assertNotIn('LISTA DE EXECUȚIE · SCHIMBUL 2',seen);self.assertNotIn('DISTRIBUȚIA TONELOR PE CLIENȚI',seen);self.assertNotIn('STADIU',seen);self.assertNotIn('SCH2',seen);self.assertIn('CABLU TEST',seen)
 def test_plan_summary_does_not_render_product_table(self):
  raw={'mode':'plan','date':'2026-10-12','week':'w42','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','product':'CABLU TEST','client':'CLIENT TEST','planned':'10','handed':'2','bar':'3'}]}
  report=app.process_plan(raw);insights=plan_analysis.build(report,raw)
  for theme in ['light','dark']:
   with patch.object(corporate,'_plan_table_image',side_effect=AssertionError('Summary must not render table')):
    seen,image=self.text_render(lambda:corporate.plan_image(report,theme,insights,'summary'))
   self.assertIn('SITUAȚIA PE FLUX · KM',seen);self.assertNotIn('CABLU TEST',seen);self.assertEqual(image.width,1672)
   seen,_=self.text_render(lambda:corporate.plan_image(report,theme,insights,'table'))
   self.assertIn('CABLU TEST',seen);self.assertNotIn('SITUAȚIA PE FLUX · KM',seen)
