"""Private PLUP report API with persisted reports, drafts and versions. Run behind an authenticated HTTPS reverse proxy."""
from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
import hashlib
import hmac
import time
from urllib.parse import unquote, urlsplit
from urllib.parse import parse_qs
from server import smart, table_import, identity, members, notifications
from server.corporate import plan_image, production_image, forecast_image
from server import source_table, plan_analysis, forecast_work
from server.source_render import SourceRenderError
from server.ocr import import_plan, import_forecast, ImportError as PlanImportError


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
FIELDS = ("al", "cu", "backlogAl", "backlogCu", "wasteAl", "wasteCu")
LABELS = ("Aluminiu predat", "Cupru predat", "Backlog aluminiu", "Backlog cupru", "Deșeu aluminiu", "Deșeu cupru")
EXTRA = (("op_asumreal","Asumat / realizat"),("op_status","Realizat vs. status"),("op_plan","Realizat vs. plan"),("op_previz","Previzionat schimbul 1"),("op_backal","Backlog aluminiu operațional"),("op_backcu","Backlog cupru operațional"),("op_rigid1","SF Rigid 1"),("op_rigid2","SF Rigid 2"),("op_rigid3","SF Rigid 3"),("op_multi1","SF Multifir 8 căi 1"),("op_multi2","SF Multifir 8 căi 2"),("op_niehoff","SF 16 căi Niehoff"),("op_beta3","SF 16 căi Beta 3"),("op_stocal","Stoc aluminiu"),("op_stoccu","Stoc cupru"),("obs","Observații"))
ZERO = Decimal("0")
MAX_BYTES = 1048576
PLAN_FIELDS = ("client","product","planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods","notes")
PLAN_NUMERIC = ("planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods")
FORECAST_FIELDS = ("material","product","km","tons","client","measure","status","notes")
DB_PATH = Path(os.environ.get("PLUP_DB_PATH", str(ROOT / "data" / "plup.sqlite3")))
PASSWORD = os.environ.get("PLUP_PASSWORD", "")
SESSION_SECRET = os.environ.get("PLUP_SESSION_SECRET", "")
LOGIN_FAILURES = {}
MIME = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".ico": "image/x-icon", ".ttf": "font/ttf"}
SECURITY = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


class InvalidReport(ValueError):
    pass


AMOUNT_LABELS = dict(zip(FIELDS, LABELS)) | dict(zip(PLAN_NUMERIC, ("Metal planificat", "Metal predat", "Sârmă", "Stoc lită", "Stoc funie / bară", "Stoc vane", "Stoc cablat", "Stoc M.I.", "Stoc armat", "Stoc M.F.", "Marfă predată"))) | {"km":"KM", "tons":"Tone"}


def read_amount(raw: object, context: str = "Valoare") -> Decimal:
    if raw is None:
        return ZERO
    if isinstance(raw, str):
        raw = raw.strip().replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
        if raw in ("", "-", "—"):
            return ZERO
    if not isinstance(raw, str) or not re.fullmatch(r"\d{1,7}(?:[.,]\d{1,12})?", raw):
        raise InvalidReport(f'{context}: valoarea „{str(raw)[:80]}” nu este numerică. Folosește virgulă sau punct pentru zecimale (maximum 12).')
    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise InvalidReport(f"{context}: valoare numerică invalidă.") from exc
    if value > Decimal("1000000"):
        raise InvalidReport(f"{context}: valoarea depășește limita de 1.000.000.")
    return value


def process(data: object) -> dict:
    data,source=source_table.split(data)
    if not isinstance(data, dict) or set(data) != {"mode", "date", "values"}:
        raise InvalidReport("Structură invalidă a raportului.")
    mode, values = data["mode"], data["values"]
    if mode not in ("weekday", "weekend") or not isinstance(values, dict):
        raise InvalidReport("Tip de raport invalid.")
    try:
        start = date.fromisoformat(data["date"])
    except (TypeError, ValueError) as exc:
        raise InvalidReport("Data raportului este invalidă.") from exc
    if start.year < 2020 or start.year > 2100:
        raise InvalidReport("Anul raportului este în afara intervalului permis.")
    if mode == "weekend" and start.weekday() != 4:
        raise InvalidReport("Raportul de weekend trebuie să înceapă vineri.")
    days = [start + timedelta(days=i) for i in range(3 if mode == "weekend" else 1)]
    if set(values) - {day.isoformat() for day in days}:
        raise InvalidReport("Raportul conține date din afara perioadei alese.")
    items = []
    totals = {key: ZERO for key in ("handed", "backlog", "waste", "processed")}
    for day in days:
        raw = values.get(day.isoformat(), {})
        if not isinstance(raw, dict) or set(raw) - set(FIELDS) - {key for key,_ in EXTRA}:
            raise InvalidReport("Câmpuri invalide în raport.")
        fields = {key: read_amount(raw.get(key, ""), f"{day.isoformat()} · {AMOUNT_LABELS[key]}") for key in FIELDS}
        extras = {}
        for key,_ in EXTRA:
            value=raw.get(key,"")
            if not isinstance(value,str) or len(value)>120 or any(ord(char)<32 for char in value):
                raise InvalidReport("Indicator operațional invalid.")
            extras[key]=value.strip()
        handed = fields["al"] + fields["cu"]
        backlog = fields["backlogAl"] + fields["backlogCu"]
        waste = fields["wasteAl"] + fields["wasteCu"]
        processed = handed + waste
        summary = {"handed": handed, "backlog": backlog, "waste": waste, "processed": processed}
        for key in totals:
            totals[key] += summary[key]
        items.append({"date": day.isoformat(), "values": fields, "extras":extras, **summary, "percent": waste / processed * 100 if processed else ZERO})
    totals["percent"] = totals["waste"] / totals["processed"] * 100 if totals["processed"] else ZERO
    return source_table.attach({"mode": mode, "date": start.isoformat(), "days": items, "total": totals},source)


