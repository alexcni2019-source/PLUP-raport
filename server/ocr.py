"""Extract editable PLUP plan draft from a straight-on image of the plan table.

The image is decoded in memory, passed as PNG to Tesseract, and discarded.
OCR output is a draft: the browser must show it for correction before save.
"""
from __future__ import annotations

import base64
import binascii
import csv
from datetime import date
from io import BytesIO, StringIO
import os
import re
import subprocess
import threading
import time
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 6_000_000
Image.MAX_IMAGE_PIXELS = 20_000_000
OCR_SLOT = threading.BoundedSemaphore(1)
NUMERIC = ("planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods")
# Normalized cell boundaries from the supplied PLUP plan design.
COLS = (350,477,565,649,736,847,946,1056,1146,1245,1329,1430)


class ImportError(ValueError):
    pass


def command(image, *, digits=False, timeout=8):
    data = BytesIO()
    image.save(data,"PNG")
    args = ["tesseract","stdin","stdout","--psm","7" if digits else "6","-l","eng"]
    if digits:
        args += ["-c","tessedit_char_whitelist=0123456789.,"]
    else:
        args.insert(3,"tsv")
    try:
        completed = subprocess.run(args,input=data.getvalue(),capture_output=True,
                                   timeout=timeout,check=False,env={**os.environ,"OMP_THREAD_LIMIT":"1"})
    except (FileNotFoundError,subprocess.TimeoutExpired) as exc:
        raise ImportError("Citirea imaginii a durat prea mult. Încearcă o captură mai clară.") from exc
    if completed.returncode:
        raise ImportError("Nu am putut citi imaginea. Folosește o fotografie clară a tabelului.")
    return completed.stdout.decode("utf-8",errors="replace").strip()


def cell_number(image, x1, x2, center, height):
    w,h=image.size
    left=max(0,round(x1*w/1672)+2)
    right=min(w,round(x2*w/1672)-2)
    top=max(0,round(center-height*.46))
    bottom=min(h,round(center+height*.46))
    if right<=left or bottom<=top:return "",True
    tile=image.crop((left,top,right,bottom))
    tile=tile.resize((max(80,tile.width*3),max(42,tile.height*3)),Image.Resampling.LANCZOS)
    raw=command(tile,digits=True,timeout=3).replace(" ","").replace(",",".")
    # Never silently turn an ambiguous number into another amount.
    match=re.fullmatch(r"\d{1,7}(?:\.\d{1,4})?",raw)
    return (raw if match else ""), not bool(match)


def import_plan(encoded):
    if not isinstance(encoded,str) or len(encoded)>MAX_IMAGE_BYTES*4//3+100:
        raise ImportError("Imaginea depășește limita de 6 MB.")
    try:
        binary=base64.b64decode(encoded,validate=True)
        if len(binary)>MAX_IMAGE_BYTES:raise ImportError("Imaginea depășește limita de 6 MB.")
        source=Image.open(BytesIO(binary))
        if source.format not in ("PNG","JPEG","WEBP"):
            raise ImportError("Folosește o imagine JPG, PNG sau WebP.")
        if source.width*source.height>20_000_000:
            raise ImportError("Rezoluția imaginii depășește limita admisă.")
        source.verify()
        source=Image.open(BytesIO(binary))
        image=ImageOps.exif_transpose(source).convert("RGB")
        if image.width<900 or image.height<400:
            raise ImportError("Imaginea este prea mică pentru a citi tabelul.")
        if image.width>3000:
            image.thumbnail((3000,3000),Image.Resampling.LANCZOS)
    except (binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError,ValueError) as exc:
        if isinstance(exc,ImportError):raise
        raise ImportError("Fișierul nu este o imagine validă.") from exc
    if not OCR_SLOT.acquire(blocking=False):
        raise ImportError("Se procesează deja o imagine. Reîncearcă în câteva secunde.")
    try:
        return _extract(image)
    finally:
        OCR_SLOT.release()


