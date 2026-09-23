"""Server-side PNG renderers for PLUP reports. No input is treated as markup."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

FONT_DIR=Path(__file__).resolve().parent
if not (FONT_DIR/"DejaVuSans.ttf").exists():
    FONT_DIR=Path("/usr/share/fonts/truetype/dejavu")
NAVY="#071a29"; PANEL="#102b41"; LINE="#2c5a70"; TEXT="#f2f7f9"
MUTED="#a6c1d0"; BLUE="#34a9ee"; GREEN="#36d792"; ORANGE="#ff9348"

def font(size,bold=False):
    return ImageFont.truetype(str(FONT_DIR/("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")),size)

def amount(value,digits=1):
    s=f"{value:,.{digits}f}".replace(",","§").replace(".",",").replace("§",".")
    return s.rstrip("0").rstrip(",") if digits else s

def rect(d,box,fill,outline=None,radius=0,width=1):
    d.rounded_rectangle(box,radius=radius,fill=fill,outline=outline,width=width)

def txt(d,xy,value,size=16,color=TEXT,bold=False,anchor=None,max_width=None):
    value=str(value)
    if max_width:
        while d.textlength(value,font=font(size,bold))>max_width and len(value)>3:value=value[:-2]+"…"
    d.text(xy,value,font=font(size,bold),fill=color,anchor=anchor)

def gradient(image,box,top,bottom):
    x1,y1,x2,y2=box
    a=tuple(bytes.fromhex(top.lstrip('#')));b=tuple(bytes.fromhex(bottom.lstrip('#')))
    dr=ImageDraw.Draw(image)
    for y in range(y1,y2):
        t=(y-y1)/max(1,y2-y1-1)
        dr.line((x1,y,x2,y),fill=tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3)))

def png(image):
    out=BytesIO();image.save(out,"PNG",optimize=True);return out.getvalue()

def base(w,h):
    im=Image.new("RGB",(w,h),NAVY);d=ImageDraw.Draw(im)
    gradient(im,(0,0,w,h),"#102a3e","#05121f")
    for k in range(8):d.line((w-440+k*70,-30,520+k*70,h),fill="#173d53",width=2)
    return im,ImageDraw.Draw(im)

def brand(d,w,date_line):
    txt(d,(42,25),"NRG",43,TEXT,True)
    txt(d,(163,42),"Cables",27,TEXT)
    d.line((43,81,271,81),fill=BLUE,width=3)
    txt(d,(43,86),"P L U P   D E P A R T A M E N T",12,"#9cc6d5",True)
    d.line((305,22,305,100),fill="#76a2b4",width=2)
    txt(d,(337,35),date_line,30,TEXT,True,max_width=w-380)

PLAN_KEYS=["planned","handed","wire","spool","bar","vane","cable","mi","armored","mf","goods"]
PLAN_HEADERS=["CLIENT","PRODUS","METAL\nPLANIFICAT\n(t)","METAL\nPREDAT\n(t)","SÂRMĂ\n(t)","STOC LITĂ\n(t)","FUNE /\nBARĂ (km)","VANE\n(km)","CABLAT\n(km)","M.I.\n(km)","ARMAT\n(km)","M.F.\n(km)","MARFĂ\n(km)","OBSERVAȚII"]
PLAN_WIDTHS=[100,170,118,90,85,85,112,100,110,85,85,85,100,218]

def plan_image(plan):
    al=[r for r in plan["rows"] if r["material"]=="AL"]
    cu=[r for r in plan["rows"] if r["material"]=="CU"]
    count=len(al)+len(cu)
    row_h=39 if count<=22 else 30
    h=max(740,234+(count+6)*row_h+30)
    w=1680;im,d=base(w,h)
    display=date.fromisoformat(plan["date"]).strftime("%d.%m.%Y")
    brand(d,w,f"{display} – plan {plan['week']}")
    x0=23;y0=138
    rect(d,(x0,y0,w-23,h-24),"#0d2637",LINE,13)
    xs=[x0+56]
    for width in PLAN_WIDTHS:xs.append(xs[-1]+width)
    xs[-1]=w-24
    header_h=78
    gradient(im,(x0+1,y0+1,w-24,y0+header_h),"#1b394e","#142d40")
    d=ImageDraw.Draw(im)
    for j,head in enumerate(PLAN_HEADERS):
        cx=(xs[j]+xs[j+1])/2
        lines=head.split('\n')
        for k,line in enumerate(lines):txt(d,(cx,y0+22+k*17),line,12,TEXT,True,anchor="mm",max_width=xs[j+1]-xs[j]-8)
    y=y0+header_h
    def row(r,material,index):
        nonlocal y
        if index%2:rect(d,(x0+1,y,w-24,y+row_h),"#192f3f")
        else:rect(d,(x0+1,y,w-24,y+row_h),"#102634")
        if index==0:rect(d,(x0+1,y,xs[0],y+row_h),"#075070" if material=="AL" else "#0c6247")
        if index==0:txt(d,(x0+13,y+row_h/2),material+":",16,TEXT,True,anchor="lm")
        vals=[r["client"],r["product"]]+[amount(r[key],2) for key in PLAN_KEYS]+[r["notes"]]
        for j,value in enumerate(vals):
            cell_left=xs[j];cell_right=xs[j+1]
            if j in (0,1,13):txt(d,(cell_left+9,y+row_h/2),value,13,TEXT,anchor="lm",max_width=cell_right-cell_left-16)
            else:txt(d,((cell_left+cell_right)/2,y+row_h/2),value,14,TEXT,anchor="mm",max_width=cell_right-cell_left-10)
        y+=row_h
    def total(material,label,top,bottom):
        nonlocal y
        gradient(im,(x0+1,y,w-24,y+row_h+7),top,bottom)
        nonlocal_d=ImageDraw.Draw(im)
        nonlocal_d.line((x0+1,y,w-24,y),fill=BLUE if material=="AL" else GREEN,width=2)
        txt(nonlocal_d,(x0+56,y+(row_h+7)/2),label,15,TEXT,True,anchor="lm")
        vals=plan["totals"].get(material,{})
        for key,j in [('planned',2),('handed',3),('wire',4)]:
            txt(nonlocal_d,((xs[j]+xs[j+1])/2,y+(row_h+7)/2),amount(vals[key],2),15,TEXT,True,anchor="mm")
        y+=row_h+7
    for i,r in enumerate(al):row(r,"AL",i)
    total("AL","TOTAL AL (TONE)","#084c68","#0a3048")
    y+=12
    for i,r in enumerate(cu):row(r,"CU",i)
    total("CU","TOTAL CU (TONE)","#0a513c","#0b332d")
    gradient(im,(x0+1,y,w-24,y+row_h+7),"#675817","#3e3516");d=ImageDraw.Draw(im)
    d.line((x0+1,y,w-24,y),fill="#d9b535",width=2)
    txt(d,(x0+56,y+22),"TOTAL GENERAL (TONE)",15,TEXT,True,anchor="lm")
    for key,j in [('planned',2),('handed',3),('wire',4)]:
        val=plan["totals"]["AL"][key]+plan["totals"]["CU"][key]
        txt(d,((xs[j]+xs[j+1])/2,y+22),amount(val,2),15,TEXT,True,anchor="mm")
    y+=row_h+7
    rect(d,(x0+1,y,w-24,y+row_h+7),"#173142")
    txt(d,(x0+56,y+22),"INTRĂRI METAL",15,TEXT,True,anchor="lm")
    txt(d,((xs[2]+xs[3])/2,y+22),amount(plan["incoming"],2),15,TEXT,True,anchor="mm")
    y+=row_h+7
    d=ImageDraw.Draw(im)
    for x in [x0,*xs]:d.line((x,y0,x,y),fill="#365d6d",width=1)
    d.line((w-24,y0,w-24,y),fill="#365d6d",width=1)
    return png(im)

OPS=[("Asumat / Realizat","op_asumreal"),("Realizat vs. status","op_status"),("Realizat vs. plan","op_plan"),("Previzionat schimbul 1","op_previz"),("Backlog aluminiu","op_backal"),("Backlog cupru","op_backcu"),("SF așteptare – Rigid 1","op_rigid1"),("SF așteptare – Rigid 2","op_rigid2"),("SF așteptare – Rigid 3","op_rigid3"),("SF așteptare – Multifir 8 căi 1","op_multi1"),("SF așteptare – Multifir 8 căi 2","op_multi2"),("SF așteptare – 16 căi Niehoff","op_niehoff"),("SF așteptare – 16 căi Beta 3","op_beta3"),("Stoc aluminiu","op_stocal"),("Stoc cupru","op_stoccu")]

def production_image(report,page=0):
    days=report["days"]
    is_total=len(days)>1 and page==len(days)
    if page<0 or page>len(days) if len(days)>1 else page!=0:raise ValueError("Pagină invalidă")
    r=report["total"] if is_total else days[page]
    extras={} if is_total else days[page]["extras"]
    al=sum(day["values"]["al"] for day in days) if is_total else r["values"]["al"]
    cu=sum(day["values"]["cu"] for day in days) if is_total else r["values"]["cu"]
    bal=sum(day["values"]["backlogAl"] for day in days) if is_total else r["values"]["backlogAl"]
    bcu=sum(day["values"]["backlogCu"] for day in days) if is_total else r["values"]["backlogCu"]
    wal=sum(day["values"]["wasteAl"] for day in days) if is_total else r["values"]["wasteAl"]
    wcu=sum(day["values"]["wasteCu"] for day in days) if is_total else r["values"]["wasteCu"]
    date_line=(f"TOTAL WEEKEND · {days[0]['date']} – {days[-1]['date']}" if is_total else date.fromisoformat(r["date"]).strftime("%d.%m.%Y"))
    w,h=1500,1000;im,d=base(w,h);brand(d,w,"PLUP · RAPORT DE PRODUCȚIE")
    rect(d,(20,123,1480,288),"#0c304c",BLUE,15)
    gradient(im,(23,126,1477,284),"#134a72","#081d31");d=ImageDraw.Draw(im)
    # Metallic aluminum and copper strands, drawn from geometry rather than a stock image.
    for group,color in [(0,(155,205,230)),(1,(208,119,72))]:
        for i in range(35):
            ox=850+i*12+group*180;oy=260-i*3
            shade=0.55+0.45*math.sin(i*1.6)**2
            c=tuple(int(v*shade) for v in color)
            d.line((ox,oy,ox+250,oy-115),fill=c,width=2+(i%3))
    txt(d,(63,157),"▤",56,"#a7dcf1")
    d.line((150,155,150,251),fill="#9bc9d7",width=2)
    txt(d,(183,159),"Raport" if not is_total else "Total weekend",51,TEXT,True)
    txt(d,(186,234),date_line,23,"#d6eaf0",max_width=600)
    # Main material cards.
    for x,name,code,main,back,color,fill in [(20,"Aluminiu","Al",al,bal,BLUE,"#0e4266"),(436,"Cupru","Cu",cu,bcu,ORANGE,"#443322")]:
        rect(d,(x,306,x+400,495),fill,color,13)
        d.ellipse((x+23,327,x+86,390),fill=color)
        txt(d,(x+54,359),code,27,TEXT,True,anchor="mm")
        txt(d,(x+105,341),name,29,TEXT,True)
        txt(d,(x+28,420),"Predat",17,"#c3dbe5")
        txt(d,(x+28,446),amount(main)+" t",34,TEXT,True)
        d.line((x+205,407,x+205,478),fill="#6690a4",width=1)
        txt(d,(x+225,420),"Backlog",17,"#c3dbe5")
        txt(d,(x+225,446),amount(back)+" t",30,color,True)
    rect(d,(20,508,836,628),"#075142",GREEN,12)
    txt(d,(47,528),"Total predat AL + CU",21,TEXT,True)
    txt(d,(48,565),amount(r["handed"])+" t",42,TEXT,True)
    d.line((445,528,445,607),fill="#7edcba",width=2)
    txt(d,(475,528),"Backlog predat",21,TEXT,True)
    txt(d,(475,565),amount(r["backlog"])+" t",42,TEXT,True)
    rect(d,(20,641,836,869),"#0b304d",BLUE,12)
    txt(d,(48,662),"Deșeu",29,TEXT,True)
    for y,label,value,color in [(713,"Aluminiu",wal,BLUE),(755,"Cupru",wcu,ORANGE),(804,"Total deșeu",r["waste"],GREEN)]:
        txt(d,(55,y),label,17,"#d7e8ed");txt(d,(235,y),amount(value)+" t",20,color,True)
    d.line((47,797,315,797),fill="#6698a9",width=1)
    cx,cy,rad=438,762,72
    d.ellipse((cx-rad,cy-rad,cx+rad,cy+rad),outline="#728f9f",width=21)
    pct=float(r["percent"])
    if pct>0:d.arc((cx-rad,cy-rad,cx+rad,cy+rad),-90,-90+max(2,360*min(100,pct)/100),fill=GREEN,width=21)
    txt(d,(cx,cy-10),amount(r["percent"],1)+"%",26,TEXT,True,anchor="mm")
    txt(d,(cx,cy+20),"PROCENT DEȘEU",10,"#aec6d0",anchor="mm")
    txt(d,(575,731),"DEȘEU",14,GREEN,True);txt(d,(575,755),amount(r["waste"])+" t",22,TEXT,True)
    txt(d,(575,792),"MATERIAL PREDAT",14,"#b0c6d2",True);txt(d,(575,816),amount(r["handed"])+" t",22,TEXT,True)
    rect(d,(20,883,836,966),"#0b4971",BLUE,12)
    txt(d,(49,899),"Total procesat",18,"#dcecf2");txt(d,(48,924),amount(r["processed"])+" t",33,TEXT,True)
    d.line((430,899,430,952),fill="#7daabe",width=1)
    txt(d,(462,899),"Procent deșeu",18,"#dcecf2");txt(d,(462,924),amount(r["percent"],1)+"%",33,TEXT,True)
    # Operational table.
    rect(d,(850,306,1480,966),"#0e3049",LINE,12)
    txt(d,(878,329),"Indicatori operaționali",25,TEXT,True)
    txt(d,(1455,341),date_line,13,"#bbd8e4",anchor="rm",max_width=250)
    rect(d,(868,378,1461,412),"#145076",BLUE,7)
    txt(d,(883,386),"INDICATOR",13,TEXT,True)
    txt(d,(1444,386),"VALOARE",13,TEXT,True,anchor="ra")
    y=412;row_h=34
    for i,(label,key) in enumerate(OPS):
        if i%2:rect(d,(868,y,1461,y+row_h),"#153a53")
        txt(d,(882,y+row_h/2),label,13,"#e0edf1",anchor="lm",max_width=300)
        txt(d,(1441,y+row_h/2),extras.get(key,"") or "—",13,GREEN if i<3 else "#dbe9ee",anchor="rm",max_width=260)
        d.line((868,y+row_h,1461,y+row_h),fill="#315c71",width=1)
        y+=row_h
    if extras.get("obs"):
        txt(d,(878,933),"Observații: "+extras["obs"],12,"#d4e7eb",max_width=560)
    return png(im)