def process_plan(data: object) -> dict:
    data,source=source_table.split(data)
    remaining_total_raw=data.get('remainingTotalOverride','') if isinstance(data,dict) else ''
    remaining_total_override=read_amount(remaining_total_raw,'Total rest de predat') if str(remaining_total_raw).strip() else None
    remaining_edits=data.get('remainingOverrides',{}) if isinstance(data,dict) else {}
    if not isinstance(remaining_edits,dict) or len(remaining_edits)>100 or any(not isinstance(k,str) or len(k)>(124 if k.startswith(('AL::','CU::')) else 120) for k in remaining_edits):raise InvalidReport('Rest de predat invalid.')
    remaining_overrides={k:read_amount(v,'Rest de predat '+k) for k,v in remaining_edits.items()}
    stock_names=data.get('stockNames',{}) if isinstance(data,dict) else {}
    if not isinstance(stock_names,dict) or len(stock_names)>120 or any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() or len(k)>150 or len(v)>120 or any(ord(c)<32 for c in v) for k,v in stock_names.items()):raise InvalidReport('Nume client invalid.')
    adjustments=data.get('stockAdjustments',{}) if isinstance(data,dict) else {}
    if not isinstance(adjustments,dict) or len(adjustments)>120 or any(not isinstance(k,str) or len(k)>150 for k in adjustments):raise InvalidReport('Ajustări de stoc invalide.')
    stock_adjustments={k:read_amount(v,'Ajustare '+k) for k,v in adjustments.items()}
    inventory_data=data.get('inventory') if isinstance(data,dict) else None
    if inventory_data is not None:
        from server.inventory import validate as validate_inventory
        validate_inventory(inventory_data)
    extras=data.get('sectionStock',{'samples':'','waste':'','dead':''}) if isinstance(data,dict) else None
    if not isinstance(extras,dict) or (set(extras)-{'samples','waste','dead','blocked','bar95','bar15'} or not {'samples','waste','dead'}<=set(extras)):raise InvalidReport('Stocuri de secție invalide.')
    extras={'blocked':'','bar95':'','bar15':'',**extras}
    section_stock={k:read_amount(v,k) if str(v).strip() else None for k,v in extras.items()}
    if isinstance(data,dict):data={k:v for k,v in data.items() if k not in ('sectionStock','inventory','stockAdjustments','stockNames','remainingOverrides','remainingTotalOverride')}
    if not isinstance(data,dict) or set(data)!={"mode","date","week","incoming","rows"} or data["mode"]!="plan":
        raise InvalidReport("Structură invalidă a planului.")
    try: start=date.fromisoformat(data["date"])
    except (TypeError,ValueError) as exc: raise InvalidReport("Data planului este invalidă.") from exc
    if not 2020<=start.year<=2100 or not isinstance(data["week"],str) or not re.fullmatch(r"[\w -]{0,10}",data["week"],re.UNICODE):
        raise InvalidReport("Data sau săptămâna planului este invalidă.")
    if not isinstance(data["rows"],list) or not (0 if source is not None else 1)<=len(data["rows"])<=100:
        raise InvalidReport("Planul trebuie să aibă între 1 și 100 rânduri.")
    rows=[];totals={material:{key:ZERO for key in PLAN_NUMERIC} for material in ("AL","CU")}
    for index, raw in enumerate(data["rows"], 1):
        if not isinstance(raw,dict) or set(raw)!={"material",*PLAN_FIELDS} or raw["material"] not in ("AL","CU"):
            raise InvalidReport("Rând invalid în plan.")
        row={"material":raw["material"]}
        for key in PLAN_FIELDS:
            val=raw[key]
            if key in PLAN_NUMERIC:
                row[key]=read_amount(val, f"Rând {index} · {raw.get('product', '')} · {AMOUNT_LABELS[key]}")
                totals[row["material"]][key]+=row[key]
            elif not isinstance(val,str) or len(val)>120 or any(ord(char)<32 for char in val):
                raise InvalidReport("Text invalid în plan.")
            else: row[key]=val.strip()
        rows.append(row)
    return source_table.attach({"mode":"plan","remainingTotalOverride":remaining_total_override,"remainingOverrides":remaining_overrides,"stockNames":stock_names,"stockAdjustments":stock_adjustments,**({"inventory":inventory_data} if inventory_data is not None else {}),"sectionStock":section_stock,"date":start.isoformat(),"week":source_table.plan_week(source,data["week"].strip()),"incoming":read_amount(data["incoming"], "Intrări metal"),"rows":rows,"totals":totals},source)


