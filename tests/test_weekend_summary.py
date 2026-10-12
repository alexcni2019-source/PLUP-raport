import unittest
from io import BytesIO
from unittest.mock import patch
from PIL import Image, ImageDraw
from server.app import validate_report
from server.corporate import production_image

class WeekendSummaryTests(unittest.TestCase):
 def test_one_report_daily_values_and_sunday_indicators(self):
  payload={'mode':'weekend','date':'2026-10-09','values':{'2026-10-09':{'al':'10','backlogAl':'2','op_previz':'FRIDAY_ONLY'},'2026-10-10':{'al':'20','cu':'1','backlogAl':'3','op_previz':'SATURDAY_ONLY'},'2026-10-11':{'al':'30','backlogCu':'4','op_previz':'SUNDAY_ONLY','obs':'Observații detaliate pentru duminică. '*3}}}
  report=validate_report(payload)
  self.assertEqual(report['total']['handed'],61);self.assertEqual(report['total']['backlog'],9)
  original=ImageDraw.ImageDraw.text
  for theme in ('light','dark'):
   seen=[]
   def record(draw,xy,text,*args,**kwargs):seen.append(text);return original(draw,xy,text,*args,**kwargs)
   with patch.object(ImageDraw.ImageDraw,'text',record):blob=production_image(report,theme=theme)
   self.assertIn('SUNDAY_ONLY',seen);self.assertNotIn('FRIDAY_ONLY',seen);self.assertNotIn('SATURDAY_ONLY',seen)
   for text in ('Vineri','Sâmbătă','Duminică','61 t','9 t'):self.assertIn(text,seen)
   self.assertFalse(any('DEȘEU' in str(text) for text in seen))
   self.assertGreaterEqual(Image.open(BytesIO(blob)).height,1020)
  with self.assertRaises(ValueError):production_image(report,page=1)
