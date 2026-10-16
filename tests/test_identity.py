import hashlib
import hmac
import http.client
import os
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from http.server import ThreadingHTTPServer
from server import app, identity


class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'PLUP_AUTH_MODE':'github',
            'PLUP_PUBLIC_ORIGIN':'https://example.test','PLUP_GITHUB_CLIENT_ID':'test',
            'PLUP_GITHUB_CLIENT_SECRET':'test-secret','PLUP_GITHUB_ALLOWED_ID':'123'})
        self.env.start()
        identity.PENDING.clear();identity.SESSIONS.clear()

    def tearDown(self):
        self.env.stop()

    def flow(self):
        url, binding = identity.start()
        q = parse_qs(urlsplit(url).query)
        self.assertEqual(q['code_challenge_method'], ['S256'])
        self.assertNotIn('test-secret', url)
        return {'state':q['state'],'code':['synthetic']}, {'Cookie':'__Host-plup_oauth='+binding}

    def test_binding_identity_and_single_use(self):
        query, headers = self.flow()
        with self.assertRaises(ValueError):identity.finish(query, {})
        with patch.object(identity,'request_json',side_effect=[{'access_token':'synthetic','scope':''},{'id':123}]) as api:
            token = identity.finish(query, headers)
            self.assertIn('code_verifier', api.call_args_list[0].args[1])
        self.assertEqual(identity.session({'Cookie':'__Host-plup_identity='+token}),token)
        with self.assertRaises(ValueError):identity.finish(query,headers)
        identity.logout({'Cookie':'__Host-plup_identity='+token})
        self.assertIsNone(identity.session({'Cookie':'__Host-plup_identity='+token}))

    def test_other_accounts_scopes_and_missing_config_denied(self):
        for result in ({'id':124},{'id':'123'}):
            q,h=self.flow()
            with patch.object(identity,'request_json',side_effect=[{'access_token':'synthetic'},result]):
                with self.assertRaises(ValueError):identity.finish(q,h)
        q,h=self.flow()
        with patch.object(identity,'request_json',return_value={'access_token':'synthetic','scope':'repo'}):
            with self.assertRaises(ValueError):identity.finish(q,h)
        with patch.dict(os.environ, {'PLUP_GITHUB_CLIENT_SECRET':''}):
            self.assertIsNone(identity.session({}))
            with self.assertRaises(ValueError):identity.start()

    def test_expiry_and_allowlist_change(self):
        identity.SESSIONS['synthetic']={'owner':'123','expires':time.time()-1}
        self.assertIsNone(identity.session({'Cookie':'__Host-plup_identity=synthetic'}))
        identity.SESSIONS['synthetic']={'owner':'124','expires':time.time()+60}
        self.assertIsNone(identity.session({'Cookie':'__Host-plup_identity=synthetic'}))

    def test_http_gate_no_password_or_static_bypass(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,headers=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port)
            c.request(method,path,headers=headers or {})
            r=c.getresponse();body=r.read();status=r.status;c.close();return status,body
        try:
            for path in ('/api/reports','/api/smart/dashboard','/api/smart/drafts'):
                self.assertEqual(request('GET',path)[0],401)
            for path in ('/','/index.html','/app.js'):
                status,body=request('GET',path)
                self.assertEqual(status,200);self.assertIn(b'Continu',body)
                self.assertNotIn(b'login-password',body)
            self.assertEqual(request('POST','/api/login')[0],403)
            self.assertEqual(request('POST','/api/render')[0],401)
            self.assertEqual(request('PUT','/api/reports/id')[0],401)
            identity.SESSIONS['synthetic']={'owner':'123','expires':time.time()+60}
            headers={'Cookie':'__Host-plup_identity=synthetic','Origin':'http://127.0.0.1:'+str(server.server_port)}
            self.assertEqual(request('POST','/auth/logout',headers)[0],403)
            csrf=hmac.new(app.SESSION_SECRET.encode(),b'csrf:synthetic',hashlib.sha256).hexdigest()
            headers['X-CSRF-Token']=csrf
            self.assertEqual(request('POST','/auth/logout',headers)[0],200)
            self.assertIsNone(identity.session(headers))
            with patch.dict(os.environ, {'PLUP_GITHUB_CLIENT_SECRET':''}):
                self.assertEqual(request('GET','/')[0],503)
                self.assertEqual(request('GET','/api/reports')[0],401)
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