def process_forecast(data: object) -> dict:
    data,source=source_table.split(data)
    if not isinstance(data,dict) or set(data)!={"mode","date","rows"} or data["mode"]!="forecast":
        raise InvalidReport("Structură invalidă a previzului.")
    try:start=date.fromisoformat(data["date"])
    except (TypeError,ValueError) as exc:raise InvalidReport("Data previzului este invalidă.") from exc
    if not 2020<=start.year<=2100 or not isinstance(data["rows"],list) or not (0 if source is not None else 1)<=len(data["rows"])<=100:
        raise InvalidReport("Previzul trebuie să conțină între 1 și 100 produse.")
    totals={key:{"km":ZERO,"tons":ZERO} for key in ("AL","CU")}
    rows=[]
    for index, raw in enumerate(data["rows"], 1):
        if not isinstance(raw,dict) or (set(raw)-forecast_work.FIELDS)!=set(FORECAST_FIELDS) or raw["material"] not in ("AL","CU"):
            raise InvalidReport("Rând invalid în previz.")
        row={"material":raw["material"],"km":read_amount(raw["km"], f"Rând {index} · {raw.get('product', '')} · KM"),"tons":read_amount(raw["tons"], f"Rând {index} · {raw.get('product', '')} · Tone")}
        for key in ("product","client","measure","status","notes"):
            value=raw[key]
            if not isinstance(value,str) or len(value)>120 or any(ord(char)<32 for char in value):
                raise InvalidReport("Text invalid în previz.")
            row[key]=value.strip()
        order=raw.get('order','');priority=raw.get('priority','');drum=raw.get('drumLength','')
        if not isinstance(order,str) or (order and not re.fullmatch(r'[1-9]\d{0,2}',order)):raise InvalidReport(f"Rând {index}: ordinea trebuie să fie un număr între 1 și 999.")
        if not isinstance(priority,str) or priority.strip().casefold() not in ('','normal','urgent'):raise InvalidReport(f"Rând {index}: prioritatea trebuie să fie Normal sau Urgent.")
        row['order']=order;row['priority']=priority.strip().casefold() or 'normal'
        row['drumLength']=read_amount(drum,f"Rând {index} · metri/tambur") if drum not in ('',None) else None
        if row['drumLength'] is not None and row['drumLength']<=0:raise InvalidReport(f"Rând {index}: lungimea pe tambur trebuie să fie mai mare decât zero.")
        if not row["product"]:
            raise InvalidReport("Completează produsul pentru fiecare rând din previz.")
        totals[row["material"]]["km"]+=row["km"]
        totals[row["material"]]["tons"]+=row["tons"]
        rows.append(row)
    orders=[r['order'] for r in rows]
    if any(orders) and (not all(orders) or len(set(orders))!=len(orders)):raise InvalidReport("Completează o ordine distinctă pentru fiecare produs sau lasă toate câmpurile Ordine goale.")
    return source_table.attach({"mode":"forecast","date":start.isoformat(),"rows":rows,"totals":totals,"work":forecast_work.build(rows if source else [r for m in ("AL","CU") for r in rows if r["material"]==m])},source)


