"""PNG export using sanitized reference artwork and live report values."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
WHITE = "#f7fbff"


def font(size, bold=False):
    return ImageFont.truetype(str(ROOT / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def text(draw, xy, value, size=16, color=WHITE, bold=False, anchor=None, width=None):
    value = str(value)
    if width:
        while draw.textlength(value, font=font(size, bold)) > width and len(value) > 1:
            value = value[:-2] + "…"
    draw.text(xy, value, font=font(size, bold), fill=color, anchor=anchor)


def amount(value, places=2):
    value = Decimal(str(value))
    return f"{value:.{places}f}".rstrip("0").rstrip(".") if places else f"{value:.0f}"


def png(image):
    out = BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def gradient(image, box, start, end):
    x1, y1, x2, y2 = box
    a = tuple(bytes.fromhex(start.lstrip("#")))
    b = tuple(bytes.fromhex(end.lstrip("#")))
    d = ImageDraw.Draw(image)
    for y in range(y1, y2):
        t = (y-y1) / max(1, y2-y1)
        d.line((x1, y, x2, y), fill=tuple(round(v*(1-t)+w*t) for v, w in zip(a,b)))


KEYS = ["planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods"]
HEADERS = ["CLIENT","PRODUS","METAL\nPLANIFICAT\n(TONE)","METAL\nPREDAT\n(TONE)",
           "SARMA\n(TONE)","STOC LITA\n(TONE)","STOC FUNE /\nBARA (KM)",
           "STOC VANE\n(KM)","STOC CABLAT\n(KM)","STOC M.I.\n(KM)",
           "STOC ARMATI\n(KM)","STOC M.F.\n(KM)","MARFA\nPREDATA (KM)","OBSERVATII"]
X = [22,78,178,350,477,565,649,736,847,946,1056,1146,1245,1329,1430,1649]


def plan_image(plan):
    al = [r for r in plan["rows"] if r["material"] == "AL"]
    cu = [r for r in plan["rows"] if r["material"] == "CU"]
    row_h = 37 if len(al)+len(cu) <= 18 else 32
    bottom = 218+row_h*(len(al)+len(cu))+47+14+38+44+49+49
    h = max(941, bottom+75)
    image = Image.new("RGB", (1672,h), "#0b1d29")
    gradient(image, (0,0,1672,h), "#0a1c27", "#102536")
    with Image.open(ASSETS/"plan_header.jpg") as header:
        image.paste(header, (0,0))
    d = ImageDraw.Draw(image)
    display = date.fromisoformat(plan["date"]).strftime("%d.%m.%Y")
    text(d, (386,46), f"{display} – plan {plan['week']}", 36, bold=True, width=485)
    d.rounded_rectangle((11,122,1660,h-59),radius=15,fill="#0b1c28",outline="#466474")
    d.rounded_rectangle((22,139,1649,h-75),radius=9,fill="#122635",outline="#466474")
    gradient(image, (22,139,1650,218), "#1c3344", "#132a3a")
    d = ImageDraw.Draw(image)
    for j, head in enumerate(HEADERS):
        lines = head.split("\n")
        for k, line in enumerate(lines):
            text(d, ((X[j+1]+X[j+2])/2,177+(k-(len(lines)-1)/2)*18),line,12,
                 bold=True,anchor="mm",width=X[j+2]-X[j+1]-5)
    y = 218
    def row(r, material, index):
        nonlocal y
        d = ImageDraw.Draw(image)
        d.rectangle((22,y,1649,y+row_h),fill="#1b303d" if index%2 else "#102432")
        d.line((22,y+row_h,1649,y+row_h),fill="#355061")
        if index == 0:
            d.rectangle((22,y,78,y+row_h),fill="#075b80" if material=="AL" else "#086544")
            text(d,(36,y+row_h/2),material+":",16,bold=True,anchor="lm")
        vals = [r["client"],r["product"]]+[amount(r[k]) for k in KEYS]+[r["notes"]]
        for i,val in enumerate(vals):
            left,right = X[i+1],X[i+2]
            if i in (0,1,13):
                text(d,(left+8,y+row_h/2),val,11 if i==13 else 13,anchor="lm",width=right-left-10)
            else:
                text(d,((left+right)/2,y+row_h/2),val,14,anchor="mm",width=right-left-7)
        y += row_h
    def band(label,height,start,end,accent,totals=None):
        nonlocal y
        gradient(image,(22,y,1650,y+height),start,end)
        d = ImageDraw.Draw(image)
        d.line((22,y,1649,y),fill=accent,width=2)
        text(d,(79,y+height/2),label,16,bold=True,anchor="lm",width=262)
        if totals:
            for key,index in (("planned",3),("handed",4),("wire",5)):
                text(d,((X[index]+X[index+1])/2,y+height/2),amount(totals[key]),16,bold=True,anchor="mm")
        y += height
    for i,r in enumerate(al): row(r,"AL",i)
    band("TOTAL AL (TONE) :",47,"#064767","#0d3247","#00b7f5",plan["totals"]["AL"])
    y += 14
    d=ImageDraw.Draw(image)
    d.rectangle((22,y,78,y+38),fill="#086544",outline="#23ac77")
    text(d,(36,y+19),"CU:",16,bold=True,anchor="lm")
    y += 38
    for i,r in enumerate(cu): row(r,"CU",i)
    a,c=plan["totals"]["AL"],plan["totals"]["CU"]
    band("TOTAL CU (TONE )",44,"#0b503a","#103c32","#13b771",c)
    band("TOTAL GENERAL (TONE )",49,"#63531b","#3c3519","#ffd21c",
         {k:a[k]+c[k] for k in ("planned","handed","wire")})
    gradient(image,(22,y,1650,y+49),"#142d40","#1b3447")
    d=ImageDraw.Draw(image)
    text(d,(79,y+24),"INTRARI METAL",16,bold=True,anchor="lm")
    text(d,((X[3]+X[4])/2,y+24),amount(plan["incoming"]),16,bold=True,anchor="mm")
    y += 49
    for x in X[1:]: d.line((x,139,x,y),fill="#365469")
    d.line((22,217,1649,217),fill="#49718a")
    return png(image)


OPS = ["op_asumreal","op_status","op_plan","op_previz","op_backal","op_backcu",
       "op_rigid1","op_rigid2","op_rigid3","op_multi1","op_multi2","op_niehoff",
       "op_beta3","op_stocal","op_stoccu"]


def production_image(report,page=0):
    days=report["days"]
    total=len(days)>1 and page==len(days)
    if page<0 or (page>len(days) if len(days)>1 else page!=0): raise ValueError("Pagină invalidă")
    r=report["total"] if total else days[page]
    vals={k:sum(day["values"][k] for day in days) if total else r["values"][k]
          for k in ("al","cu","backlogAl","backlogCu","wasteAl","wasteCu")}
    extras={} if total else r["extras"]
    start=date.fromisoformat(days[0]["date"]).strftime("%d.%m.%Y")
    end=date.fromisoformat(days[-1]["date"]).strftime("%d.%m.%Y")
    date_line=f"{start} – {end}" if total else date.fromisoformat(r["date"]).strftime("%d.%m.%Y")
    image=Image.new("RGB",(1491,1055),"#071b2a")
    gradient(image,(0,0,1491,1055),"#0d304c","#071725")
    d=ImageDraw.Draw(image)
    for n in range(8):
        d.line((490+n*90,0,380+n*90,106),fill="#114366",width=5)
    with Image.open(ASSETS/"plan_header.jpg") as logo:
        image.paste(logo.crop((34,17,292,101)).resize((215,70)),(34,18))
    d=ImageDraw.Draw(image)
    d.line((240,23,240,87),fill="#ecfaff",width=2)
    text(d,(272,18),"PLUP",36,bold=True)
    text(d,(273,62),"D E P A R T M E N T",17)

    def panel(box,top,bottom,outline="#3b779d",radius=12):
        x1,y1,x2,y2=box
        layer=Image.new("RGB",(x2-x1+1,y2-y1+1))
        gradient(layer,(0,0,layer.width,layer.height),top,bottom)
        mask=Image.new("L",layer.size,0)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,layer.width-1,layer.height-1),radius=radius,fill=255)
        image.paste(layer,(x1,y1),mask)
        ImageDraw.Draw(image).rounded_rectangle(box,radius=radius,outline=outline,width=1)

    panel((19,106,1473,284),"#113e62","#092b45","#5fa0d0")
    with Image.open(ASSETS/"cables_hero.jpg") as source:
        hero=source.resize((765,181),Image.Resampling.LANCZOS)
    fade=Image.new("L",hero.size)
    fd=ImageDraw.Draw(fade)
    for x in range(hero.width):
        strength=min(1,x/125,(hero.width-x)/35)
        fd.line((x,0,x,180),fill=round(255*max(0,strength)))
    image.paste(hero,(546,106),fade)
    d=ImageDraw.Draw(image)
    d.rounded_rectangle((63,141,166,244),radius=27,fill="#174260",outline="#6cb8e8",width=2)
    d.rectangle((92,164,135,221),outline=WHITE,width=4)
    for yy in (182,193,205):d.line((101,yy,126,yy),fill=WHITE,width=3)
    d.line((196,143,196,243),fill="#b5e3f2",width=2)
    text(d,(226,136),"Raport",55,bold=True)
    text(d,(230,209),date_line,27,width=390)

    # The cards use the same positions, typography, colors and cable motif as
    # the reference; all figures come exclusively from the validated payload.
    for x,code,title,value,back,color,top,bottom in [
        (19,"Al","Aluminiu",vals["al"],vals["backlogAl"],"#52baff","#0e4163","#10334e"),
        (440,"Cu","Cupru",vals["cu"],vals["backlogCu"],"#ff9650","#493b37","#162a3c")]:
        panel((x,297,x+408,496),top,bottom,color)
        d=ImageDraw.Draw(image)
        for i in range(11):
            d.line((x+275+i*16,373-i*5,x+408,303+i*3),fill="#225b79" if code=="Al" else "#744c3d",width=2)
        d.ellipse((x+22,314,x+92,384),fill="#147ecc" if code=="Al" else "#ff7627",outline=color,width=2)
        text(d,(x+57,348),code,31,bold=True,anchor="mm")
        text(d,(x+114,331),title,28,bold=True)
        d.line((x+209,397,x+209,472),fill="#9bbdcb",width=1)
        text(d,(x+92,406),"Predat",18,anchor="mm")
        text(d,(x+300,406),"Backlog",18,anchor="mm")
        text(d,(x+89,435),amount(value,1)+" t",33,bold=True,anchor="mt",width=175)
        text(d,(x+297,435),amount(back,1)+" t",33,color,True,anchor="mt",width=178)
    panel((19,509,848,627),"#07604a","#064a43","#16bd70")
    d=ImageDraw.Draw(image)
    d.line((434,525,434,612),fill=WHITE,width=2)
    for cx,symbol,label,value in [(97,"▮","Total predat AL + CU",r["handed"]),
                                   (530,"□","Backlog predat",r["backlog"])]:
        d.ellipse((cx-43,525,cx+43,611),outline="#28c881",width=2)
        text(d,(cx,566),symbol,43,bold=True,anchor="mm")
        text(d,(cx+75,532),label,20,bold=True,width=275)
        text(d,(cx+75,563),amount(value,1)+" t",46,bold=True,width=270)
    panel((19,639,848,869),"#113c58","#0b2942","#347aab")
    d=ImageDraw.Draw(image)
    text(d,(44,651),"♻",42,"#6df3ad",True)
    text(d,(114,661),"Deșeu",27,bold=True)
    d.line((296,679,296,851),fill="#92b1c1")
    d.line((679,679,679,851),fill="#92b1c1")
    for y,code,label,value,color in [
        (728,"Al","Aluminiu",vals["wasteAl"],"#177fd2"),
        (775,"Cu","Cupru",vals["wasteCu"],"#ff7728"),
        (829,"♻","Total deșeu",r["waste"],"#425b70")]:
        d.ellipse((47,y-16,88,y+25),fill=color)
        text(d,(67,y+4),code,19,bold=True,anchor="mm")
        text(d,(106,y+5),label,16,anchor="lm")
        text(d,(225,y+5),amount(value,1)+" t",17,bold=True,anchor="lm")
    d.line((47,811,264,811),fill="#739db2")
    d.ellipse((318,682,483,849),fill="#708fa6")
    d.ellipse((344,708,457,823),fill="#0a2c43")
    pct=min(100,max(0,float(r["percent"])))
    if pct:d.arc((319,683,482,848),-90,-90+max(2,round(pct*3.6)),fill="#5bf4a0",width=25)
    text(d,(400,751),amount(r["percent"],1)+"%",25,bold=True,anchor="mm")
    text(d,(400,780),"Procent deșeu",12,anchor="mm")
    for y,label,val,color in [(721,"Deșeu",r["waste"],"#5bf4a0"),
                               (789,"Material procesat",r["processed"],"#bcd8ef")]:
        d.ellipse((507,y-9,526,y+10),fill=color)
        text(d,(541,y),label,16,anchor="lm")
        text(d,(541,y+18),amount(val,1)+" t",18,anchor="lt")

    panel((862,297,1474,869),"#113b5a","#0b2e49","#3985b5")
    d=ImageDraw.Draw(image)
    text(d,(891,317),"▥",27,"#5aedac",True)
    text(d,(934,318),"Indicatori operaționali",21,bold=True)
    d.rounded_rectangle((1301,311,1456,347),radius=7,outline="#6eadd4",width=1)
    text(d,(1379,329),date_line,14,anchor="mm",width=143)
    d.rounded_rectangle((877,359,1459,800),radius=8,fill="#0d2b43",outline="#3979a3")
    d.rectangle((878,360,1458,390),fill="#14557e")
    text(d,(891,366),"Indicator",15,bold=True)
    text(d,(1270,366),"Valoare",15,bold=True)
    d.line((1125,360,1125,800),fill="#3f6177")
    labels=["Asumat / Realizat (t) + %","Realizat VS Status","Realizat vs Plan",
            "Previz sch 1","Backlog Aluminiu (t)","Backlog Cupru (t)",
            "SF așteptare – Rigid 1 (km)","SF așteptare – Rigid 2 (km)",
            "SF așteptare – Rigid 3 (km)","SF așteptare – Multifir 8 Cai 1 (t)",
            "SF așteptare – Multifir 8 Cai 2 (t)","SF așteptare – 16 Cai Niehoff (t)",
            "SF așteptare – 16 Cai Beta 3 (t)","Stoc Al","Stoc Cu"]
    for i,(label,key) in enumerate(zip(labels,OPS)):
        yy=391+i*27
        if i%2:d.rectangle((878,yy,1458,yy+27),fill="#153850")
        d.line((878,yy+27,1458,yy+27),fill="#3a5c71")
        text(d,(890,yy+13),label,13,anchor="lm",width=225)
        text(d,(1291,yy+13),extras.get(key,"") or "—",13,
             "#8ceab4" if i<3 else WHITE,i<3,anchor="mm",width=322)
    panel((19,882,978,989),"#104a70","#093a5e","#42aee6")
    d=ImageDraw.Draw(image)
    d.ellipse((58,901,132,975),outline="#46d5ff",width=2)
    text(d,(95,937),"⚙",37,bold=True,anchor="mm")
    text(d,(177,902),"Total procesat",18)
    text(d,(175,931),amount(r["processed"],1)+" t",39,bold=True)
    d.line((482,901,482,970),fill="#85b9d4")
    d.ellipse((589,901,663,975),outline="#46d5ff",width=2)
    text(d,(626,936),"%",43,bold=True,anchor="mm")
    text(d,(701,902),"Procent deșeu",18)
    text(d,(702,931),amount(r["percent"],1)+"%",39,bold=True)
    text(d,(42,1014),"N R G  C A B L E S    │    P L U P  D E P A R T M E N T",12)
    return png(image)
