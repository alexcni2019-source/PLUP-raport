import copy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw
from server import app, smart, source_table
from server.corporate import plan_image, forecast_image, production_image


def fixture(mode='plan'):
 fields=app.PLAN_FIELDS if mode=='plan' else tuple(k for k in app.FORECAST_FIELDS if k!='material')
 rows=[['08.10.2026 - TABEL'],['Material','Produs','KM PORNITI','KM PREDATI','Note suplimentare'],['AL','CABLU TEST','2,8','2,766','Text complet'],['TOTAL','','0','','']]
 table={'version':1,'header':1,'rows':rows,'columns':{'material':0,'product':1},'records':[{'row':2,'material':'AL'}],'date':'2026-10-08'}
 payload={'mode':mode,'date':'2026-10-08','rows':[{**{k:'' for k in fields},'material':'AL','product':'CABLU TEST'}],'sourceTable':table}
 if mode=='plan':payload.update(week='w41',incoming='')
 return payload

class SourceTableTests(unittest.TestCase):
 def test_history_draft_and_defaults_keep_every_cell(self):
  with TemporaryDirectory() as tmp:
   original=app.DB_PATH;app.DB_PATH=Path(tmp)/'reports.sqlite'
   try:
    for mode in ('plan','forecast'):
     payload=fixture(mode);saved=app.save_report(payload)
     app.remember_generated(payload);self.assertEqual(app.latest_template(mode)['sourceTable'],payload['sourceTable'])
     conn=app.database()
     import json
     stored=json.loads(conn.execute('SELECT payload FROM reports WHERE id=?',(saved['id'],)).fetchone()[0]);self.assertEqual(stored,payload)
     smart.draft_save(conn,{'payload':payload,'metadata':{},'expected':None});draft=json.loads(conn.execute('SELECT payload FROM drafts WHERE mode=?',(mode,)).fetchone()[0]);self.assertEqual(draft['sourceTable'],payload['sourceTable']);conn.close()
     payload['sourceTable']['rows'][2][3]='2,700';updated=app.update_report(saved['id'],payload,saved['version']);self.assertGreater(updated['version'],saved['version'])
   finally:app.DB_PATH=original
 def test_extra_headers_values_blanks_and_zero_are_rendered(self):
  original=ImageDraw.ImageDraw.text;drawn=[]
  def record(draw,xy,text,*args,**kwargs):drawn.append(text);return original(draw,xy,text,*args,**kwargs)
  for mode,renderer in [('plan',plan_image),('forecast',forecast_image)]:
   for theme in ('light','dark'):
    drawn.clear()
    with patch.object(ImageDraw.ImageDraw,'text',record):image=renderer(app.validate_report(fixture(mode)),theme)
    self.assertIn('KM PORNITI',drawn);self.assertIn('KM PREDATI',drawn);self.assertIn('2,766',drawn);self.assertIn('0',drawn);self.assertIn('Text complet',drawn)
    self.assertGreaterEqual(Image.open(BytesIO(image)).width,1672)
 def test_source_only_and_production_charts_keep_custom_columns(self):
  table=fixture()['sourceTable'];table['columns']={};table['records']=[]
  payload={'mode':'weekday','date':'2026-10-08','values':{},'sourceTable':table}
  self.assertTrue(production_image(app.validate_report(payload)).startswith(b'\x89PNG'))
  table=copy.deepcopy(table);table['columns']={'al':2};table['records']=[{'row':2,'day':0}]
  payload.update(values={'2026-10-08':{'al':'2.8'}},sourceTable=table)
  self.assertGreater(Image.open(BytesIO(production_image(app.validate_report(payload)))).height,1000)
  for mode in ('plan','forecast'):
   p=fixture(mode);p['rows']=[];p['sourceTable']['records']=[];app.validate_report(p)
 def test_status_hidden_only_when_requested(self):
  payload=fixture('forecast');table=payload['sourceTable'];table['rows'][1].append('STADIU');table['rows'][2].append('STATUT_UNIC');table['columns']['status']=5
  rendered=[];original=ImageDraw.ImageDraw.text
  def record(draw,xy,text,*a,**kw):rendered.append(text);return original(draw,xy,text,*a,**kw)
  with patch.object(ImageDraw.ImageDraw,'text',record):forecast_image(app.validate_report(payload),'dark',False)
  self.assertNotIn('STADIU',rendered);self.assertNotIn('STATUT_UNIC',rendered);self.assertIn('KM PREDATI',rendered)
 def test_invalid_shapes_and_column_bindings_rejected(self):
  for mutation in [lambda t:t.update(header=999),lambda t:t['columns'].update(product=45),lambda t:t['rows'][2].append('x'*1001),lambda t:t['records'].append({'row':2,'material':'AL'}),lambda t:t.update(rows=[['x']*41])]:
   table=copy.deepcopy(fixture()['sourceTable']);mutation(table)
   with self.assertRaises(ValueError):source_table.validate(table,'plan')

if __name__=='__main__':unittest.main()
