import unittest
from io import BytesIO
from unittest.mock import patch
from PIL import Image,ImageColor,ImageDraw
from server import app,corporate,plan_analysis

class SplitExportTests(unittest.TestCase):
 def text_render(self,fn):
  seen=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*args,**kwargs):seen.append(text);return original(draw,xy,text,*args,**kwargs)
  with patch.object(ImageDraw.ImageDraw,'text',record):image=Image.open(BytesIO(fn()))
  return seen,image
 def test_forecast_summary_and_table_can_still_render_separately(self):
  raw={'mode':'forecast','date':'2026-10-12','rows':[{**dict.fromkeys(app.FORECAST_FIELDS,''),'material':'AL','product':'CABLU TEST','km':'2.8','tons':'3','client':'CLIENT TEST','measure':'1000 M/TB','status':'SCH2','priority':'urgent'}]}
  raw['rows'].append({**raw['rows'][0],'product':'CABLU NORMAL','priority':'normal'})
  report=app.process_forecast(raw)
  for theme in ['light','dark']:
   with patch.object(corporate,'_forecast_table_image',side_effect=AssertionError('Summary must not render table')):
    seen,image=self.text_render(lambda:corporate.forecast_image(report,theme,False,'summary'))
   self.assertNotIn('LISTA DE EXECUȚIE · SCHIMBUL 2',seen);self.assertIn('DISTRIBUȚIA TONELOR PE CLIENȚI',seen);self.assertNotIn('STADIU',seen);self.assertEqual(image.width,1672)
   palette=corporate.DARK if theme=='dark' else corporate.LIGHT
   with patch('server.corporate.priority_dot',wraps=corporate.priority_dot) as dot:
    seen,table=self.text_render(lambda:corporate.forecast_image(report,theme,False,'table'))
   self.assertEqual([call.args[2] for call in dot.call_args_list],['urgent','normal'])
   for call in dot.call_args_list:
    _,center,priority,*_=call.args
    self.assertEqual(table.getpixel(center),ImageColor.getrgb(palette['priority_'+priority]))
   self.assertNotIn('URGENT',seen)
   self.assertNotIn('PRIORITATE',seen)
   self.assertNotIn('LISTA DE EXECUȚIE · SCHIMBUL 2',seen);self.assertNotIn('DISTRIBUȚIA TONELOR PE CLIENȚI',seen);self.assertNotIn('STADIU',seen);self.assertNotIn('SCH2',seen);self.assertIn('CABLU TEST',seen)
 def test_full_forecast_ends_with_table_totals_and_respects_status(self):
  raw={'mode':'forecast','date':'2026-10-12','rows':[{**dict.fromkeys(app.FORECAST_FIELDS,''),'material':'AL','product':'CABLU TEST','km':'2.8','tons':'3','client':'CLIENT TEST','measure':'1000 M/TB','status':'SCH2','priority':'urgent'}]}
  report=app.process_forecast(raw)
  for theme in ('light','dark'):
   for show_status in (True,False):
    seen,image=self.text_render(lambda:corporate.forecast_image(report,theme,show_status,'all'))
    for label in ('TOTAL PREVIZ','DISTRIBUȚIA TONELOR PE CLIENȚI','TOTAL AL + CU'):
     self.assertIn(label,seen)
    for label in ('STADIU','SCH2'):
     self.assertEqual(label in seen,show_status)
    self.assertEqual(seen.count('NRG Cables'),1)
    self.assertNotIn('LISTA DE EXECUȚIE · SCHIMBUL 2',seen)
    with Image.open(BytesIO(corporate.forecast_image(report,theme,show_status,'table'))) as table:
     # The complete image ends with the same table, including its bottom margin.
     body=table.crop((0,87,table.width,table.height))
     self.assertEqual(image.crop((0,image.height-body.height,image.width,image.height)).tobytes(),body.tobytes())
 def test_plan_summary_does_not_render_product_table(self):
  raw={'mode':'plan','date':'2026-10-12','week':'w42','incoming':'','rows':[{**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','product':'CABLU TEST','client':'CLIENT TEST','planned':'10','handed':'2','bar':'3'}]}
  report=app.process_plan(raw);insights=plan_analysis.build(report,raw)
  for theme in ['light','dark']:
   with patch.object(corporate,'_plan_table_image',side_effect=AssertionError('Summary must not render table')):
    seen,image=self.text_render(lambda:corporate.plan_image(report,theme,insights,'summary'))
   self.assertIn('SITUAȚIA PE FLUX · KM',seen);self.assertNotIn('CABLU TEST',seen);self.assertEqual(image.width,1672)
   seen,_=self.text_render(lambda:corporate.plan_image(report,theme,insights,'table'))
   self.assertIn('CABLU TEST',seen);self.assertNotIn('SITUAȚIA PE FLUX · KM',seen)
   seen,mobile=self.text_render(lambda:corporate.plan_image(report,theme,insights,'overview'))
   self.assertEqual(mobile.width,840)
   self.assertIn('Rest de predat',seen)
   self.assertIn('AL · Aluminiu',seen)
