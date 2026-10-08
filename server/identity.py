"""Browser-only GitHub identity gate. No report data or tokens go to GitHub."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

LOCK = threading.Lock()
PENDING = {}
SESSIONS = {}
TTL = 28800


def enabled():
    return os.environ.get('PLUP_AUTH_MODE', '') == 'github'


def config():
    origin = os.environ.get('PLUP_PUBLIC_ORIGIN', '').rstrip('/')
    parsed = urlsplit(origin)
    client = os.environ.get('PLUP_GITHUB_CLIENT_ID', '')
    secret = os.environ.get('PLUP_GITHUB_CLIENT_SECRET', '')
    owner = os.environ.get('PLUP_GITHUB_ALLOWED_ID', '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or parsed.path or parsed.query or parsed.fragment or
            not client or not secret or not owner.isdecimal()):
        raise ValueError('Autentificarea GitHub nu este încă configurată.')
    return origin, client, secret, owner


def cookie(headers, name):
    jar = SimpleCookie()
    try:
        jar.load(headers.get('Cookie', ''))
        return jar[name].value if name in jar else ''
    except Exception:
        return ''


def prune():
    now = time.time()
    for collection in (PENDING, SESSIONS):
        for key in list(collection):
            if collection[key]['expires'] <= now:
                del collection[key]


def session(headers):
    try:
        _, _, _, owner = config()
    except ValueError:
        return None
    token = cookie(headers, '__Host-plup_identity')
    with LOCK:
        prune()
        item = SESSIONS.get(token)
        return token if item and item['owner'] == owner else None


def start():
    origin, client, _, _ = config()
    state = secrets.token_urlsafe(32)
    binding = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with LOCK:
        prune()
        if len(PENDING) >= 500:
            raise ValueError('Prea multe conectări în curs. Reîncearcă mai târziu.')
        PENDING[state] = {'binding': binding, 'verifier': verifier, 'expires': time.time()+600}
    query = urlencode({'client_id': client, 'redirect_uri': origin+'/auth/callback',
                       'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
                       'scope': '', 'allow_signup': 'false'})
    return 'https://github.com/login/oauth/authorize?'+query, binding


def request_json(url, data=None, token=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'PLUP-identity'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    if data:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    req = Request(url, data=urlencode(data).encode() if data else None, headers=headers)
    with urlopen(req, timeout=12) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('Răspuns de autentificare invalid.')
    return json.loads(raw)


def finish(query, headers):
    origin, client, secret, owner = config()
    state = query.get('state', [])
    codes = query.get('code', [])
    if len(state) != 1 or len(codes) != 1 or not 1 <= len(codes[0]) <= 512:
        raise ValueError('Conectare anulată sau invalidă. Reîncearcă.')
    binding = cookie(headers, '__Host-plup_oauth')
    with LOCK:
        prune()
        item = PENDING.get(state[0])
        if not item or not secrets.compare_digest(binding, item['binding']):
            raise ValueError('Conectare expirată sau invalidă. Reîncearcă.')
        del PENDING[state[0]]  # Single use, including failed exchanges.
    try:
        result = request_json('https://github.com/login/oauth/access_token',
                              {'client_id': client, 'client_secret': secret, 'code': codes[0],
                               'redirect_uri': origin+'/auth/callback', 'code_verifier': item['verifier']})
        token = result.get('access_token')
        if not isinstance(token, str) or not token or result.get('error') or result.get('scope', ''):
            raise ValueError('Răspuns de autentificare invalid.')
        user = request_json('https://api.github.com/user', token=token)
        if type(user.get('id')) is not int or str(user['id']) != owner:
            raise ValueError('Acest cont nu are acces la aplicația PLUP.')
    except ValueError:
        raise
    except Exception:
        raise ValueError('Serviciul de autentificare nu răspunde. Reîncearcă.') from None
    # Token only exists in this request; do not store it or expose it to the browser.
    token = secrets.token_urlsafe(48)
    with LOCK:
        prune()
        if len(SESSIONS) >= 1000:
            raise ValueError('Prea multe sesiuni. Reîncearcă mai târziu.')
        SESSIONS[token] = {'owner': owner, 'expires': time.time()+TTL}
    return token


def logout(headers):
    with LOCK:
        SESSIONS.pop(cookie(headers, '__Host-plup_identity'), None)


STYLE = b'''body{margin:0;min-height:100svh;display:grid;place-items:center;background:#091724;color:#edf5ff;font:17px/1.6 system-ui,sans-serif;padding:24px;box-sizing:border-box}main{width:min(100%,440px);padding:32px;border:1px solid #385568;border-radius:24px;background:#132838;box-sizing:border-box}h1{font-size:28px;line-height:1.2}p{color:#bacddd}a{display:block;min-height:44px;padding:12px 20px;border-radius:12px;background:#4587e6;color:white;text-align:center;text-decoration:none;font-weight:650}a:focus-visible{outline:3px solid #99d5ff;outline-offset:5px}.brand{letter-spacing:2px;font-size:13px;color:#99d5ff}@media(prefers-color-scheme:light){body{background:#eef4f8;color:#172c3d}main{background:white;border-color:#becfdb}p{color:#496173}.brand{color:#175778}}'''


def page(message='Acces permis exclusiv contului autorizat. Nu este necesară instalarea Tailscale.'):
    from html import escape
    return ('''<!doctype html><html lang="ro"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Acces privat · PLUP</title><link rel="stylesheet" href="/auth/style.css"><main><div class="brand">NRG CABLES · PLUP</div><h1>Conectare securizată</h1><p>'''+escape(message)+'''</p><a href="/auth/login">Continuă cu GitHub</a></main></html>''').encode()
