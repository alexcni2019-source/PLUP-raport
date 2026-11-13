"""Owner-only Web Push delivery for the PLUP activity journal."""
import base64
from contextlib import closing
import json
import re
import sqlite3
from threading import Thread
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
import requests


ACTIONS = {
    'login': 's-a autentificat',
    'logout': 's-a deconectat',
    'report-generate': 'a generat un PNG',
    'report-create': 'a salvat un raport',
    'report-edit': 'a modificat un raport',
    'report-restore': 'a restaurat o versiune',
    'report-download': 'a apăsat pe descărcarea unui PNG',
    'table-apply': 'a aplicat un tabel importat',
    'report-open': 'a deschis un raport din istoric',
    'report-check': 'a verificat un raport',
    'image-import': 'a citit o imagine pentru import',
    'table-import': 'a citit un tabel pentru import',
    'inventory-import': 'a importat inventarul',
}
MODULES = {'weekday': 'Raport zilnic', 'weekend': 'Raport 3 zile',
           'plan': 'Plan de producție', 'forecast': 'Previz'}
PROVIDERS = ('fcm.googleapis.com', 'push.services.mozilla.com', 'push.apple.com', 'notify.windows.com')
TTL = 3600
LIMIT = 12


def bootstrap(conn):
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS push_identity (
        id INTEGER PRIMARY KEY CHECK(id=1), private_key TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS push_devices (
        endpoint TEXT PRIMARY KEY, subscription TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS push_pending (
        id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT NOT NULL, payload TEXT NOT NULL,
        expires INTEGER NOT NULL, next_try INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS push_pending_due ON push_pending(next_try);
      CREATE INDEX IF NOT EXISTS push_pending_endpoint ON push_pending(endpoint);
      CREATE INDEX IF NOT EXISTS access_events_render_batch ON access_events(actor, target)
        WHERE action='report-generate';
    ''')


def encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def decode(value, size):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,90}', value):
        raise ValueError('Abonament invalid.')
    raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    if len(raw) != size:
        raise ValueError('Abonament invalid.')
    return raw


def public_key(conn):
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT private_key FROM push_identity WHERE id=1').fetchone()
        if row:
            key = ec.derive_private_key(int.from_bytes(decode(row[0], 32)), ec.SECP256R1())
        else:
            key = ec.generate_private_key(ec.SECP256R1())
            secret = key.private_numbers().private_value.to_bytes(32)
            conn.execute('INSERT INTO push_identity VALUES (1,?)', (encode(secret),))
    numbers = key.public_key().public_numbers()
    return encode(b'\x04' + numbers.x.to_bytes(32) + numbers.y.to_bytes(32))


def endpoint_url(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048 or not value.isascii() or re.search(r'[\s\x00-\x1f\\]', value):
        raise ValueError('Abonament invalid.')
    url = urlsplit(value)
    host = url.hostname
    if (url.scheme != 'https' or not host or url.netloc != host or not url.path.startswith('/')
            or url.fragment or not any(host == provider or host.endswith('.'+provider) for provider in PROVIDERS)):
        raise ValueError('Serviciul de notificări al acestui browser nu este acceptat.')
    return value


def device(conn, action, body):
    if not isinstance(body, dict):
        raise ValueError('Abonament invalid.')
    endpoint = endpoint_url(body.get('endpoint'))
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        registered = conn.execute('SELECT 1 FROM push_devices WHERE endpoint=?', (endpoint,)).fetchone()
        if action == 'enable':
            keys = body.get('keys')
            if not isinstance(keys, dict):
                raise ValueError('Abonament invalid.')
            try:
                ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decode(keys.get('p256dh'), 65))
                decode(keys.get('auth'), 16)
            except ValueError as exc:
                raise ValueError('Cheile abonamentului sunt invalide.') from exc
            if not registered and conn.execute('SELECT COUNT(*) FROM push_devices').fetchone()[0] >= LIMIT:
                raise ValueError('Ai atins limita de dispozitive. Dezactivează notificările pe un dispozitiv.')
            subscription = {'endpoint': endpoint, 'keys': {key: keys[key] for key in ('p256dh', 'auth')}}
            conn.execute('INSERT INTO push_devices VALUES (?,?) ON CONFLICT(endpoint) DO UPDATE SET subscription=excluded.subscription',
                         (endpoint, json.dumps(subscription)))
            return {'active': True}
        if action == 'disable':
            remove_device(conn, endpoint)
            return {'active': False}
        if action == 'status':
            return {'active': bool(registered)}
        if not registered:
            raise ValueError('Activează notificările pe acest dispozitiv.')
        identifier = enqueue(conn, {'title': 'PLUP · Notificare de test', 'body': 'Notificările funcționează pe acest dispozitiv.'}, endpoint)
        return {'queued': identifier is not None}


def remove_device(conn, endpoint):
    conn.execute('DELETE FROM push_pending WHERE endpoint=?', (endpoint,))
    conn.execute('DELETE FROM push_devices WHERE endpoint=?', (endpoint,))


def enqueue(conn, payload, endpoint=None):
    now = int(time.time())
    conn.execute('DELETE FROM push_pending WHERE expires<=?', (now,))
    result = conn.execute('''INSERT INTO push_pending(endpoint,payload,expires,next_try)
        SELECT endpoint,?,?,? FROM push_devices WHERE (? IS NULL OR endpoint=?)
        AND (SELECT COUNT(*) FROM push_pending p WHERE p.endpoint=push_devices.endpoint)<200''',
                          (json.dumps(payload, ensure_ascii=False), now + TTL, now, endpoint, endpoint))
    return result.lastrowid if result.rowcount else None


def for_event(conn, actor, action, detail):
    if actor == 'owner' or action not in ACTIONS:
        return
    member = conn.execute('SELECT name,email FROM members WHERE id=?', (actor,)).fetchone()
    if not member:
        return
    name = (member['name'] or member['email'])[:70]
    context = MODULES.get(detail.get('mode')) or detail.get('device', '')
    if context and re.fullmatch(r'\d{4}-\d{2}-\d{2}', detail.get('date') or ''):
        context += ' · ' + '.'.join(reversed(detail['date'].split('-')))
    body = f'{name} {ACTIONS[action]}' + (f' · {context}' if context else '') + '.'
    enqueue(conn, {'title': 'PLUP · Activitatea echipei', 'body': body})


class PushSession(requests.Session):
    def request(self, method, url, **kwargs):
        return super().request(method, endpoint_url(url), **(kwargs | {'allow_redirects': False}))


def deliver_one(conn, origin):
    now = int(time.time())
    with conn:
        conn.execute('DELETE FROM push_pending WHERE expires<=?', (now,))
    item = conn.execute('''SELECT p.*, d.subscription, k.private_key FROM push_pending p
        JOIN push_devices d USING(endpoint) CROSS JOIN push_identity k
        WHERE p.next_try<=? ORDER BY p.id LIMIT 1''', (now,)).fetchone()
    if not item:
        return False
    try:
        with PushSession() as session:
            response = webpush(json.loads(item['subscription']), item['payload'],
                               vapid_private_key=item['private_key'], vapid_claims={'sub': origin},
                               ttl=item['expires']-now, timeout=6, requests_session=session)
        status = response.status_code
    except WebPushException as error:
        status = error.response.status_code if error.response is not None else 503
    except requests.RequestException:
        status = 503
    with conn:
        if status in (404, 410):
            if conn.execute('SELECT 1 FROM push_pending WHERE id=?', (item['id'],)).fetchone():
                remove_device(conn, item['endpoint'])
        elif status in (408, 429) or status >= 500:
            delay = min(300, 10 * 2 ** min(item['attempts'], 5))
            conn.execute('UPDATE push_pending SET attempts=attempts+1,next_try=? WHERE id=?',
                         (now+delay, item['id']))
        else:
            conn.execute('DELETE FROM push_pending WHERE id=?', (item['id'],))
            if not 200 <= status < 300:
                print(f'PLUP push delivery rejected ({status})', flush=True)
    return True


def start(database_path, origin):
    def run():
        while True:
            try:
                with closing(sqlite3.connect(database_path, timeout=10)) as conn:
                    conn.row_factory = sqlite3.Row
                    while deliver_one(conn, origin):
                        pass
            except (sqlite3.Error, ValueError):
                print('PLUP push worker could not process its queue', flush=True)
            time.sleep(3)

    Thread(target=run, name='plup-push', daemon=True).start()