def database():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=10)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('weekday','weekend','plan','forecast')), report_date TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
    schema=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reports'").fetchone()[0]
    if "'forecast'" not in schema:
        conn.execute("BEGIN IMMEDIATE")
        try:
            schema=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reports'").fetchone()[0]
            if "'forecast'" in schema:
                conn.commit()
            else:
                conn.execute("DROP TABLE IF EXISTS reports_new")
                conn.execute("CREATE TABLE reports_new (id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('weekday','weekend','plan','forecast')), report_date TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
                conn.execute("INSERT INTO reports_new SELECT id,mode,report_date,created_at,payload FROM reports")
                conn.execute("DROP TABLE reports")
                conn.execute("ALTER TABLE reports_new RENAME TO reports")
                conn.commit()
        except Exception:
            conn.rollback()
            raise
    conn.execute("CREATE INDEX IF NOT EXISTS reports_recent ON reports(created_at DESC)")
    conn.execute("CREATE TABLE IF NOT EXISTS report_defaults (mode TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS plan_snapshots (report_date TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    smart.bootstrap(conn)
    members.bootstrap(conn)
    notifications.bootstrap(conn)
    return conn


def plan_insights(report,payload,production_access=True):
    conn=database()
    try:
        previous,old=plan_analysis.previous(conn,report["date"],process_plan)
        result=plan_analysis.build(report,payload,previous,old)
        if report.get('inventory') and production_access:
            stamp=report['inventory']['date'];context=[]
            for row in conn.execute("SELECT id,payload FROM reports WHERE mode IN ('weekday','weekend') AND report_date<=? AND report_date>=date(?,'-2 days') ORDER BY created_at DESC LIMIT 30",(stamp,stamp)):
                try:production=validate_report(json.loads(row['payload']))
                except (ValueError,TypeError,KeyError):continue
                for day in production['days']:
                    if day['date']==stamp:
                        context.append({'id':row['id'],'date':stamp,'handedAl':day['values']['al'],'wasteAl':day['values']['wasteAl']})
            result['inventory_review']['productionContext']=context
        return result
    finally:conn.close()


def remember_generated(payload,actor='owner'):
    conn=database()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if not members.can_write(conn,actor,payload['mode']):return
            conn.execute("INSERT INTO report_defaults(mode,payload) VALUES (?,?) ON CONFLICT(mode) DO UPDATE SET payload=excluded.payload",
                         (payload["mode"],json.dumps(payload,ensure_ascii=False)))
            if payload['mode']=='plan':
                conn.execute("INSERT INTO plan_snapshots VALUES (?,?) ON CONFLICT(report_date) DO UPDATE SET payload=excluded.payload",(payload['date'],json.dumps(payload,ensure_ascii=False)))
    finally:conn.close()


def latest_template(mode):
    if mode not in ("weekday","weekend","plan","forecast"):
        raise InvalidReport("Tip de raport invalid.")
    conn=database()
    try:
        row=conn.execute("SELECT payload FROM report_defaults WHERE mode=?",(mode,)).fetchone()
        if not row:
            row=conn.execute("SELECT payload FROM reports WHERE mode=? ORDER BY created_at DESC,id DESC LIMIT 1",(mode,)).fetchone()
        return json.loads(row["payload"]) if row else None
    finally:conn.close()


def save_report(payload,actor='owner'):
    if not isinstance(payload,dict): raise InvalidReport("Raport invalid.")
    item=process_plan(payload) if payload.get("mode")=="plan" else process_forecast(payload) if payload.get("mode")=="forecast" else process(payload)
    record={"id":str(uuid.uuid4()),"mode":item["mode"],"date":item["date"],"created_at":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")}
    conn=database()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if not members.can_write(conn,actor,item['mode']):raise InvalidReport('Accesul de editare nu mai este disponibil.')
            conn.execute("INSERT INTO reports (id,mode,report_date,created_at,payload) VALUES (?,?,?,?,?)",(record["id"],record["mode"],record["date"],record["created_at"],json.dumps(payload,ensure_ascii=False)))
            record["version"]=smart.revision(conn,record["id"],payload,"create")
            if actor=='owner':conn.execute("DELETE FROM drafts WHERE mode=?",(item["mode"],))
            else:conn.execute("DELETE FROM member_drafts WHERE member_id=? AND mode=?",(actor,item["mode"]))
            members.event(conn,actor,'report-create',record['id'],{'mode':item['mode'],'date':item['date'],'version':record['version']})
    finally:conn.close()
    return record


def validate_report(payload):
    return process_plan(payload) if isinstance(payload,dict) and payload.get("mode")=="plan" else process_forecast(payload) if isinstance(payload,dict) and payload.get("mode")=="forecast" else process(payload)


def update_report(identifier, payload, expected=None, action="edit", actor="owner"):
    item=validate_report(payload)
    conn=database()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            previous=conn.execute("SELECT payload,mode FROM reports WHERE id=?",(identifier,)).fetchone()
            if not previous:raise InvalidReport("Raportul din istoric nu există.")
            if not members.can_write(conn,actor,previous['mode']) or not members.can_write(conn,actor,item['mode']):raise InvalidReport('Accesul de editare nu mai este disponibil.')
            current=smart.latest_version(conn,identifier)
            if expected is not None and int(expected)!=current:raise InvalidReport("Raportul a fost modificat între timp. Redeschide-l din istoric înainte de salvare.")
            if not current:smart.revision(conn,identifier,json.loads(previous["payload"]),"baseline")
            conn.execute("UPDATE reports SET mode=?,report_date=?,payload=? WHERE id=?",(item["mode"],item["date"],json.dumps(payload,ensure_ascii=False),identifier))
            version=smart.revision(conn,identifier,payload,action)
            if actor=='owner':conn.execute("DELETE FROM drafts WHERE mode=?",(item["mode"],))
            else:conn.execute("DELETE FROM member_drafts WHERE member_id=? AND mode=?",(actor,item["mode"]))
            members.event(conn,actor,'report-'+action,identifier,{'mode':item['mode'],'date':item['date'],'version':version})
    finally:conn.close()
    return {"id":identifier,"mode":item["mode"],"date":item["date"],"version":version}


def serialize(result: dict) -> dict:
    def convert(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, dict):
            return {key: convert(value) for key, value in obj.items()}
        if isinstance(obj, list):
            return [convert(value) for value in obj]
        return obj
    return convert(result)


def client_device(headers):
    agent = headers.get('User-Agent', '').lower()
    if 'ipad' in agent or ('android' in agent and 'mobile' not in agent):
        return 'Tabletă'
    if headers.get('Sec-CH-UA-Mobile') == '?1' or any(token in agent for token in ('iphone', 'android', 'mobile')):
        return 'Telefon'
    if any(token in agent for token in ('windows', 'macintosh', 'linux', 'cros')):
        return 'Desktop'
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "PLUP"
    sys_version = ""

    def respond(self,status:int,body:bytes,mime:str,headers=None):
        policy=SECURITY
        if mime.startswith("text/html") and b"__PLUP_STYLE_NONCE__" in body:
            nonce=uuid.uuid4().hex
            body=body.replace(b"__PLUP_STYLE_NONCE__",nonce.encode())
            policy={**SECURITY,"Content-Security-Policy":SECURITY["Content-Security-Policy"].replace("style-src 'self'",f"style-src 'self' 'nonce-{nonce}'")}
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(body)))
        for key,value in policy.items():self.send_header(key,value)
        if identity.enabled():self.send_header('Strict-Transport-Security','max-age=31536000')
        for key,value in (headers or {}).items():
            for entry in (value if isinstance(value,list) else [value]):self.send_header(key,entry)
        self.end_headers()
        self.wfile.write(body)

    def error(self,status:int,message:str):
        self.respond(status,json.dumps({"error":message},ensure_ascii=False).encode(),"application/json; charset=utf-8")

    def principal(self):
        if not identity.enabled():return members.OWNER.copy() if self.session() else None
        if identity.session(self.headers):return members.OWNER.copy()
        return members.principal(DB_PATH,identity.cookie(self.headers,members.COOKIE))

    def permitted(self,mode,write=False):
        person=self.principal()
        if not person or mode not in person['modules'] or (write and person['role']=='viewer'):
            self.error(403,"Nu ai permisiune pentru această operațiune.");return False
        return True

    def owner_only(self):
        if not self.principal() or self.principal()['role']!='owner':
            self.error(403,"Doar proprietarul poate administra accesul și backupurile.");return False
        return True

    def report_permission(self,identifier,write=False):
        conn=database()
        try:row=conn.execute('SELECT mode FROM reports WHERE id=?',(identifier,)).fetchone()
        finally:conn.close()
        if not row:self.error(404,"Raport inexistent.");return False
        return self.permitted(row['mode'],write)

    def session(self):
        if identity.enabled():
            owner=identity.session(self.headers)
            if owner:return owner
            token=identity.cookie(self.headers,members.COOKIE)
            return token if members.principal(DB_PATH,token) else None
        if not PASSWORD:return "local"
        cookie=self.headers.get("Cookie","")
        match=re.search(r"(?:^|;\s*)plup_session=([0-9]+\.[a-f0-9]{64})(?:;|$)",cookie)
        if not match:return None
        token=match.group(1);stamp,signature=token.split(".")
        if abs(time.time()-int(stamp))>28800:return None
        expected=hmac.new(SESSION_SECRET.encode(),stamp.encode(),hashlib.sha256).hexdigest()
        return token if hmac.compare_digest(signature,expected) else None

    def authorize(self,mutation=False):
        token=self.session()
        if not token:self.error(401,"Autentificarea este necesară.");return False
        if self.path.startswith('/api/admin/') and not self.owner_only():return False
        person=self.principal()
        if not person:self.error(401,"Autentificarea este necesară.");return False
        if mutation and person['role']=='viewer' and (self.command=='PUT' or urlsplit(self.path).path in ('/api/reports','/api/smart/draft','/api/smart/restore','/api/smart/table','/api/plan/import','/api/forecast/import','/api/inventory/import')):
            self.error(403,"Contul Cititor poate consulta și exporta rapoartele permise.");return False
        if mutation and (PASSWORD or identity.enabled()):
            expected=hmac.new(SESSION_SECRET.encode(),("csrf:"+token).encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(self.headers.get("X-CSRF-Token",""),expected):
                self.error(403,"Sesiune invalidă. Reîncarcă pagina.");return False
        return True

    def colleague_event(self, person, action, target='', detail=None):
        if not person or person['id'] == 'owner':
            return
        try:
            with closing(database()) as conn, conn:
                if action == 'report-generate' and target:
                    conn.execute('BEGIN IMMEDIATE')
                    if conn.execute(
                        "SELECT 1 FROM access_events WHERE actor=? AND target=? AND action='report-generate'",
                        (person['id'], target),
                    ).fetchone():
                        return
                members.event(conn, person['id'], action, target, detail)
        except sqlite3.Error:
            print('PLUP could not record colleague activity', flush=True)

    def do_GET(self):
        pathname=unquote(urlsplit(self.path).path)
        if pathname=="/health":
            self.respond(200,b"ok","text/plain; charset=utf-8");return
        push_assets = {
            '/push-worker.js': 'text/javascript', '/plup.webmanifest': 'application/manifest+json',
            '/plup-icon.svg': 'image/svg+xml',
        }
        if pathname in push_assets:
            self.respond(200, (WEB / pathname[1:]).read_bytes(), push_assets[pathname]);return
        if identity.enabled():
            if pathname == '/invite':
                self.respond(303,b'','text/plain',{'Location':'/auth/member-login'});return
            if pathname == '/auth/member-login':
                from server.member_pages import page
                self.respond(200,page(),'text/html; charset=utf-8');return
            if pathname=='/auth/member.js':
                self.respond(200,(WEB/'member-login.js').read_bytes(),'text/javascript; charset=utf-8');return
            if pathname=="/auth/style.css":
                self.respond(200,identity.STYLE,"text/css; charset=utf-8");return
            if pathname in ("/auth/login","/auth/callback"):
                try:
                    if pathname=="/auth/login":
                        location,binding=identity.start()
                        self.respond(303,b"","text/plain",{"Location":location,"Set-Cookie":f"__Host-plup_oauth={binding}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=600"});return
                    origin=identity.config()[0]
                    if self.headers.get('Host') != urlsplit(origin).netloc:
                        self.error(400,"Adresă de conectare invalidă.");return
                    token=identity.finish(parse_qs(urlsplit(self.path).query),self.headers)
                    self.respond(303,b"","text/plain",{"Location":origin+'/',"Set-Cookie":f"__Host-plup_identity={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={identity.TTL}"});return
                except ValueError as exc:
                    self.respond(403,identity.page(str(exc)),"text/html; charset=utf-8");return
            if pathname != '/api/session' and not self.session():
                if pathname.startswith('/api/'):
                    self.error(401,"Autentificarea este necesară.")
                else:
                    try:identity.config();status,message=200,'Acces privat pentru proprietar și colegii cu un cont PLUP.'
                    except ValueError:status,message=503,'Accesul prin browser este în curs de configurare.'
                    self.respond(status,identity.page(message),"text/html; charset=utf-8")
                return
        if pathname=="/api/session":
            token=self.session()
            csrf=hmac.new(SESSION_SECRET.encode(),("csrf:"+token).encode(),hashlib.sha256).hexdigest() if (PASSWORD or identity.enabled()) and token else ""
            self.respond(200,json.dumps({"authenticated":bool(token),"csrf":csrf,"provider":("github" if (self.principal() and self.principal()['role']=='owner') or (not self.principal() and not identity.cookie(self.headers,members.COOKIE)) else "email") if identity.enabled() else "password","user":self.principal()}).encode(),"application/json; charset=utf-8");return
        if pathname == '/api/admin/push':
            if not self.authorize():return
            with closing(database()) as conn:
                result = {'publicKey': notifications.public_key(conn)}
            self.respond(200, json.dumps(result).encode(), 'application/json');return
        if pathname=='/api/admin/members':
            if not self.authorize() or not self.owner_only():return
            conn=database()
            try:result=members.listing(conn)
            finally:conn.close()
            self.respond(200,json.dumps(result,ensure_ascii=False).encode(),'application/json');return
        if pathname in ("/api/smart/dashboard","/api/smart/drafts","/api/smart/versions"):
            if not self.authorize():return
            query=parse_qs(urlsplit(self.path).query);conn=database()
            try:
                if pathname.endswith("dashboard"):
                    days=int(query.get("days",[7])[0])
                    if days not in (7,30):raise ValueError("Perioadă invalidă.")
                    result=smart.dashboard(conn,query.get("date",[date.today().isoformat()])[0],days,validate_report,self.principal()["modules"])
                elif pathname.endswith("drafts"):
                    person=self.principal()
                    rows=conn.execute("SELECT * FROM drafts") if person['id']=='owner' else conn.execute("SELECT * FROM member_drafts WHERE member_id=?",(person['id'],))
                    result=[{"mode":r["mode"],"updated_at":r["updated_at"],"payload":json.loads(r["payload"]),"metadata":json.loads(r["metadata"])} for r in rows if r['mode'] in person['modules']] if person['role']!='viewer' else []
                else:
                    identifier=query.get("id",[""])[0];uuid.UUID(identifier)
                    if not self.report_permission(identifier):return
                    result=[dict(r) for r in conn.execute("SELECT version,created_at,action,payload FROM report_versions WHERE report_id=? ORDER BY version DESC LIMIT 100",(identifier,))]
                    for r in result:r["payload"]=json.loads(r["payload"])
                    result=[r for r in result if r["payload"].get("mode") in self.principal()["modules"]]
            except (ValueError,TypeError):self.error(400,"Solicitare invalidă.");return
            finally:conn.close()
            self.respond(200,json.dumps(serialize(result),ensure_ascii=False).encode(),"application/json; charset=utf-8");return
        if pathname=="/api/admin/export":
            if not self.authorize():return
            from server import data_admin
            kind=parse_qs(urlsplit(self.path).query).get('format',['json'])[0]
            conn=database()
            try:
                if kind=='json':content=json.dumps(data_admin.snapshot(conn),ensure_ascii=False).encode();mime='application/json';ext='json'
                elif kind=='sqlite':content=data_admin.sqlite_bytes(conn);mime='application/octet-stream';ext='sqlite3'
                elif kind=='csv':content=data_admin.csv_bytes(conn);mime='application/zip';ext='zip'
                else:self.error(400,'Format invalid.');return
            finally:conn.close()
            self.respond(200,content,mime,{'Content-Disposition':'attachment; filename="PLUP_backup_'+date.today().isoformat()+'.'+ext+'"','Cache-Control':'no-store'});return
        if pathname=="/api/reports":
            if not self.authorize():return
            try:
                query=parse_qs(urlsplit(self.path).query)
                limit=max(1,min(100,int(query.get("limit",[50])[0])))
                offset=max(0,int(query.get("offset",[0])[0]))
            except ValueError: self.error(400,"Limită invalidă.");return
            conn=database()
            try:
                modes=self.principal()['modules'];marks=','.join('?' for _ in modes)
                records=[dict(row) for row in conn.execute("SELECT id,mode,report_date AS date,created_at,COALESCE((SELECT MAX(created_at) FROM report_versions v WHERE v.report_id=reports.id),created_at) AS updated_at FROM reports WHERE mode IN ("+marks+") ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",(*modes,limit,offset))]
            finally: conn.close()
            self.respond(200,json.dumps(records).encode(),"application/json; charset=utf-8");return
        if pathname=="/api/reports/latest":
            if not self.authorize():return
            mode=parse_qs(urlsplit(self.path).query).get("mode",[""])[0]
            if not self.permitted(mode):return
            try:payload=latest_template(mode)
            except InvalidReport as exc:self.error(400,str(exc));return
            self.respond(200,json.dumps({"payload":payload},ensure_ascii=False).encode(),"application/json; charset=utf-8");return
        if pathname.startswith("/api/reports/"):
            if not self.authorize():return
            identifier=pathname.rsplit("/",1)[-1]
            try: uuid.UUID(identifier)
            except ValueError: self.error(404,"Raport inexistent.");return
            conn=database()
            try: record=conn.execute("SELECT id,mode,report_date AS date,created_at,payload FROM reports WHERE id=?",(identifier,)).fetchone()
            finally: conn.close()
            if not record: self.error(404,"Raport inexistent.");return
            if not self.permitted(record["mode"]):return
            result=dict(record);result["payload"]=json.loads(result["payload"]);conn=database()
            try:result["version"]=smart.latest_version(conn,identifier)
            finally:conn.close()
            self.colleague_event(self.principal(), 'report-open', identifier, {'mode': record['mode']})
            self.respond(200,json.dumps(result,ensure_ascii=False).encode(),"application/json; charset=utf-8");return
        if pathname == "/":pathname="/index.html"
        if pathname.startswith("/api/"):
            self.error(404,"Resursa nu există.");return
        target=(WEB/pathname.lstrip("/")).resolve()
        if not target.is_relative_to(WEB) or target.suffix not in MIME or not target.is_file():
            self.error(404,"Resursa nu există.");return
        content=target.read_bytes()
        if target.name=='index.html':
            from html import escape
            access=escape(json.dumps(self.principal(),ensure_ascii=False),quote=True)
            content=content.replace(b'</head>',('<meta name="plup-access" content="'+access+'"></head>').encode())
        self.respond(200,content,MIME[target.suffix]+("; charset=utf-8" if target.suffix in (".html",".css",".js") else ""))

    def do_POST(self):
        parts=urlsplit(self.path);path=parts.path
        if identity.enabled() and path == '/auth/member-login':
            self.member_auth();return
        if identity.enabled() and path=='/api/login':
            self.error(403,"Conectarea prin parolă este dezactivată. Folosește GitHub.");return
        if identity.enabled() and path=='/auth/logout':
            if not self.same_origin():
                self.error(403,"Origine neautorizată.");return
            if not self.authorize(mutation=True):return
            person=self.principal();conn=database()
            try:
                with conn:
                    conn.execute('DELETE FROM member_sessions WHERE token_hash=?',(members.digest(identity.cookie(self.headers,members.COOKIE)),))
                    members.event(conn,person['id'],'logout',person['id'])
            finally:conn.close()
            identity.logout(self.headers)
            self.respond(200,b'{}','application/json',{'Set-Cookie':[name+'=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0' for name in ('__Host-plup_identity',members.COOKIE)]});return
        if path not in ("/api/login","/api/compute","/api/reports","/api/render","/api/plan/analysis","/api/plan/import","/api/forecast/import","/api/smart/check","/api/smart/draft","/api/smart/restore","/api/smart/table","/api/admin/preview","/api/admin/import","/api/inventory/import","/api/admin/members/create","/api/admin/members/update","/api/admin/push","/api/activity"):
            self.error(404,"Resursa nu există.");return
        origin=self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.error(403,"Origine neautorizată.");return
        if path!="/api/login" and not self.authorize(mutation=True):return
        if self.headers.get("Content-Type","").split(";")[0].strip().lower() != "application/json":
            self.error(415,"Este necesar application/json.");return
        length=self.headers.get("Content-Length","")
        limit=4096 if path.startswith('/api/admin/members/') or path in ('/api/admin/push','/api/activity') else 50_000_000 if path.startswith('/api/admin/') else 8_000_200 if path in ("/api/plan/import","/api/forecast/import","/api/smart/table","/api/inventory/import") else MAX_BYTES
        if not length.isdecimal() or int(length)>limit:
            self.error(413,"Raport prea mare.");return
        try:
            body=json.loads(self.rfile.read(int(length)))
            person=self.principal()
            if path == '/api/admin/push':
                action = body.get('action') if isinstance(body, dict) else None
                if action not in ('enable', 'disable', 'status', 'test'):
                    raise ValueError('Acțiune invalidă.')
                with closing(database()) as conn:
                    result = notifications.device(conn, action, body)
                self.respond(200, json.dumps(result).encode(), 'application/json');return
            if path == '/api/activity':
                mode = body.get('mode') if isinstance(body, dict) else None
                action = body.get('action') if isinstance(body, dict) else None
                if mode not in members.MODES or action not in ('report-download', 'table-apply'):
                    raise ValueError('Acțiune invalidă.')
                if not self.permitted(mode, action == 'table-apply'):return
                self.colleague_event(person, action, detail={'mode':mode})
                self.respond(200, b'{}', 'application/json');return
            if path in ('/api/admin/members/create','/api/admin/members/update'):
                conn=database()
                try:result=members.create(conn,body) if path.endswith('/create') else members.update(conn,body)
                finally:conn.close()
                self.respond(200,json.dumps(result).encode(),'application/json');return
            scoped=body.get('payload') if path=='/api/smart/draft' and isinstance(body,dict) else body
            if isinstance(scoped,dict) and scoped.get('mode') and not self.permitted(scoped['mode'],path in ('/api/reports','/api/smart/draft')):return
            fixed={'/api/plan/analysis':'plan','/api/plan/import':'plan','/api/inventory/import':'plan','/api/forecast/import':'forecast'}
            if path in fixed and not self.permitted(fixed[path],path.endswith('/import')):return
            if path in ('/api/admin/preview','/api/admin/import'):
                from server import data_admin
                try:
                    backup=data_admin.validate(body.get('backup'),validate_report)
                    conn=database()
                    try:
                        result=data_admin.preview(conn,backup) if path.endswith('preview') else data_admin.restore(conn,backup,body.get('action'),body.get('expected'),DB_PATH)
                    finally:conn.close()
                except (ValueError,TypeError,KeyError,sqlite3.Error) as exc:self.error(400,str(exc));return
                self.respond(200,json.dumps(result,ensure_ascii=False).encode(),'application/json');return
            if path=="/api/inventory/import":
                from server.inventory import read as read_inventory
                try:result=read_inventory(body)
                except ValueError as exc:raise InvalidReport(str(exc))
                self.colleague_event(person, 'inventory-import', detail={'mode':'plan'})
                self.respond(200,json.dumps(result,ensure_ascii=False).encode(),'application/json');return
            if path=="/api/smart/table":
                result=table_import.read(body)
                mode = self.headers.get('X-PLUP-Module')
                if mode not in person['modules']:
                    mode = None
                self.colleague_event(person, 'table-import', detail={'mode':mode})
                self.respond(200,json.dumps(result,ensure_ascii=False).encode(),"application/json; charset=utf-8");return
            if path in ("/api/smart/check","/api/smart/draft","/api/smart/restore"):
                if path.endswith("check"):
                    conn=database()
                    try:result=smart.checks(body,validate_report,conn if "plan" in person["modules"] else None)
                    finally:conn.close()
                    self.colleague_event(person, 'report-check', detail={'mode':body.get('mode')})
                elif path.endswith("draft"):
                    conn=database()
                    try:
                        result=smart.draft_save(conn,body) if person["id"]=="owner" else members.draft_save(conn,body,person["id"])
                    finally:conn.close()
                else:
                    if not isinstance(body,dict) or set(body)!={"id","version","expected"} or type(body.get("version")) is not int or type(body.get("expected")) is not int:raise InvalidReport("Restaurare invalidă.")
                    uuid.UUID(body["id"])
                    if not self.report_permission(body["id"],True):return
                    conn=database()
                    try:old=conn.execute("SELECT payload FROM report_versions WHERE report_id=? AND version=?",(body["id"],int(body["version"]))).fetchone()
                    finally:conn.close()
                    if not old:raise InvalidReport("Versiunea nu există.")
                    previous=json.loads(old['payload'])
                    if not self.permitted(previous['mode'],True):return
                    result=update_report(body["id"],previous,body["expected"],"restore",person['id'])
                self.respond(200,json.dumps(serialize(result),ensure_ascii=False).encode(),"application/json; charset=utf-8");return
            if path in ("/api/plan/import","/api/forecast/import"):
                if not isinstance(body,dict) or set(body)!={"image"}:
                    raise PlanImportError("Imagine invalidă.")
                result=import_plan(body["image"]) if path=="/api/plan/import" else import_forecast(body["image"])
                self.colleague_event(person, 'image-import', detail={'mode':fixed[path]})
                self.respond(200,json.dumps(result,ensure_ascii=False).encode(),"application/json; charset=utf-8");return
            if path=="/api/plan/analysis":
                report=process_plan(body);result=plan_insights(report,body,"weekday" in person["modules"])
                self.respond(200,json.dumps(serialize(result),ensure_ascii=False).encode(),"application/json; charset=utf-8");return
            if path=="/api/login":
                key=self.client_address[0];now=time.monotonic()
                failures=[t for t in LOGIN_FAILURES.get(key,[]) if now-t<600]
                if len(failures)>=5:self.error(429,"Prea multe încercări. Reîncearcă mai târziu.");return
                supplied=body.get("password","") if isinstance(body,dict) else ""
                if not PASSWORD or not isinstance(supplied,str) or not hmac.compare_digest(supplied,PASSWORD):
                    LOGIN_FAILURES[key]=failures+[now];self.error(401,"Parolă incorectă.");return
                LOGIN_FAILURES.pop(key,None)
                stamp=str(int(time.time()))
                token=stamp+"."+hmac.new(SESSION_SECRET.encode(),stamp.encode(),hashlib.sha256).hexdigest()
                csrf=hmac.new(SESSION_SECRET.encode(),("csrf:"+token).encode(),hashlib.sha256).hexdigest()
                self.respond(200,json.dumps({"authenticated":True,"csrf":csrf}).encode(),"application/json; charset=utf-8",{"Set-Cookie":f"plup_session={token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=28800"});return
            if path=="/api/reports":
                saved=save_report(body,person["id"])
                self.respond(201,json.dumps(saved).encode(),"application/json; charset=utf-8");return
            report=process_plan(body) if isinstance(body,dict) and body.get("mode")=="plan" else process_forecast(body) if isinstance(body,dict) and body.get("mode")=="forecast" else process(body)
        except (ValueError,UnicodeDecodeError,TypeError,OverflowError) as exc:
            self.error(400,str(exc) if isinstance(exc,(InvalidReport,PlanImportError)) or ((path.startswith("/api/smart/") or path.startswith("/api/admin/members/") or path in ("/api/admin/push","/api/activity")) and type(exc) is ValueError) else "Raport invalid.");return
        if path=="/api/render":
            try:
                params=parse_qs(parts.query)
                theme=params.get("theme",["light"])[0]
                if theme not in ("light","dark"):raise ValueError("Temă invalidă")
                page=int(params.get("page",[0])[0]);section=params.get("section",["all" if report["mode"]=="forecast" else "summary"])[0]
                if report["mode"] in ("plan","forecast"):
                    if (page!=0 and section not in ("clients","stock")) or section not in (("overview","summary","table","clients","stock") if report["mode"]=="plan" else ("all","summary","table")):raise ValueError("Secțiune invalidă")
                    image=plan_image(report,theme,plan_insights(report,body,"weekday" in person["modules"]) if section in ("overview","summary","clients","stock") else None,section,page) if report["mode"]=="plan" else forecast_image(report,theme,params.get("status",["1"])[0]=="1",section)
                else:image=production_image(report,page,theme)
            except SourceRenderError as exc: self.error(400,str(exc));return
            except (ValueError,KeyError): self.error(400,"Pagină invalidă.");return
            if person["role"]!="viewer":remember_generated(body,person["id"])
            batch = self.headers.get('X-PLUP-Export', '')
            if not re.fullmatch(r'[a-f0-9-]{36}', batch):
                batch = str(uuid.uuid4())
            self.colleague_event(person, 'report-generate', batch,
                                 {'mode':report['mode'], 'date':report['date']})
            self.respond(200,image,"image/png")
        else:
            self.respond(200,json.dumps(serialize(report),ensure_ascii=False).encode(),"application/json; charset=utf-8")

    def same_origin(self):
        origin = self.headers.get('Origin')
        return (urlsplit(origin).netloc == self.headers.get('Host') if origin is not None
                else self.headers.get('Sec-Fetch-Site') == 'same-origin')

    def member_auth(self):
        if not self.same_origin():
            self.error(403,'Origine neautorizată.');return
        if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':
            self.error(415,'Este necesar application/json.');return
        length=self.headers.get('Content-Length','')
        if not length.isdecimal() or int(length)>4096:
            self.error(413,'Solicitare prea mare.');return
        try:
            body=json.loads(self.rfile.read(int(length)));conn=database()
            try:
                token=members.login(conn,body,self.client_address[0], client_device(self.headers));result={'ok':True}
            finally:conn.close()
            headers=None
            if token:
                # A successful colleague login explicitly switches this browser's identity.
                # Never leave a valid owner's cookie taking precedence over the new account.
                identity.logout(self.headers)
                conn=database()
                try:
                    with conn:conn.execute('DELETE FROM member_sessions WHERE token_hash=?',(members.digest(identity.cookie(self.headers,members.COOKIE)),))
                finally:conn.close()
                headers={'Set-Cookie':[f'{members.COOKIE}={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={members.TTL}',
                                      '__Host-plup_identity=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0']}
            self.respond(200,json.dumps(result,ensure_ascii=False).encode(),'application/json',headers)
        except (ValueError,TypeError,UnicodeDecodeError) as exc:
            self.error(429 if 'Prea multe' in str(exc) else 400,str(exc) if type(exc) is ValueError else 'Solicitare invalidă.')

    def do_PUT(self):
        path=urlsplit(self.path).path
        if not path.startswith("/api/reports/"):
            self.error(404,"Resursa nu există.");return
        if not self.authorize(mutation=True):return
        identifier=path.rsplit("/",1)[-1]
        try:uuid.UUID(identifier)
        except ValueError:self.error(404,"Raport inexistent.");return
        origin=self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.error(403,"Origine neautorizată.");return
        if self.headers.get("Content-Type","").split(";")[0].strip().lower()!="application/json":
            self.error(415,"Este necesar application/json.");return
        length=self.headers.get("Content-Length","")
        if not length.isdecimal() or int(length)>MAX_BYTES:
            self.error(413,"Raport prea mare.");return
        if not self.report_permission(identifier,True):return
        try:
            body=json.loads(self.rfile.read(int(length)))
            if not isinstance(body,dict) or not self.permitted(body.get('mode'),True):return
            record=update_report(identifier,body,self.headers.get("X-Report-Version"),actor=self.principal()['id'])
        except (ValueError,UnicodeDecodeError,TypeError,OverflowError) as exc:
            self.error(400,str(exc) if isinstance(exc,InvalidReport) else "Raport invalid.");return
        self.respond(200,json.dumps(record).encode(),"application/json; charset=utf-8")

    def log_message(self,format,*args):
        # Do not log production values or PDF contents.
        pass


if __name__=="__main__":
    if identity.enabled():
        issues=identity.configuration_issues()
        print('PLUP identity configuration: '+(', '.join(issues) if issues else 'ready'),flush=True)
    host=os.environ.get("PLUP_HOST","127.0.0.1")
    port=int(os.environ.get("PORT","8000"))
    if host not in ("127.0.0.1","::1","localhost") and (len(PASSWORD)<16 or len(SESSION_SECRET)<32):
        raise SystemExit("For network hosting, set PLUP_PASSWORD (16+ characters) and PLUP_SESSION_SECRET (32+ characters).")
    with closing(database()):
        pass
    if identity.enabled() and not identity.configuration_issues():
        notifications.start(DB_PATH, identity.config()[0])
    print(f"PLUP server on http://{host}:{port}",flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
