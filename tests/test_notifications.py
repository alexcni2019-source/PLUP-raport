from contextlib import closing
import json
from requests import Response
import unittest
import uuid
from unittest.mock import patch

from server import app, notifications
import test_members


class NotificationsTest(unittest.TestCase):
    def setUp(self):
        self.api = test_members.MembersTest()
        self.api.setUp()
        self.addCleanup(self.api.tearDown)

    def connect_device(self, token):
        with closing(app.database()) as conn:
            key = notifications.public_key(conn)
        endpoint = 'https://fcm.googleapis.com/fcm/send/' + token
        body = {'action': 'enable', 'endpoint': endpoint,
                'keys': {'p256dh': key, 'auth': notifications.encode(b'x' * 16)}}
        self.assertEqual(self.api.request('POST', '/api/admin/push', body)[0], 200)
        return endpoint

    def queued(self):
        with closing(app.database()) as conn:
            return [(row[0], json.loads(row[1])) for row in conn.execute(
                'SELECT endpoint,payload FROM push_pending ORDER BY id')]

    def test_owner_activates_each_device_and_colleague_events_fan_out(self):
        desktop = self.connect_device('desktop-test')
        phone = self.connect_device('phone-test')
        self.api.create(modes=['forecast'])
        member_session = self.api.login()
        for method, body in [('GET', None), ('POST', {'action': 'disable', 'endpoint': phone})]:
            self.assertEqual(self.api.request(method, '/api/admin/push', body, token=member_session)[0], 403)
        self.assertEqual(self.api.request('POST', '/api/admin/push', {'action': 'disable', 'endpoint': phone}, csrf=False)[0], 403)

        batch = {'X-PLUP-Export': str(uuid.uuid4())}
        for section in ('table', 'summary'):
            self.assertEqual(self.api.request('POST', '/api/render?section='+section, test_members.FORECAST,
                                              token=member_session, extra_headers=batch)[0], 200)
        self.assertEqual(self.api.request('POST', '/api/reports', test_members.FORECAST, token=member_session)[0], 201)
        self.assertEqual(self.api.request('POST', '/api/activity', {'mode': 'plan', 'action': 'report-download'}, token=member_session)[0], 403)
        self.assertEqual(self.api.request('POST', '/api/activity', {'mode': 'forecast', 'action': 'report-download'}, token=member_session)[0], 200)

        for endpoint in (desktop, phone):
            bodies = [value['body'] for target, value in self.queued() if target == endpoint]
            self.assertEqual(len(bodies), 4)
            for term in ('autentificat', 'generat', 'salvat', 'descărcarea'):
                self.assertTrue(any(term in body for body in bodies))
            self.assertNotIn('ALLOWED FORECAST', json.dumps(bodies))
        self.api.request('POST', '/api/admin/push', {'action': 'disable', 'endpoint': phone})
        self.assertEqual({endpoint for endpoint, _ in self.queued()}, {desktop})

    def test_provider_validation_and_encrypted_delivery(self):
        for url in ('https://localhost/push', 'https://web.push.apple.com.evil.test/push',
                    'https://fcm.googleapis.com:443/push', 'https://user@fcm.googleapis.com/push'):
            with self.assertRaises(ValueError):
                notifications.endpoint_url(url)
        endpoint = self.connect_device('delivery-test')
        result = self.api.request('POST', '/api/admin/push', {'action': 'test', 'endpoint': endpoint})
        self.assertTrue(result[1]['queued'])

        def provider(session, method, url, **kwargs):
            self.assertEqual(url, endpoint)
            self.assertFalse(kwargs['allow_redirects'])
            self.assertEqual(kwargs['headers']['content-encoding'], 'aes128gcm')
            self.assertTrue(kwargs['headers']['Authorization'].startswith('vapid '))
            self.assertNotIn(b'Notificare', kwargs['data'])
            response = Response()
            response.status_code = 201
            return response

        with closing(app.database()) as conn, patch('requests.Session.request', new=provider):
            self.assertTrue(notifications.deliver_one(conn, 'https://plup.example.test'))
        self.assertEqual(self.queued(), [])
