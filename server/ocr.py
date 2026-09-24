"""Extract editable PLUP plan draft from a straight-on image of the plan table.

The image is decoded in memory, passed as PNG to Tesseract, and discarded.
OCR output is a draft: the browser must show it for correction before save.
"""
from __future__ import annotations

import base64
import binascii
import csv
from datetime import date
from decimal import Decimal
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


def read_cell(image, box, *, numeric=False, nearest=False):
    x1,y1,x2,y2=box
    side=max(2,round(image.width/(320 if numeric else 400)))
    tile=image.crop((x1+side,y1+max(2,round(image.width/530)),
                     x2-side,y2-max(1,round(image.width/800))))
    if tile.width<5 or tile.height<4:return ""
    tile=ImageOps.grayscale(tile)
    if numeric:
        ink=tile.point(lambda color:255 if color<170 else 0).getbbox()
        if ink:
            pad=max(2,round(image.width/400))
            tile=tile.crop((max(0,ink[0]-pad),max(0,ink[1]-2),
                            min(tile.width,ink[2]+pad),min(tile.height,ink[3]+2)))
    tile=ImageOps.expand(ImageOps.autocontrast(tile),border=10 if numeric else 12,fill="white")
    factor=4 if numeric else 3
    tile=tile.resize((tile.width*factor,tile.height*factor),
                     Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS)
    data=BytesIO();tile.save(data,"PNG")
    args=["tesseract","stdin","stdout","--psm","7","-l","eng"]
    if numeric:args+=["-c","tessedit_char_whitelist=0123456789.,"]
    try:
        result=subprocess.run(args,input=data.getvalue(),capture_output=True,timeout=3,
                              env={**os.environ,"OMP_THREAD_LIMIT":"1"})
    except (FileNotFoundError,subprocess.TimeoutExpired) as exc:
        raise ImportError("Citirea imaginii a durat prea mult.") from exc
    if result.returncode:return ""
    return result.stdout.decode("utf-8",errors="replace").strip()


