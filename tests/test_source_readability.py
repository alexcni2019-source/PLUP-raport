import unittest
from PIL import ImageDraw
from unittest.mock import patch
from server.source_render import source_image
from server.corporate import LIGHT,DARK
class ReadabilityTests(unittest.TestCase):
 def test_long_headers_wrap_without_stretching_columns(self):
  head=['','CLIENT','PRODUS','METAL PLANIFICAT ( TONE )','METAL PREDAT ( TONE )','SARMA (TONE)','STOC LITA (TONE)','STOC FUNIE / BARA (KM)','STOC VANE (KM)','STOC CABLAT (KM)','STOC M.I. (KM)','STOC ARMAT (KM)','STOC M.F. (KM)','KM PORNITI','KM PREDATI']
  row=['AL:','CLIENT TEST','NA2XBY/AC2XABY 3X120SM+70SM']+['1.01']*12
  report={'mode':'plan','date':'2026-10-13','sourceTable':{'rows':[head]+[row]*28,'header':0,'columns':{'material':0,'client':1,'product':2}}}
  for palette in [LIGHT,DARK]:
   seen=[];original=ImageDraw.ImageDraw.text
   def record(draw,xy,text,*a,**kw):
    f=kw.get('font');seen.append((xy,text,f.size));return original(draw,xy,text,*a,**kw)
   with patch.object(ImageDraw.ImageDraw,'text',record):image=source_image(report,palette)
   self.assertLessEqual(image.width,2600);self.assertTrue(any(t==row[2] for _,t,size in seen));self.assertTrue(any(t=='CLIENT TEST' and size==20 for _,t,size in seen))
   for (x,y),t,size in seen:self.assertGreaterEqual(x,0);self.assertLess(x,image.width);self.assertLess(y+size,image.height)
