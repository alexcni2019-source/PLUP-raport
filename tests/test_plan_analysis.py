import copy,unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from server import app,plan_analysis
from server.corporate import plan_image
from PIL import Image
from io import BytesIO

def row(product,planned,handed,bar,cable='',client='CLIENT TEST'):
 return {**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':client,'product':product,'planned':planned,'handed':handed,'bar':bar,'cable':cable}
def payload(stamp,rows):return {'mode':'plan','date':stamp,'week':'w42','incoming':'','rows':rows}

class PlanAnalysisTests(unittest.TestCase):
 def test_common_positions_exclude_new_missing_and_ambiguous(self):
  old=payload('2026-10-09',[row('A','10','2','8','1'),row('DISPĂRUT','8','0','4')]);now=payload('2026-10-12',[row('A','10','5','3','4'),row('NOU','20','15','25')])
  result=plan_analysis.build(app.process_plan(now),now,app.process_plan(old),old)
  self.assertEqual(result['planned'],30);self.assertEqual(result['handed'],20)
  comparison=result['comparison'];self.assertEqual((comparison['common'],comparison['new'],comparison['missing']),(1,1,1))
  self.assertEqual(comparison['metrics'][0]['delta'],3)
  bar=next(r for r in comparison['metrics'] if r['label']=='Fune / bară');self.assertEqual(bar['delta'],-5);self.assertEqual(bar['unit'],'km')
  now['rows'].append(copy.deepcopy(now['rows'][0]));result=plan_analysis.build(app.process_plan(now),now,app.process_plan(old),old)
  self.assertEqual(result['comparison']['common'],0);self.assertIsNone(result['comparison']['metrics'][0]['delta'])
 def test_missing_cells_do_not_become_numeric_progress(self):
  old=payload('2026-10-09',[row('A','10','2','')]);now=payload('2026-10-12',[row('A','10','5','3')])
  result=plan_analysis.build(app.process_plan(now),now,app.process_plan(old),old)
  bar=next(r for r in result['comparison']['metrics'] if r['label']=='Fune / bară');self.assertIsNone(bar['delta'])
  self.assertIsNone(next(r for r in result['stages'] if r['key']=='mf')['current'])
 def test_source_only_custom_columns_are_not_invented_metrics(self):
  raw=payload('2026-10-12',[])
  raw['sourceTable']={'version':1,'header':0,'rows':[['PRODUS','KM PORNITI'],['CABLU TEST','7']],'columns':{},'records':[],'date':'2026-10-12'}
  result=plan_analysis.build(app.process_plan(raw),raw)
  self.assertIsNone(result['planned']);self.assertIsNone(result['handed']);self.assertIsNone(result['percent'])
  self.assertTrue(all(r['current'] is None for r in result['stages']))
 def test_generated_snapshot_and_history_lookup_respect_dates(self):
  original=app.DB_PATH
  with TemporaryDirectory() as tmp:
   app.DB_PATH=Path(tmp)/'db.sqlite'
   try:
    old=payload('2026-10-09',[row('A','10','2','8','1')]);app.remember_generated(old)
    now=payload('2026-10-12',[row('A','10','5','3','4')]);report=app.process_plan(now);result=app.plan_insights(report,now)
    self.assertEqual(result['comparison']['date'],'2026-10-09')
    app.remember_generated(now);self.assertEqual(app.plan_insights(app.process_plan(old),old)['comparison'],None)
    for theme in ('light','dark'):
     image=Image.open(BytesIO(plan_image(report,theme,result)));self.assertGreaterEqual(image.width,1672)
   finally:app.DB_PATH=original
