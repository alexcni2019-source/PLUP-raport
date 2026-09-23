"""Stateless PLUP report API. Run behind an authenticated HTTPS reverse proxy."""
from __future__ import annotations

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
from server.render import plan_image, production_image
from server.ocr import import_plan, ImportError as PlanImportError


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
FIELDS = ("al", "cu", "backlogAl", "backlogCu", "wasteAl", "wasteCu")
LABELS = ("Aluminiu predat", "Cupru predat", "Backlog aluminiu", "Backlog cupru", "Deșeu aluminiu", "Deșeu cupru")
EXTRA = (("op_asumreal","Asumat / realizat"),("op_status","Realizat vs. status"),("op_plan","Realizat vs. plan"),("op_previz","Previzionat schimbul 1"),("op_backal","Backlog aluminiu operațional"),("op_backcu","Backlog cupru operațional"),("op_rigid1","SF Rigid 1"),("op_rigid2","SF Rigid 2"),("op_rigid3","SF Rigid 3"),("op_multi1","SF Multifir 8 căi 1"),("op_multi2","SF Multifir 8 căi 2"),("op_niehoff","SF 16 căi Niehoff"),("op_beta3","SF 16 căi Beta 3"),("op_stocal","Stoc aluminiu"),("op_stoccu","Stoc cupru"),("obs","Observații"))
ZERO = Decimal("0")
MAX_BYTES = 262144
PLAN_FIELDS = ("client","product","planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods","notes")
PLAN_NUMERIC = ("planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods")
DB_PATH = Path(os.environ.get("PLUP_DB_PATH", str(ROOT / "data" / "plup.sqlite3")))
PASSWORD = os.environ.get("PLUP_PASSWORD", "")
SESSION_SECRET = os.environ.get("PLUP_SESSION_SECRET", "")
LOGIN_FAILURES = {}
MIME = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".ico": "image/x-icon"}
SECURITY = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


class InvalidReport(ValueError):
    pass


def read_amount(raw: object) -> Decimal:
    if raw is None or raw == "":
        return ZERO
    if not isinstance(raw, str) or not re.fullmatch(r"\d{1,7}(?:[.,]\d{1,4})?", raw):
        raise InvalidReport("Valorile trebuie să fie numere pozitive, cu maximum 4 zecimale.")
    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise InvalidReport("Valoare numerică invalidă.") from exc
    if value > Decimal("1000000"):
        raise InvalidReport("O valoare depășește limita permisă.")
    return value


def process(data: object) -> dict:
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
    if mode == "weekday" and start.weekday() > 3:
        raise InvalidReport("Raportul zilnic acceptă luni–joi.")
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
        fields = {key: read_amount(raw.get(key, "")) for key in FIELDS}
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
    return {"mode": mode, "date": start.isoformat(), "days": items, "total": totals}


def process_plan(data: object) -> dict:
    if not isinstance(data,dict) or set(data)!={"mode","date","week","incoming","rows"} or data["mode"]!="plan":
        raise InvalidReport("Structură invalidă a planului.")
    try: start=date.fromisoformat(data["date"])
    except (TypeError,ValueError) as exc: raise InvalidReport("Data planului este invalidă.") from exc
    if not 2020<=start.year<=2100 or not isinstance(data["week"],str) or not re.fullmatch(r"[\w -]{0,10}",data["week"],re.UNICODE):
        raise InvalidReport("Data sau săptămâna planului este invalidă.")
    if not isinstance(data["rows"],list) or not 1<=len(data["rows"])<=100:
        raise InvalidReport("Planul trebuie să aibă între 1 și 100 rânduri.")
    rows=[];totals={material:{key:ZERO for key in PLAN_NUMERIC} for material in ("AL","CU")}
    for raw in data["rows"]:
        if not isinstance(raw,dict) or set(raw)!={"material",*PLAN_FIELDS} or raw["material"] not in ("AL","CU"):
            raise InvalidReport("Rând invalid în plan.")
        row={"material":raw["material"]}
        for key in PLAN_FIELDS:
            val=raw[key]
            if key in PLAN_NUMERIC:
                row[key]=read_amount(val)
                totals[row["material"]][key]+=row[key]
            elif not isinstance(val,str) or len(val)>120 or any(ord(char)<32 for char in val):
                raise InvalidReport("Text invalid în plan.")
            else: row[key]=val.strip()
        rows.append(row)
    return {"mode":"plan","date":start.isoformat(),"week":data["week"].strip(),"incoming":read_amount(data["incoming"]),"rows":rows,"totals":totals}


def database():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=10)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('weekday','weekend','plan')), report_date TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS reports_recent ON reports(created_at DESC)")
    return conn


