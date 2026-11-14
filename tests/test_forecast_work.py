import copy,unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import ImageDraw
from server import app,smart
from server.forecast_work import drum_plan
from server.corporate import forecast_image

def row(**changes):return {**dict.fromkeys(app.FORECAST_FIELDS,''),'material':'AL','product':'CABLU TEST','km':'2.8','tons':'3','measure':'1000 M/TB',**changes}
def payload(rows):return {'mode':'forecast','date':'2026-10-12','rows':rows}

class ForecastWorkTests(unittest.TestCase):
 def test_exact_drums_remainder_and_no_guessing(self):
  p=app.process_forecast(payload([row()]));calc=p['work'][0]['drums'];self.assertEqual((calc['count'],calc['full'],calc['remainder']),(3,2,800));self.assertEqual(calc['text'],'2 × 1000 m + 1 × 800 m')
  self.assertEqual(app.process_forecast(payload([row(km='3')]))['work'][0]['drums']['count'],3)
  self.assertIsNone(app.process_forecast(payload([row(measure='1500 M/TB - MAX TB E24')]))['work'][0]['drums'])
  self.assertIsNone(app.process_forecast(payload([row(measure='1.000 M/TB')]))['work'][0]['drums'])
  calc=app.process_forecast(payload([row(measure='Măsurare complexă',drumLength='500')]))['work'][0]['drums'];self.assertEqual(calc['count'],6);self.assertEqual(calc['remainder'],300)
 def test_execution_order_priority_and_validation(self):
  data=payload([row(product='A',order='2'),row(product='B',order='1',priority='URGENT')]);work=app.process_forecast(data)['work'];self.assertEqual([r['product'] for r in work],['B','A']);self.assertEqual(work[0]['priority'],'urgent')
  for changes in [{'order':'1'},{'priority':'nonsense'},{'drumLength':'0'}]:
   bad=payload([row(**changes),row(product='B')])
   with self.assertRaises(app.InvalidReport):app.process_forecast(bad)
 def test_default_order_matches_standard_material_groups(self):
  raw=payload([row(product='A'),row(material='CU',product='B'),row(product='C')])
  self.assertEqual([r['product'] for r in app.process_forecast(raw)['work']],['A','C','B'])
 def test_new_fields_survive_history_and_drafts(self):
  original=app.DB_PATH
  with TemporaryDirectory() as tmp:
   app.DB_PATH=Path(tmp)/'data.sqlite'
   try:
    raw=payload([row(order='1',priority='urgent',drumLength='1000')]);record=app.save_report(raw)
    conn=app.database();smart.draft_save(conn,{'payload':raw,'metadata':{},'expected':None})
    import json
    restored=json.loads(conn.execute('SELECT payload FROM reports WHERE id=?',(record['id'],)).fetchone()[0]);self.assertEqual(restored,raw);conn.close()
    app.process_forecast(payload([row()])) # Legacy rows remain valid.
   finally:app.DB_PATH=original
 def test_source_columns_and_status_hidden_export(self):
  raw=payload([row(order='1',priority='urgent',notes='MAX TB E24')]);raw['sourceTable']={'version':1,'header':0,'date':raw['date'],'rows':[['Produs','Ordine','Prioritate','Metri pe tambur','Observații'],['CABLU TEST','1','urgent','1000','MAX TB E24']],'columns':{'product':0,'order':1,'priority':2,'drumLength':3,'notes':4},'records':[{'row':1,'material':'AL'}]}
  from server.source_render import priority_dot
  original=ImageDraw.ImageDraw.text;seen=[]
  def record(draw,xy,text,*a,**kw):seen.append(text);return original(draw,xy,text,*a,**kw)
  for mapped in (True,False):
   if not mapped:
    for key in ('product','priority','drumLength'):
     del raw['sourceTable']['columns'][key]
   seen.clear()
   report=app.process_forecast(raw)
   with patch.object(ImageDraw.ImageDraw,'text',record),patch('server.source_render.priority_dot',wraps=priority_dot) as dot:
    forecast_image(report,'light',False)
   dot.assert_called_once()
   self.assertEqual(dot.call_args.args[2],'urgent')
   self.assertTrue({'Produs','CABLU TEST','Ordine','MAX TB E24'}.issubset(seen))
   self.assertFalse({'LISTA DE EXECUȚIE · SCHIMBUL 2','URGENT','urgent','Prioritate','Metri pe tambur','1000','STADIU'}.intersection(seen))