def _extract(image):
    w,h=image.size
    started=time.monotonic()
    words=[]
    for token in csv.DictReader(StringIO(command(image,timeout=12)),delimiter="\t"):
        value=token.get("text","").strip()
        if not value:continue
        try:
            words.append({"text":value,"x":int(token["left"]),"y":int(token["top"]),
                          "width":int(token["width"]),"height":int(token["height"]),
                          "conf":float(token["conf"])})
        except (ValueError,KeyError):continue
    # Find actual client cells; headers and total bands cannot become product rows.
    clients=[t for t in words if .046*w<t["x"]<.109*w and .22*h<t["y"]<.71*h
             and re.search("[A-Za-zĂÂÎȘȚăâîșț]",t["text"])
             and t["text"].upper() not in ("CLIENT","TOTAL","AL","CU","INTRARI")]
    lines=[]
    for token in sorted(clients,key=lambda a:a["y"]):
        yy=token["y"]+token["height"]/2
        if lines and abs(yy-lines[-1])<max(9,h*.011):continue
        lines.append(yy)
    if not lines or len(lines)>25:
        raise ImportError("Nu pot identifica rândurile produselor. Încarcă o imagine frontală, clară, cu tabelul complet.")
    distances=[b-a for a,b in zip(lines,lines[1:]) if b-a>9]
    row_height=sorted(distances)[len(distances)//2] if distances else h*.039
    if not .023*h<row_height<.075*h:
        raise ImportError("Rândurile nu pot fi separate. Fotografiază tabelul drept, fără perspectivă.")
    # Only the supplied plan layout has this column order. Require the header.
    header=" ".join(t["text"].upper() for t in words if .11*h<t["y"]<.24*h)
    if "PRODUS" not in header and "CLIENT" not in header:
        raise ImportError("Imaginea nu pare să conțină tabelul PLUP de plan. Verifică antetul CLIENT / PRODUS.")
    cu_y=next((t["y"] for t in words if t["x"]<.055*w and .55*h<t["y"]<.83*h
               and re.fullmatch("CU:?",t["text"],re.I)),None)
    rows=[]
    review=[]
    for center in lines:
        band=[t for t in words if abs(t["y"]+t["height"]/2-center)<row_height*.45]
        if any(t["text"].upper()=="TOTAL" for t in band if t["x"]<.15*w):
            continue
        index=len(rows)
        value=lambda lo,hi:" ".join(t["text"] for t in sorted(band,key=lambda q:q["x"])
                            if lo*w<t["x"]<hi*w).strip(" _—'‘|")[:120]
        client=value(.06,.105)
        product=value(.11,.208)
        notes=value(.854,.99)
        material="CU" if cu_y is not None and center>cu_y else "AL"
        item={"material":material,"client":client,"product":product,"notes":notes}
        if not client:review.append({"row":index,"field":"client"})
        if not product:review.append({"row":index,"field":"product"})
        for j,key in enumerate(NUMERIC):
            in_cell=[t for t in band if (COLS[j]+3)*w/1672<t["x"]<(COLS[j+1]-2)*w/1672]
            if any(re.search(r"[A-Za-zĂÂÎȘȚăâîșț]{2}",t["text"]) for t in in_cell):
                item[key]=""
                review.append({"row":index,"field":key})
                continue
            if time.monotonic()-started>40:
                item[key]=""
                review.append({"row":index,"field":key})
                continue
            result,uncertain=cell_number(image,COLS[j],COLS[j+1],center,row_height)
            if not result:
                fallback=[t for t in in_cell if re.fullmatch(r"\d{1,7}(?:[.,]\d{1,4})?",t["text"])]
                if len(fallback)==1 and fallback[0]["conf"]>=65:
                    result=fallback[0]["text"].replace(",",".")
                    uncertain=True
            item[key]=result
            if uncertain:review.append({"row":index,"field":key})
        rows.append(item)
    if not rows:raise ImportError("Nu au fost găsite produse în tabel.")
    full_text=" ".join(t["text"] for t in sorted(words,key=lambda q:(q["y"],q["x"])))
    match=re.search(r"(\d{2})[.\-/](\d{2})[.\-/](20\d{2})",full_text)
    date_value=""
    if match:
        try:date_value=date(int(match[3]),int(match[2]),int(match[1])).isoformat()
        except ValueError:pass
    week_match=re.search(r"\b[Ww]\s?(\d{1,2})\b",full_text)
    incoming=""
    for t in words:
        if t["y"]>.84*h and .23*w<t["x"]<.32*w and re.fullmatch(r"\d+(?:[.,]\d+)?",t["text"]):
            incoming=t["text"].replace(",",".")
            break
    return {"rows":rows,"date":date_value,"week":"W"+week_match[1] if week_match else "",
            "incoming":incoming,"review":review,
            "message":"Verifică fiecare valoare înainte de salvare. Celulele marcate nu au putut fi citite sigur."}
