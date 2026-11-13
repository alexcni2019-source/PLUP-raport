"""Owner-managed colleague accounts and revocable sessions.

The GitHub owner remains configured outside this table. Tokens are stored only
as hashes; no password or session token enters the audit log.
"""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
import uuid
from server import notifications, smart

MODES = ('weekday', 'weekend', 'plan', 'forecast')
COOKIE = '__Host-plup_member'
TTL = 28800
USERNAME = re.compile(r'[a-z0-9][a-z0-9._-]{2,63}', re.ASCII)
OWNER = {'id': 'owner', 'role': 'owner', 'username': '', 'modules': list(MODES)}
LOCK = threading.Lock()
HASH_SLOTS = threading.BoundedSemaphore(4)
FAILURES = {}


def bootstrap(conn):
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS members (
        id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('editor','viewer')), modules TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1, password_hash TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS member_sessions (
        token_hash TEXT PRIMARY KEY, member_id TEXT NOT NULL, expires INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS member_sessions_user ON member_sessions(member_id);
      CREATE TABLE IF NOT EXISTS member_drafts (
        member_id TEXT NOT NULL, mode TEXT NOT NULL, updated_at TEXT NOT NULL,
        payload TEXT NOT NULL, metadata TEXT NOT NULL, PRIMARY KEY(member_id,mode));
      CREATE TABLE IF NOT EXISTS access_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL);
    ''')


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def public(row):
    # Keep the original unique column to preserve legacy email logins.
    return {k: row[k] for k in ('id', 'name', 'role')} | {
        'username': row['email'], 'modules': json.loads(row['modules']),
    }


def principal(path, token):
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{64}', token):
        return None
    if not path.exists():return None
    conn = connect(path)
    try:
        row = conn.execute('''SELECT m.* FROM member_sessions s JOIN members m
          ON m.id=s.member_id WHERE s.token_hash=? AND s.expires>? AND m.active=1
          AND m.password_hash IS NOT NULL''', (digest(token), int(time.time()))).fetchone()
        return public(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def event(conn, actor, action, target, detail=None):
    detail = detail or {}
    conn.execute('INSERT INTO access_events(created_at,actor,action,target,detail) VALUES (?,?,?,?,?)',
                 (smart.stamp(), actor, action, target, json.dumps(detail, ensure_ascii=False)))
    notifications.for_event(conn, actor, action, detail)


def can_write(conn, actor, mode):
    if actor == 'owner':
        return True
    row = conn.execute('SELECT role,modules FROM members WHERE id=? AND active=1 AND password_hash IS NOT NULL', (actor,)).fetchone()
    return bool(row and row['role']=='editor' and mode in json.loads(row['modules']))


def validate_profile(body):
    if not isinstance(body, dict):
        raise ValueError('Utilizator invalid.')
    role, modules = body.get('role'), body.get('modules')
    if role not in ('editor', 'viewer'):
        raise ValueError('Alege Editor sau Cititor.')
    if (not isinstance(modules, list) or not modules or len(modules) > 4 or
            any(not isinstance(m, str) or m not in MODES for m in modules) or len(set(modules)) != len(modules)):
        raise ValueError('Alege modulele permise.')
    return role, [m for m in MODES if m in modules]


def create(conn, body):
    role, modules = validate_profile(body)
    username = body.get('username')
    username = username.strip().lower() if isinstance(username, str) else ''
    if not USERNAME.fullmatch(username):
        raise ValueError('Alege un utilizator de 3–64 de caractere, cu litere, cifre, punct, cratimă sau underscore.')
    name = body.get('name', '')
    if not isinstance(name, str) or len(name) > 100 or any(ord(c) < 32 for c in name):
        raise ValueError('Numele este prea lung sau invalid.')
    encoded = password_hash(body.get('password'))
    identifier, now = str(uuid.uuid4()), smart.stamp()
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM members WHERE email=?', (username,)).fetchone():
            raise ValueError('Acest nume de utilizator există deja.')
        if conn.execute('SELECT COUNT(*) FROM members').fetchone()[0] >= 100:
            raise ValueError('Limita de 100 de utilizatori a fost atinsă.')
        conn.execute(
            'INSERT INTO members (id,email,name,role,modules,active,password_hash,created_at,updated_at) VALUES (?,?,?,?,?,1,?,?,?)',
            (identifier, username, name.strip(), role, json.dumps(modules), encoded, now, now),
        )
        event(conn, 'owner', 'member-create', identifier, {'role': role, 'modules': modules})
    return {'id': identifier, 'username': username}


def update(conn, body):
    if not isinstance(body, dict) or not isinstance(body.get('id'), str):
        raise ValueError('Utilizator invalid.')
    identifier, action = body['id'], body.get('action')
    encoded = password_hash(body.get('password')) if action == 'password' else None
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM members WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise ValueError('Utilizatorul nu există.')
        if action == 'permissions':
            role, modules = validate_profile(body)
            conn.execute('UPDATE members SET role=?,modules=?,updated_at=? WHERE id=?',
                         (role, json.dumps(modules), smart.stamp(), identifier))
            event(conn, 'owner', 'permissions', identifier, {'role': role, 'modules': modules})
        elif action in ('revoke', 'password'):
            if action == 'password':
                conn.execute('UPDATE members SET active=1,password_hash=?,updated_at=? WHERE id=?',
                             (encoded, smart.stamp(), identifier))
            else:
                conn.execute('UPDATE members SET active=0,updated_at=? WHERE id=?',
                             (smart.stamp(), identifier))
            conn.execute('DELETE FROM member_sessions WHERE member_id=?', (identifier,))
            event(conn, 'owner', 'password-set' if action == 'password' else 'revoke', identifier)
        else:
            raise ValueError('Acțiune invalidă.')
    return {'ok': True}


def password_hash(password, salt=None):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('Parola trebuie să aibă între 12 și 128 de caractere.')
    salt = salt or secrets.token_hex(16)
    if not HASH_SLOTS.acquire(timeout=5):
        raise ValueError('Prea multe conectări simultane. Reîncearcă în câteva secunde.')
    try:
        result = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64*1024*1024)
    finally:
        HASH_SLOTS.release()
    return 'scrypt$32768$8$3$'+salt+'$'+result.hex()


def new_session(conn, identifier):
    token = secrets.token_urlsafe(48)
    conn.execute('DELETE FROM member_sessions WHERE expires<=?', (int(time.time()),))
    conn.execute('INSERT INTO member_sessions VALUES (?,?,?)', (digest(token), identifier, int(time.time())+TTL))
    return token


def throttle(key,limit=10):
    now = time.monotonic()
    with LOCK:
        for item in list(FAILURES):
            FAILURES[item] = [t for t in FAILURES[item] if now-t < 900]
            if not FAILURES[item]:
                del FAILURES[item]
        if len(FAILURES.get(key, [])) >= limit:
            raise ValueError('Prea multe încercări. Reîncearcă peste 15 minute.')
        if len(FAILURES) >= 10000 and key not in FAILURES:
            raise ValueError('Prea multe încercări. Reîncearcă mai târziu.')
        FAILURES.setdefault(key, []).append(now)


def login(conn, body, ip, device=None):
    throttle('ip:'+ip,100)
    if not isinstance(body, dict):
        raise ValueError('Utilizator sau parolă incorectă.')
    username = body.get('username', body.get('email', ''))
    username = username.strip().casefold() if isinstance(username, str) and len(username) <= 254 else ''
    throttle('username:'+digest(username))
    password = body.get('password')
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('Utilizator sau parolă incorectă.')
    row = conn.execute('SELECT * FROM members WHERE email=?', (username,)).fetchone()
    encoded = row['password_hash'] if row and row['password_hash'] else 'scrypt$32768$8$3$'+'0'*32+'$'+'0'*128
    candidate = password_hash(password, encoded.split('$')[4])
    if not hmac.compare_digest(candidate, encoded) or not row or not row['active']:
        raise ValueError('Utilizator sau parolă incorectă.')
    with conn:
        # Revocation and password reset may happen while scrypt runs.
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT active,password_hash FROM members WHERE id=?', (row['id'],)).fetchone()
        if not current or not current['active'] or current['password_hash'] != encoded:
            raise ValueError('Utilizator sau parolă incorectă.')
        token = new_session(conn, row['id'])
        event(conn, row['id'], 'login', row['id'], {'device': device} if device else None)
    return token


def listing(conn):
    return {'members': [public(r) | {'active': bool(r['active']), 'activated': bool(r['password_hash']),
            'created_at': r['created_at']} for r in conn.execute('SELECT * FROM members ORDER BY created_at')],
            'events': [dict(r) for r in conn.execute('SELECT * FROM access_events ORDER BY id DESC LIMIT 50')]}


def draft_save(conn, body, actor):
    payload, meta = smart.draft_validate(body)
    updated = smart.stamp()
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        if not can_write(conn, actor, payload['mode']):
            raise ValueError('Accesul de editare nu mai este disponibil.')
        row = conn.execute('SELECT updated_at FROM member_drafts WHERE member_id=? AND mode=?', (actor, payload['mode'])).fetchone()
        if 'expected' in body and body['expected'] != (row['updated_at'] if row else None):
            raise ValueError('Ciorna a fost modificată pe alt dispozitiv. Copia locală este păstrată.')
        conn.execute('INSERT INTO member_drafts VALUES (?,?,?,?,?) ON CONFLICT(member_id,mode) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload,metadata=excluded.metadata',
                     (actor, payload['mode'], updated, json.dumps(payload, ensure_ascii=False), json.dumps(meta)))
    return {'updated_at': updated}
