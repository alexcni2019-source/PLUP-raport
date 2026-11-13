import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from server import app, identity, members, smart


PLAN={'mode':'plan','date':'2026-11-12','week':'W47','incoming':'','rows':[{'material':'AL','product':'PRIVATE PLAN','client':'A','planned':'2'},{'material':'CU','product':'CU PLAN','client':'B','planned':'1','handed':''}]}
FORECAST={'mode':'forecast','date':'2026-11-12','rows':[{'material':'CU','product':'ALLOWED FORECAST','client':'B','km':'1','tons':'2'}]}

for row in PLAN['rows']:
    for key in app.PLAN_FIELDS:row.setdefault(key,'')
for row in FORECAST['rows']:
    for key in app.FORECAST_FIELDS:row.setdefault(key,'')

class MembersTest(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.dbpatch=patch.object(app,'DB_PATH',Path(self.temp.name)/'data.sqlite3');self.dbpatch.start()
        self.env=patch.dict(os.environ,{'PLUP_AUTH_MODE':'github','PLUP_PUBLIC_ORIGIN':'https://example.test','PLUP_GITHUB_CLIENT_ID':'test','PLUP_GITHUB_CLIENT_SECRET':'test-secret','PLUP_GITHUB_ALLOWED_ID':'123'})
        self.env.start();identity.SESSIONS.clear();members.FAILURES.clear()
        identity.SESSIONS['owner-session']={'owner':'123','expires':time.time()+3600}
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        conn=app.database();conn.close()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.env.stop();self.dbpatch.stop();self.temp.cleanup()

    def request(self,method,path,body=None,token='owner-session',csrf=True,origin=True):
        owner=token=='owner-session'
        headers={'Content-Type':'application/json'}
        if token:headers['Cookie']=('__Host-plup_identity=' if owner else members.COOKIE+'=')+token
        if origin:headers['Origin']=self.origin
        if csrf and token:headers['X-CSRF-Token']=hmac.new(app.SESSION_SECRET.encode(),('csrf:'+token).encode(),hashlib.sha256).hexdigest()
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        conn.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=conn.getresponse();raw=response.read();status=response.status;response_headers=dict(response.getheaders());cookies=response.headers.get_all('Set-Cookie') or [];response_headers['Set-Cookie']=next((c for c in cookies if c.startswith(members.COOKIE+'=')),response_headers.get('Set-Cookie',''));conn.close()
        try:result=json.loads(raw)
        except (ValueError,UnicodeDecodeError):result=raw
        return status,result,response_headers

    def create(self,username='colleague',role='editor',modes=None):
        status,result,_=self.request('POST','/api/admin/members/create',{
            'username':username,'name':'Colleague','password':'separate-test-password',
            'role':role,'modules':modes or list(members.MODES),
        })
        self.assertEqual(status,200,result)
        self.assertEqual(set(result),{'id','username'})
        return result

    def login(self,username='colleague',password='separate-test-password',token=None):
        status,result,headers=self.request('POST','/auth/member-login',{
            'username':username,'password':password,
        },token=token)
        self.assertEqual(status,200,result)
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('Secure',headers['Set-Cookie'])
        return headers['Set-Cookie'].split(';')[0].split('=',1)[1]

    def test_owner_created_account_password_hash_and_no_public_signup(self):
        account=self.create()
        session=self.login('COLLEAGUE')
        body={'username':'another','password':'some-test-password','role':'viewer','modules':['plan']}
        self.assertEqual(self.request('POST','/api/admin/members/create',body,token=None)[0],401)
        self.assertEqual(self.request('POST','/api/admin/members/create',body,token=session)[0],403)
        self.assertEqual(self.request('POST','/api/admin/members/create',body,csrf=False)[0],403)
        self.assertEqual(self.request('POST','/api/admin/members/create',body | {'username':'COLLEAGUE'})[0],400)
        self.assertEqual(self.request('POST','/auth/activate',{},token=None)[0],404)
        profile=self.request('GET','/api/session',token=session)[1]['user']
        self.assertEqual(profile['id'],account['id'])
        self.assertEqual(profile['username'],'colleague')
        conn=app.database()
        try:
            row=conn.execute('SELECT * FROM members').fetchone()
            self.assertNotIn('separate-test-password',row['password_hash'])
            self.assertNotEqual(row['password_hash'],members.password_hash('separate-test-password'))
            self.assertEqual(conn.execute('SELECT token_hash FROM member_sessions').fetchone()[0],members.digest(session))
            logs=' '.join(str(tuple(r)) for r in conn.execute('SELECT * FROM access_events'))
            self.assertNotIn(session,logs)
            self.assertNotIn('separate-test-password',logs)
        finally:conn.close()

    def test_owner_password_change_and_revocation_invalidate_access(self):
        account=self.create()
        session=self.login()
        change={'id':account['id'],'action':'password','password':'another-test-password'}
        self.assertEqual(self.request('POST','/api/admin/members/update',change,token=session)[0],403)
        self.assertEqual(self.request('POST','/api/admin/members/update',change)[0],200)
        self.assertEqual(self.request('GET','/api/reports',token=session)[0],401)
        self.assertEqual(self.request('POST','/auth/member-login',{'username':'colleague','password':'separate-test-password'},token=None)[0],400)
        second=self.login(password=change['password'])
        self.assertEqual(self.request('GET','/api/session',token=second)[1]['user']['id'],account['id'])
        self.assertEqual(self.request('POST','/api/admin/members/update',{'id':account['id'],'action':'revoke'})[0],200)
        self.assertEqual(self.request('GET','/api/reports',token=second)[0],401)

    def test_login_origin_password_policy_throttling_and_csrf(self):
        self.create();session=self.login()
        self.assertEqual(self.request('POST','/auth/member-login',{'username':'colleague','password':'separate-test-password'},token=None,origin=False)[0],403)
        self.assertEqual(self.request('POST','/api/reports',FORECAST,token=session,csrf=False)[0],403)
        for _ in range(10):self.assertEqual(self.request('POST','/auth/member-login',{'username':'nobody','password':'invalid-test-password'},token=None)[0],400)
        self.assertEqual(self.request('POST','/auth/member-login',{'username':'nobody','password':'invalid-test-password'},token=None)[0],429)
        members.FAILURES.clear()
        self.assertEqual(self.request('POST','/auth/member-login',{'username':'COLLEAGUE','password':'separate-test-password'},token=None)[0],200)
        conn=app.database()
        try:
            for value in ['short',None,'x'*129]:
                with self.assertRaises(ValueError):members.password_hash(value)
        finally:conn.close()

    def test_scoped_reader_cannot_write_or_access_other_module_by_id(self):
        plan=app.save_report(PLAN);forecast=app.save_report(FORECAST)
        account=self.create(role='viewer',modes=['forecast']);session=self.login()
        self.assertEqual(self.request('GET','/api/reports',token=session)[1][0]['id'],forecast['id'])
        self.assertEqual(len(self.request('GET','/api/reports',token=session)[1]),1)
        for path in ['/api/reports/'+plan['id'],'/api/smart/versions?id='+plan['id'],'/api/reports/latest?mode=plan','/api/admin/export?format=sqlite','/api/admin/members']:
            self.assertEqual(self.request('GET',path,token=session)[0],403,path)
        for path,body in [('/api/reports',FORECAST),('/api/smart/table',{'text':'a\tb'}),('/api/forecast/import',{'image':'x'}),('/api/smart/draft',{'payload':FORECAST,'metadata':{}}),('/api/smart/restore',{'id':forecast['id'],'version':1,'expected':1}),('/api/admin/members/update',{'id':account['id'],'action':'password','password':'another-test-password'})]:
            self.assertEqual(self.request('POST',path,body,token=session)[0],403,path)
        self.assertEqual(self.request('PUT','/api/reports/'+forecast['id'],FORECAST,token=session)[0],403)
        self.assertEqual(self.request('POST','/api/compute',PLAN,token=session)[0],403)
        self.assertEqual(self.request('POST','/api/render',PLAN,token=session)[0],403)
        self.assertEqual(self.request('POST','/api/compute',FORECAST,token=session)[0],200)
        dashboard=self.request('GET','/api/smart/dashboard?date=2026-11-12',token=session)[1]
        self.assertEqual({r['mode'] for r in dashboard['recent']},{'forecast'})
        self.assertNotIn('PRIVATE PLAN',json.dumps(dashboard))
        self.assertEqual(self.request('GET','/api/smart/drafts',token=session)[1],[])
        conn=app.database()
        try:before=list(conn.execute('SELECT * FROM report_defaults'))
        finally:conn.close()
        status,png,_=self.request('POST','/api/render',FORECAST,token=session)
        self.assertEqual(status,200);self.assertTrue(png.startswith(b'\x89PNG'))
        conn=app.database()
        try:self.assertEqual([tuple(r) for r in conn.execute('SELECT * FROM report_defaults')],[tuple(r) for r in before])
        finally:conn.close()

    def test_editor_scope_drafts_and_report_audit(self):
        plan=app.save_report(PLAN)
        first=self.create('first',modes=['forecast']);s1=self.login('first')
        self.create('second',modes=['forecast']);s2=self.login('second')
        owner_body={'payload':FORECAST,'metadata':{}}
        self.assertEqual(self.request('POST','/api/smart/draft',owner_body)[0],200)
        self.assertEqual(self.request('POST','/api/smart/draft',owner_body,token=s1)[0],200)
        self.assertEqual(self.request('GET','/api/smart/drafts',token=s2)[1],[])
        self.assertEqual(len(self.request('GET','/api/smart/drafts',token=s1)[1]),1)
        self.assertEqual(self.request('POST','/api/smart/draft',{'payload':PLAN,'metadata':{}},token=s1)[0],403)
        self.assertEqual(self.request('PUT','/api/reports/'+plan['id'],FORECAST,token=s1)[0],403)
        status,saved,_=self.request('POST','/api/reports',FORECAST,token=s1)
        self.assertEqual(status,201,saved)
        self.assertEqual(self.request('GET','/api/smart/drafts',token=s1)[1],[])
        self.assertEqual(len(self.request('GET','/api/smart/drafts')[1]),1)
        conn=app.database()
        try:
            event=conn.execute("SELECT * FROM access_events WHERE action='report-create' AND target=?",(saved['id'],)).fetchone()
            self.assertEqual(event['actor'],first['id'])
        finally:conn.close()
        self.assertEqual(self.request('POST','/api/admin/members/update',{'id':first['id'],'action':'permissions','role':'viewer','modules':['plan']})[0],200)
        self.assertEqual(self.request('GET','/api/reports/'+saved['id'],token=s1)[0],403)
        self.assertEqual(self.request('GET','/api/reports/'+plan['id'],token=s1)[0],200)
        self.assertEqual(self.request('POST','/api/reports',PLAN,token=s1)[0],403)

    def test_role_cannot_escalate_and_no_owner_record_can_be_modified(self):
        self.assertEqual(self.request('POST','/api/admin/members/create',{'username':'abc','password':'some-test-password','role':'owner','modules':['plan']})[0],400)
        self.assertEqual(self.request('POST','/api/admin/members/update',{'id':'owner','action':'revoke'})[0],400)
        account=self.create(role='viewer',modes=['plan']);session=self.login()
        self.assertEqual(self.request('POST','/api/admin/members/update',{'id':account['id'],'action':'permissions','role':'editor','modules':list(members.MODES)},token=session)[0],403)
        self.assertEqual(self.request('GET','/api/session')[1]['user']['role'],'owner')
        status,html,_=self.request('GET','/',token=session)
        self.assertIn(b'plup-access',html)
        self.assertNotIn(b'password_hash',html)
        self.assertEqual(self.request('POST','/auth/logout',token=session)[0],200)
        self.assertEqual(self.request('GET','/api/reports',token=session)[0],401)

    def test_versions_cannot_leak_a_formerly_different_module(self):
        report=app.save_report(PLAN)
        app.update_report(report['id'],FORECAST)
        self.create(role='viewer',modes=['forecast']);session=self.login()
        status,versions,_=self.request('GET','/api/smart/versions?id='+report['id'],token=session)
        self.assertEqual(status,200)
        self.assertEqual({version['payload']['mode'] for version in versions},{'forecast'})
        self.assertNotIn('PRIVATE PLAN',json.dumps(versions))

    def test_permission_rechecked_inside_write_and_sessions_survive_memory_reset(self):
        member=self.create(modes=['forecast']);session=self.login()
        identity.SESSIONS.clear()
        self.assertEqual(members.principal(app.DB_PATH,session)['id'],member['id'])
        conn=app.database()
        try:
            with conn:conn.execute('UPDATE members SET active=0 WHERE id=?',(member['id'],))
            self.assertIsNone(members.principal(app.DB_PATH,session))
            with self.assertRaises(ValueError):members.draft_save(conn,{'payload':FORECAST,'metadata':{}},member['id'])
            count=conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
        finally:conn.close()

        with self.assertRaises(app.InvalidReport):app.save_report(FORECAST,member['id'])
        app.remember_generated(FORECAST,member['id'])
        conn=app.database()
        try:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0],count)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM report_defaults').fetchone()[0],0)
        finally:conn.close()

    def test_colleague_login_switches_an_existing_owner_browser(self):
        self.create(role='viewer',modes=['forecast'])
        session=self.login(token='owner-session')
        self.assertIsNone(identity.session({'Cookie':'__Host-plup_identity=owner-session'}))
        profile=self.request('GET','/api/session',token=session)[1]['user']
        self.assertEqual(profile['role'],'viewer')
        self.assertEqual(profile['modules'],['forecast'])



if __name__=='__main__':unittest.main()