def _extract_compact(image):
    """Read the small Excel capture by its visible row and column grid."""
    w,h=image.size
    scale=w/1600
    if not (2.9<w/h<7.5):raise ImportError("Captura tabelului Excel trebuie să fie completă și orizontală.")
    x=lambda n:round(n*scale)
    bounds=[47,189,354,490,608,688,775,859,946,1041,1123,1201,1277,1385,1600]
    if h<round(175*scale):raise ImportError("Captura este prea mică pentru citirea rândurilor.")
    # Total AL is cyan and total CU green; their positions change with row count.
    sample_x=x(700)
    blue=[];green=[]
    for y in range(round(55*scale),h-round(16*scale)):
        r,g,b=image.getpixel((sample_x,y))
        if b>r+75 and b>g+25 and g>95:blue.append(y)
        if g>r+55 and g>b+28 and 95<g<245:green.append(y)
    def runs(points):
        grouped=[]
        for pos in points:
            if not grouped or pos>grouped[-1][-1]+1:grouped.append([pos])
            else:grouped[-1].append(pos)
        return [(q[0],q[-1]+1) for q in grouped if len(q)>=max(3,round(5*scale))]
    cyan=runs(blue)
    greens=runs(green)
    if len(cyan)!=1 or not greens:
        raise ImportError("Nu găsesc benzile albastre și verzi ale totalurilor. Include tot tabelul în captură.")
    al_start,al_end=cyan[0]
    cu_start,cu_end=next(((a,b) for a,b in greens if a>al_end+round(12*scale)),(0,0))
    if not cu_start:raise ImportError("Nu găsesc secțiunea CU în imagine.")
    # Full-width grey grid rules, excluding colored total bands.
    rules=[]
    for y in range(round(28*scale),cu_start):
        samples=[image.getpixel((xx,y)) for xx in range(x(50),min(w-1,x(1570)),max(2,round(8*scale)))]
        ratio=sum(max(c)-min(c)<12 and sum(c)/3<208 for c in samples)/max(1,len(samples))
        if ratio>.70:rules.append(y)
    rule_groups=[]
    for y in rules:
        if not rule_groups or y>rule_groups[-1][-1]+1:rule_groups.append([y])
        else:rule_groups[-1].append(y)
    lines=[round(sum(group)/len(group)) for group in rule_groups]
    header_end=min(lines,key=lambda y:abs(y-x(44))) if lines else x(44)
    if abs(header_end-x(44))>round(5*scale):
        raise ImportError("Nu pot localiza antetul tabelului.")
    def bands(first,last):
        points=[first]+[yy for yy in lines if first+round(5*scale)<yy<last-round(5*scale)]+[last]
        result=list(zip(points,points[1:]))
        if any(not round(11*scale)<=b-a<=round(19*scale) for a,b in result):
            raise ImportError("Grila de rânduri este neclară; folosește o captură la rezoluția originală.")
        return result
    al_bands=bands(header_end,al_start)
    cu_bands=bands(al_end+max(0,round(scale)),cu_start)
    if not 1<=len(al_bands)+len(cu_bands)<=60:
        raise ImportError("Nu pot identifica produsele din tabel.")
    header=read_cell(image,(x(47),x(29),x(355),x(44)))
    if "CLIENT" not in header.upper() and "PRODUS" not in header.upper():
        raise ImportError("Antetul CLIENT / PRODUS nu poate fi citit.")
    title=read_cell(image,(x(47),0,x(190),min(h,x(17))))
    found=re.search(r"(\d{2})[.\-/](\d{2})[.\-/](20\d{2})",title)
    plan_date=""
    if found:
        try:plan_date=date(int(found[3]),int(found[2]),int(found[1])).isoformat()
        except ValueError:pass
    week_match=re.search(r"\b[wW]\s?(\d{1,2})",title)
    reviews=[];rows=[];started=time.monotonic()
    for material,group in (("AL",al_bands),("CU",cu_bands)):
        for y1,y2 in group:
            index=len(rows)
            client=read_cell(image,(x(47),y1,x(189),y2)).strip(" |")
            product=read_cell(image,(x(189),y1,x(354),y2)).strip(" |")
            notes=read_cell(image,(x(1385),y1,w,y2)).strip(" |")
            row={"material":material,"client":client[:120],"product":product[:120],"notes":notes[:120]}
            for field in ("client","product"):
                if not row[field]:reviews.append({"row":index,"field":field})
            for col,key in enumerate(NUMERIC):
                if time.monotonic()-started>44:
                    row[key]="";reviews.append({"row":index,"field":key});continue
                left,right=bounds[col+2],bounds[col+3]
                box=(x(left),y1,x(right),y2)
                first=read_cell(image,box,numeric=True,nearest=True).replace(",",".").replace(" ","")
                valid=lambda s:bool(re.fullmatch(r"\d{1,7}(?:\.\d{1,4})?",s))
                second=""
                # A second rendering resolves missing dots and uncertain digits.
                if first!="0":
                    second=read_cell(image,box,numeric=True).replace(",",".").replace(" ","")
                if valid(first) and valid(second) and first==second:
                    result=first;uncertain=False
                elif valid(first) and (not second or not valid(second)):
                    result=first;uncertain=True
                elif valid(second) and (not first or not valid(first)):
                    result=second;uncertain=second!="0"
                elif valid(first) and valid(second):
                    result=first if "." in first and "." not in second else second
                    uncertain=True
                else:result="";uncertain=True
                row[key]=result
                if uncertain or result not in ("", "0"):reviews.append({"row":index,"field":key})
            rows.append(row)
    # Compare with printed subtotals: a disagreeing column requires review,
    # never silent correction of individual OCR values.
    warnings=[]
    for material,top,bottom in (("AL",al_start,al_end),("CU",cu_start,cu_end)):
        for key,left,right in (("planned",354,490),("handed",490,608)):
            printed=read_cell(image,(x(left),top,x(right),bottom),numeric=True).replace(",",".")
            if not re.fullmatch(r"\d+(?:\.\d{1,4})?",printed):
                warnings.append(f"Totalul {material} {key} nu a putut fi verificat.")
                continue
            calculated=sum((Decimal(row[key] or "0") for row in rows if row["material"]==material),Decimal("0"))
            if abs(calculated-Decimal(printed))>Decimal(".06"):
                warnings.append(f"Totalul {material} {'planificat' if key=='planned' else 'predat'} nu corespunde: imagine {printed}, extras {calculated}.")
                reviews.extend({"row":i,"field":key} for i,row in enumerate(rows) if row["material"]==material)
    # The grand total is intentionally ignored; use the incoming metal row only.
    incoming_y1=cu_end+round(15*scale)
    incoming=read_cell(image,(x(355),incoming_y1,x(490),min(h,incoming_y1+round(15*scale))),numeric=True,nearest=True)
    incoming=incoming.replace(",",".") if re.fullmatch(r"\d+(?:[.,]\d{1,4})?",incoming) else ""
    return {"rows":rows,"date":plan_date,"week":"W"+week_match[1] if week_match else "",
            "incoming":incoming,"review":reviews,
            "message":" ".join(warnings) or "Verifică toate valorile, mai ales cifrele și zecimalele, înainte de salvare."}


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
        if image.width<900 or image.height<170:
            raise ImportError("Imaginea este prea mică pentru a citi tabelul.")
        if image.width>3000:
            image.thumbnail((3000,3000),Image.Resampling.LANCZOS)
    except (binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError,ValueError) as exc:
        if isinstance(exc,ImportError):raise
        raise ImportError("Fișierul nu este o imagine validă.") from exc
    if not OCR_SLOT.acquire(blocking=False):
        raise ImportError("Se procesează deja o imagine. Reîncearcă în câteva secunde.")
    try:
        return _extract_compact(image) if image.width/image.height>2.9 else _extract(image)
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
