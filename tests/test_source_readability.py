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
   self.assertLessEqual(image.width,4000);self.assertTrue(any(t==row[2] for _,t,size in seen));self.assertTrue(any(t=='CLIENT TEST' and size==20 for _,t,size in seen))
   for (x,y),t,size in seen:self.assertGreaterEqual(x,0);self.assertLess(x,image.width);self.assertLess(y+size,image.height)
 def test_total_labels_and_observations_single_line_and_headers_centered(self):
  header=['CLIENT','PRODUS','METAL PLANIFICAT (TONE)','OBSERVATII']
  body=['CLIENT TEST','PRODUS COMPLET','1.25','OBSERVATIE COMPLETA PE UN SINGUR RAND']
  total='TOTAL GENERAL FARA PREDARI (TONE)'
  report={'mode':'plan','week':'W42','date':'2026-10-13','sourceTable':{'rows':[header,body,[total,'','1.25','']],'header':0,'columns':{'client':0,'product':1}}}
  seen=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*a,**kw):seen.append((xy,text,kw['font']));return original(draw,xy,text,*a,**kw)
  with patch.object(ImageDraw.ImageDraw,'text',record):image=source_image(report,LIGHT)
  self.assertGreaterEqual(image.width,2400)
  for value in [*body,total]:self.assertTrue(any(text==value and f.size==20 for xy,text,f in seen))
  ys={xy[1] for xy,text,f in seen if f.size==18};self.assertLessEqual(len(ys),2)
  for xy,text,f in seen:self.assertLessEqual(xy[0]+f.getlength(text),image.width)
 def test_duplicate_plan_caption_hidden_and_total_label_left_aligned(self):
  title='13.10.2026 - PLAN WK 42';total='TOTAL AL (TONE)'
  report={'mode':'plan','week':'W42','date':'2026-10-13','sourceTable':{'rows':[[title],[''],['CLIENT','PRODUS','PREDAT (t)'],['CLIENT TEST','CABLU TEST','1'],[total,'','1']],'header':2,'columns':{'client':0,'product':1}}}
  seen=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*a,**kw):seen.append((xy,text));return original(draw,xy,text,*a,**kw)
  with patch.object(ImageDraw.ImageDraw,'text',record):image=source_image(report,LIGHT)
  self.assertNotIn(title,[t for xy,t in seen]);self.assertEqual(next(xy[0] for xy,t in seen if t==total),46)
  self.assertEqual(image.height,102+82+45+45+38)
  # Other source notes above the heading are preserved.
  report['sourceTable']['rows'][0]=['NOTĂ SPECIALĂ']
  seen.clear()
  with patch.object(ImageDraw.ImageDraw,'text',record):source_image(report,LIGHT)
  self.assertIn('NOTĂ SPECIALĂ',[t for xy,t in seen])
