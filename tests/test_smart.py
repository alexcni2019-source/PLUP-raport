import os,tempfile,json,unittest
_test_dir=tempfile.TemporaryDirectory()
os.environ['PLUP_DB_PATH']=os.path.join(_test_dir.name,'test.sqlite')
from server import app,smart,table_import
from pathlib import Path
_original_db=app.DB_PATH
def setUpModule():app.DB_PATH=Path(_test_dir.name)/'test.sqlite'
def tearDownModule():app.DB_PATH=_original_db;_test_dir.cleanup()
from io import BytesIO
import zipfile,base64

def daily(day='2026-10-08',al='10',back='4'):
 return {'mode':'weekday','date':day,'values':{day:{'al':al,'backlogAl':back,'wasteAl':'1'}}}
class Quality(unittest.TestCase):
 def test_versions_restore_conflict(self):
  original=daily();saved=app.save_report(original);changed=daily(al='20');updated=app.update_report(saved['id'],changed,saved['version']);self.assertGreater(updated['version'],saved['version'])
  with self.assertRaises(app.InvalidReport):app.update_report(saved['id'],daily(al='99'),saved['version'])
  restored=app.update_report(saved['id'],original,updated['version'],'restore');self.assertGreater(restored['version'],updated['version'])
  c=app.database();self.assertEqual(c.execute('SELECT count(*) FROM report_versions WHERE report_id=?',(saved['id'],)).fetchone()[0],3);c.close()
 def test_drafts_partial_and_conflict(self):
  c=app.database();body={'payload':{'mode':'forecast','date':'2026-10-08','rows':[{'material':'AL','product':'','km':'','tons':'','client':'','measure':'','status':'','notes':''}]},'metadata':{'needsReview':True,'review':['0:km'],'version':None},'expected':None};r=smart.draft_save(c,body)
  with self.assertRaises(ValueError):smart.draft_save(c,body)
  body['expected']=r['updated_at'];self.assertTrue(smart.draft_save(c,body));c.close()
 def test_analytics_deduplicate_weekend(self):
  app.save_report(daily('2026-09-25','10'));app.save_report({'mode':'weekend','date':'2026-09-25','values':{'2026-09-25':{'al':'20'},'2026-09-26':{'al':'3'}}});c=app.database();r=smart.dashboard(c,'2026-09-27',7,app.validate_report);self.assertEqual(r['current']['handed'],23);self.assertEqual(r['series'][0]['handed'],None);c.close()
 def test_empty_day_is_distinct_from_explicit_zero(self):
  saved=app.save_report(daily('2026-10-01','8'));app.update_report(saved['id'],{'mode':'weekday','date':'2026-10-01','values':{}})
  c=app.database();r=smart.dashboard(c,'2026-10-01',7,app.validate_report);self.assertIsNone(r['series'][-1]['handed']);c.close()
  app.update_report(saved['id'],daily('2026-10-01','0','0'));c=app.database();r=smart.dashboard(c,'2026-10-01',7,app.validate_report);self.assertEqual(r['series'][-1]['handed'],0);c.close()
 def test_checks_thresholds(self):
  result=smart.checks(daily(al='10',back='11'),app.validate_report);self.assertTrue(any('Backlog' in w['message'] for w in result['warnings']));self.assertIn('10 t',result['summary'])
 def test_clipboard_and_xlsx(self):
  self.assertEqual(table_import.read({'text':'Produs\tKM\tTone\nX\t2,5\t3'})['sheets'][0]['rows'][1][1],'2,5')
  b=BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Previz" sheetId="1" r:id="rId1"/></sheets></workbook>')
   z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
   z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Produs</t></is></c><c r="B1" t="inlineStr"><is><t>KM</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>YAKXS</t></is></c><c r="B2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
  result=table_import.read({'file':base64.b64encode(b.getvalue()).decode()});self.assertEqual(result['sheets'][0]['rows'][1],['YAKXS','2']);self.assertTrue(result['sheets'][0]['warnings'])

class PrivateAPI(unittest.TestCase):
 def test_auth_and_csrf_on_new_routes(self):
  import threading,http.client,hashlib,hmac,time
  from http.server import ThreadingHTTPServer
  old_password,old_secret=app.PASSWORD,app.SESSION_SECRET
  app.PASSWORD='test-private-password';app.SESSION_SECRET='test-session-secret-with-32-characters'
  server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def call(method,path,body=None,headers=None):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request(method,path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json',**(headers or {})});r=c.getresponse();result=(r.status,r.read());c.close();return result
  try:
   for path in ['/api/smart/drafts','/api/smart/dashboard?date=2026-10-08&days=7','/api/smart/versions?id=00000000-0000-0000-0000-000000000000']:self.assertEqual(call('GET',path)[0],401)
   stamp=str(int(time.time()));token=stamp+'.'+hmac.new(app.SESSION_SECRET.encode(),stamp.encode(),hashlib.sha256).hexdigest();headers={'Cookie':'plup_session='+token}
   self.assertEqual(call('GET','/api/smart/drafts',headers=headers)[0],200)
   self.assertEqual(call('POST','/api/smart/table',{'text':'Produs\tKM\nX\t2'},headers)[0],403)
   headers['X-CSRF-Token']=hmac.new(app.SESSION_SECRET.encode(),('csrf:'+token).encode(),hashlib.sha256).hexdigest()
   self.assertEqual(call('POST','/api/smart/table',{'text':'Produs\tKM\nX\t2'},headers)[0],200)
   self.assertEqual(call('POST','/api/smart/table',{'text':'Produs\tKM\nX\t2'},{**headers,'Origin':'https://other.invalid'})[0],403)
  finally:server.shutdown();server.server_close();app.PASSWORD,app.SESSION_SECRET=old_password,old_secret

if __name__=='__main__':unittest.main()