def save_report(payload):
    if not isinstance(payload,dict): raise InvalidReport("Raport invalid.")
    item=process_plan(payload) if payload.get("mode")=="plan" else process(payload)
    record={"id":str(uuid.uuid4()),"mode":item["mode"],"date":item["date"],"created_at":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")}
    conn=database()
    try:
        with conn:
            conn.execute("INSERT INTO reports (id,mode,report_date,created_at,payload) VALUES (?,?,?,?,?)",(record["id"],record["mode"],record["date"],record["created_at"],json.dumps(payload,ensure_ascii=False)))
    finally:conn.close()
    return record


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


class Handler(BaseHTTPRequestHandler):
    server_version = "PLUP"
    sys_version = ""

    def respond(self,status:int,body:bytes,mime:str,headers=None):
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(body)))
        for key,value in SECURITY.items():self.send_header(key,value)
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.end_headers()
        self.wfile.write(body)

    def error(self,status:int,message:str):
        self.respond(status,json.dumps({"error":message},ensure_ascii=False).encode(),"application/json; charset=utf-8")

    def session(self):
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
        if mutation and PASSWORD:
            expected=hmac.new(SESSION_SECRET.encode(),("csrf:"+token).encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(self.headers.get("X-CSRF-Token",""),expected):
                self.error(403,"Sesiune invalidă. Reîncarcă pagina.");return False
        return True

    def do_GET(self):
        pathname=unquote(urlsplit(self.path).path)
        if pathname=="/health":
            self.respond(200,b"ok","text/plain; charset=utf-8");return
        if pathname=="/api/session":
            token=self.session()
            csrf=hmac.new(SESSION_SECRET.encode(),("csrf:"+token).encode(),hashlib.sha256).hexdigest() if PASSWORD and token else ""
            self.respond(200,json.dumps({"authenticated":bool(token),"csrf":csrf}).encode(),"application/json; charset=utf-8");return
        if pathname=="/api/reports":
            if not self.authorize():return
            try:
                query=parse_qs(urlsplit(self.path).query)
                limit=max(1,min(100,int(query.get("limit",[50])[0])))
                offset=max(0,int(query.get("offset",[0])[0]))
            except ValueError: self.error(400,"Limită invalidă.");return
            conn=database()
            try: records=[dict(row) for row in conn.execute("SELECT id,mode,report_date AS date,created_at FROM reports ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",(limit,offset))]
            finally: conn.close()
            self.respond(200,json.dumps(records).encode(),"application/json; charset=utf-8");return
        if pathname.startswith("/api/reports/"):
            if not self.authorize():return
            identifier=pathname.rsplit("/",1)[-1]
            try: uuid.UUID(identifier)
            except ValueError: self.error(404,"Raport inexistent.");return
            conn=database()
            try: record=conn.execute("SELECT id,mode,report_date AS date,created_at,payload FROM reports WHERE id=?",(identifier,)).fetchone()
            finally: conn.close()
            if not record: self.error(404,"Raport inexistent.");return
            result=dict(record);result["payload"]=json.loads(result["payload"])
            self.respond(200,json.dumps(result,ensure_ascii=False).encode(),"application/json; charset=utf-8");return
        if pathname == "/":pathname="/index.html"
        if pathname.startswith("/api/"):
            self.error(404,"Resursa nu există.");return
        target=(WEB/pathname.lstrip("/")).resolve()
        if not target.is_relative_to(WEB) or target.suffix not in MIME or not target.is_file():
            self.error(404,"Resursa nu există.");return
        self.respond(200,target.read_bytes(),MIME[target.suffix]+("; charset=utf-8" if target.suffix in (".html",".css",".js") else ""))

    def do_POST(self):
        parts=urlsplit(self.path);path=parts.path
        if path not in ("/api/login","/api/compute","/api/reports","/api/render","/api/plan/import"):
            self.error(404,"Resursa nu există.");return
        origin=self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.error(403,"Origine neautorizată.");return
        if path!="/api/login" and not self.authorize(mutation=True):return
        if self.headers.get("Content-Type","").split(";")[0].strip().lower() != "application/json":
            self.error(415,"Este necesar application/json.");return
        length=self.headers.get("Content-Length","")
        limit=8_000_200 if path=="/api/plan/import" else MAX_BYTES
        if not length.isdecimal() or int(length)>limit:
            self.error(413,"Raport prea mare.");return
        try:
            body=json.loads(self.rfile.read(int(length)))
            if path=="/api/plan/import":
                if not isinstance(body,dict) or set(body)!={"image"}:
                    raise PlanImportError("Imagine invalidă.")
                result=import_plan(body["image"])
                self.respond(200,json.dumps(result,ensure_ascii=False).encode(),"application/json; charset=utf-8");return
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
                saved=save_report(body)
                self.respond(201,json.dumps(saved).encode(),"application/json; charset=utf-8");return
            report=process_plan(body) if isinstance(body,dict) and body.get("mode")=="plan" else process(body)
        except (ValueError,UnicodeDecodeError) as exc:
            self.error(400,str(exc) if isinstance(exc,(InvalidReport,PlanImportError)) else "Raport invalid.");return
        if path=="/api/render":
            try: page=int(parse_qs(parts.query).get("page",[0])[0]);image=plan_image(report) if report["mode"]=="plan" else production_image(report,page)
            except (ValueError,KeyError): self.error(400,"Pagină invalidă.");return
            self.respond(200,image,"image/png")
        else:
            self.respond(200,json.dumps(serialize(report),ensure_ascii=False).encode(),"application/json; charset=utf-8")

    def log_message(self,format,*args):
        # Do not log production values or PDF contents.
        pass


if __name__=="__main__":
    host=os.environ.get("PLUP_HOST","127.0.0.1")
    port=int(os.environ.get("PORT","8000"))
    if host not in ("127.0.0.1","::1","localhost") and (len(PASSWORD)<16 or len(SESSION_SECRET)<32):
        raise SystemExit("For network hosting, set PLUP_PASSWORD (16+ characters) and PLUP_SESSION_SECRET (32+ characters).")
    print(f"PLUP server on http://{host}:{port}",flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
