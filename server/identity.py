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


def configuration_issues():
    """Only variable names, never credential values, for operator diagnostics."""
    origin = os.environ.get('PLUP_PUBLIC_ORIGIN', '').rstrip('/')
    try:
        parsed = urlsplit(origin)
        valid_origin = (parsed.scheme == 'https' and bool(parsed.hostname) and
                        not any((parsed.username, parsed.password, parsed.path, parsed.query, parsed.fragment)))
    except ValueError:
        valid_origin = False
    issues = [] if valid_origin else ['PLUP_PUBLIC_ORIGIN']
    for name in ('PLUP_GITHUB_CLIENT_ID', 'PLUP_GITHUB_CLIENT_SECRET'):
        if not os.environ.get(name, '').strip():issues.append(name)
    if not os.environ.get('PLUP_GITHUB_ALLOWED_ID', '').isdecimal():
        issues.append('PLUP_GITHUB_ALLOWED_ID')
    return issues


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


STYLE = b'body{margin:0;min-height:100svh;display:grid;place-items:center;background:#fffdf1;color:#1e342e;font:17px/1.5 system-ui,sans-serif;padding:24px;box-sizing:border-box}main{width:min(100%,460px);padding:30px;border:1px solid #d9e2d3;border-radius:18px;background:#fffef9;box-sizing:border-box;box-shadow:0 10px 35px -22px #006b6540}h1{font-size:30px;line-height:1.2}p{color:#53645a}a,button{display:block;box-sizing:border-box;width:100%;min-height:46px;padding:12px 18px;border:1px solid #006b65;border-radius:10px;background:#006b65;color:#fff;text-align:center;text-decoration:none;font:650 16px system-ui,sans-serif;cursor:pointer;margin-top:14px}a.secondary{background:transparent;color:#006b65;border-color:#ccd9ca}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #006b65;outline-offset:4px}.brand{letter-spacing:2px;font-size:13px;color:#006b65}label{display:block;font-weight:600;margin:16px 0 7px}input{box-sizing:border-box;width:100%;min-height:48px;padding:10px 12px;border:1px solid #ccd9ca;border-radius:8px;background:#fffef9;color:inherit;font:18px system-ui,sans-serif}input[readonly]{background:#edf2e7}button:disabled{opacity:.65;cursor:wait}.help{font-size:15px}#status{min-height:24px}[hidden]{display:none!important}@media(prefers-color-scheme:dark){body{background:#141f1a;color:#fff9e9}main,input{background:#1e2c24;border-color:#425748}p{color:#c4d2be}.brand{color:#64dbc4}a,button{background:#64dbc4;color:#102d25;border-color:#64dbc4}a.secondary{color:#64dbc4;border-color:#53695a}input[readonly]{background:#293b2e}}'


def page(message='Acces privat pentru proprietar și colegii cu un cont PLUP.'):
    from html import escape
    return ('''<!doctype html><html lang="ro"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Acces privat · PLUP</title><link rel="stylesheet" href="/auth/style.css"><main><div class="brand">NRG CABLES · PLUP</div><h1>Conectare securizată</h1><p>'''+escape(message)+'''</p><a href="/auth/member-login">Conectare colegi · utilizator și parolă</a><a class="secondary" href="/auth/login">Proprietar · Continuă cu GitHub</a></main></html>''').encode()
