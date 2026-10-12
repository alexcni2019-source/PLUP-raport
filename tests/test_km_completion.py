import unittest
from server.km_completion import close,highlighted
from server.source_render import source_image
from server.corporate import LIGHT,DARK
from unittest.mock import patch
from PIL import ImageDraw

class KmCompletionTests(unittest.TestCase):
 def test_exact_threshold_blanks_and_zeros(self):
  for a,b in [('1,6','1,4'),('2.8 km','2.6'),('1','1.2'),('100','100')]:self.assertTrue(close(a,b))
  for a,b in [('1','0.799999999999'),('','1'),('1',''),('0','0'),('—','0'),('100','99.7'),('1','text')]:self.assertFalse(close(a,b))
 def test_only_both_detail_cells_are_highlighted(self):
  table={'header':0,'rows':[['Produs','KM porniți','KM predați'],['A','2.8','2.6'],['B','2.8','2.599'],['TOTAL','2.8','2.6']]}
  self.assertEqual(highlighted(table),{1:{1,2}})
  for palette in (LIGHT,DARK):
   calls=[];original=ImageDraw.ImageDraw.rectangle
   def record(draw,box,*args,**kwargs):
    if kwargs.get('fill')==palette['success_bg']:calls.append(box)
    return original(draw,box,*args,**kwargs)
   report={'mode':'plan','date':'2026-10-12','sourceTable':{**table,'columns':{},'records':[]}}
   with patch.object(ImageDraw.ImageDraw,'rectangle',record):image=source_image(report,palette)
   self.assertEqual(len(calls),2)
   self.assertGreaterEqual(calls[0][1],166) # Enlarged 64 px header.
   self.assertGreater(image.width,1600)
