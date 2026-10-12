import unittest
from unittest.mock import patch
from PIL import ImageDraw
from server import app,plan_analysis
from server.corporate import plan_image,forecast_image

class CleanReportTests(unittest.TestCase):
 def test_empty_analysis_and_technical_explanations_are_omitted(self):
  row={**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'CLIENT TEST','product':'CABLU TEST','planned':'10','handed':'2','vane':'3'}
  raw={'mode':'plan','date':'2026-10-12','week':'w42','incoming':'','rows':[row]};report=app.process_plan(raw);analysis=plan_analysis.build(report,raw)
  seen=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*a,**kw):seen.append(text);return original(draw,xy,text,*a,**kw)
  with patch.object(ImageDraw.ImageDraw,'text',record):plan_image(report,'light',analysis)
  joined=' '.join(seen).casefold()
  for phrase in ['necompletat','poziții comparabile','comparație după','sinteza folosește','nu se adună','comparația apare','stoc lită']:
   self.assertNotIn(phrase,joined)
  self.assertIn('3 km',seen);self.assertNotIn('Fune / bară',seen);self.assertNotIn('EVOLUȚIE',seen)
 def test_only_metrics_with_paired_values_are_analyzed(self):
  base={**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'CLIENT TEST','product':'A','planned':'10','handed':'2','bar':'3'}
  old={'mode':'plan','date':'2026-10-09','week':'w42','incoming':'','rows':[base,{**base,'product':'B','handed':''}]}
  now={**old,'date':'2026-10-12','rows':[{**base,'handed':'5'},{**base,'product':'B','handed':'7'}]}
  result=plan_analysis.build(app.process_plan(now),now,app.process_plan(old),old)
  metric=result['comparison']['metrics'][0];self.assertEqual(metric['delta'],3);self.assertEqual(metric['positions'],1)
 def test_export_has_no_drum_hint_for_ambiguous_measure(self):
  raw={'mode':'forecast','date':'2026-10-12','rows':[{**dict.fromkeys(app.FORECAST_FIELDS,''),'material':'AL','product':'CABLU TEST','km':'2','tons':'1','measure':'1000 M/TB + 500 M/TB'}]}
  seen=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*a,**kw):seen.append(text);return original(draw,xy,text,*a,**kw)
  with patch.object(ImageDraw.ImageDraw,'text',record):forecast_image(app.process_forecast(raw),'light',False)
  joined=' '.join(seen)
  self.assertNotIn('Completează',joined);self.assertNotIn('Client necompletat',joined);self.assertNotIn('Cantități previzionate;',joined)
