"""Clean NRG PLUP image layouts with matching light and dark palettes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from PIL import Image, ImageDraw

from server.render import HEADERS, KEYS, OPS, amount, font, png, text, wrapped


LIGHT = {
    "bg":"#f5f8fc","paper":"#ffffff","ink":"#0b2859","muted":"#526788",
    "line":"#d6e2f0","head":"#ecf4fe","stripe":"#f6f9fd","pill":"#e8eef8",
    "blue":"#c6e2ff","green":"#d7f6df","yellow":"#fff2c0",
    "accent":"#1681ee","success":"#197338","success_bg":"#d8f5d9"
}
DARK = {
    "bg":"#071522","paper":"#0d2030","ink":"#f0f6ff","muted":"#a7c0d1",
    "line":"#304b5e","head":"#1d3b53","stripe":"#10283a","pill":"#203b52",
    "blue":"#07538e","green":"#075139","yellow":"#69551b",
    "accent":"#5ab6fc","success":"#c1f7c9","success_bg":"#176c3b"
}
X = [30,69,193,384,516,622,701,780,874,966,1048,1149,1233,1325,1442,1644]


def label(draw, xy, value, size, color, *, bold=False, width=None, anchor=None):
    text(draw,xy,value,size,color,bold,anchor,width)


def brand(draw, width, stamp, title, palette):
    p=palette
    label(draw,(29,20),"NRG Cables",40,p["ink"],bold=True,width=465)
    draw.line((309,24,309,68),fill=p["muted"],width=2)
    label(draw,(339,31),"PLUP Department",24,p["muted"])
    caption=f"{stamp}  ·  {title}"
    caption_width=draw.textlength(caption,font=font(22,True))
    x=max(630,round(width-caption_width-57))
    if p is LIGHT:draw.rounded_rectangle((x-17,18,width-25,77),radius=13,fill=p["head"],outline=p["line"])
    label(draw,(x,35),caption,22,p["ink"],bold=True,width=width-x-42)


def plan_image(plan,theme="light"):
    p=DARK if theme=="dark" else LIGHT
    al=[r for r in plan["rows"] if r["material"]=="AL"]
    cu=[r for r in plan["rows"] if r["material"]=="CU"]
    measure=ImageDraw.Draw(Image.new("RGB",(1,1)))
    def line_layout(row):
        product=wrapped(measure,row["product"],12,X[3]-X[2]-13)
        notes=wrapped(measure,row["notes"],11,X[15]-X[14]-20) if row["notes"] else []
        return product,notes,max(31,9+max(len(product),len(notes),1)*15)
    lines=[line_layout(row) for row in al+cu]
    body_height=sum(item[2] for item in lines)
    end=156+body_height+39+16+36+40+42+42
    height=max(540,end+40)
    image=Image.new("RGB",(1672,height),p["bg"])
    d=ImageDraw.Draw(image)
    stamp=date.fromisoformat(plan["date"]).strftime("%d.%m.%Y")
    brand(d,1672,stamp,f"PLAN {plan['week'].upper()}",p)
    d.rounded_rectangle((14,87,1658,height-22),radius=14,fill=p["paper"],outline=p["line"],width=1)
    d.rectangle((30,104,1644,156),fill=p["head"])
    for index,head in enumerate(HEADERS):
        left,right=X[index+1],X[index+2]
        parts=head.split("\n")
        for n,part in enumerate(parts):
            label(d,((left+right)/2,131+(n-(len(parts)-1)/2)*16),part,11,p["ink"],bold=True,anchor="mm",width=right-left-5)
    y=156
    positions={"AL":al,"CU":cu}
    layout_iter=iter(lines)

    def data_rows(material):
        nonlocal y
        for i,row in enumerate(positions[material]):
            product_lines,note_lines,row_h=next(layout_iter)
            if i%2:d.rectangle((30,y,1644,y+row_h),fill=p["stripe"])
            if i==0:
                d.rectangle((30,y,69,y+row_h),fill=p["blue"] if material=="AL" else p["green"])
                label(d,(39,y+row_h/2),material+":",13,p["ink"],bold=True,anchor="lm")
            label(d,(X[2]-9,y+row_h/2),row["client"],12,p["ink"],anchor="rm",width=X[2]-X[1]-15)
            for n,line in enumerate(product_lines):
                label(d,(X[2]+9,y+(row_h-15*len(product_lines))/2+n*15),line,12,p["ink"])
            for col,key in enumerate(KEYS):
                label(d,((X[col+3]+X[col+4])/2,y+row_h/2),amount(row[key]),12,p["ink"],anchor="mm",width=X[col+4]-X[col+3]-8)
            if note_lines:
                is_done=row["notes"].strip().lower()=="predat"
                if is_done:
                    d.rounded_rectangle((X[14]+10,y+3,X[15]-7,y+row_h-3),radius=13,fill=p["success_bg"])
                for n,line in enumerate(note_lines):
                    label(d,((X[14]+X[15])/2,y+(row_h-15*len(note_lines))/2+n*15),line,11,p["success"] if is_done else p["ink"],bold=is_done,anchor="mt",width=X[15]-X[14]-18)
            y+=row_h
            d.line((30,y,1644,y),fill=p["line"])

    def band(name,fill,totals=None,height=40):
        nonlocal y
        d.rectangle((30,y,1644,y+height),fill=fill)
        label(d,(42,y+height/2),name,14,p["ink"],bold=True,anchor="lm",width=330)
        if totals:
            for key,column in (("planned",3),("handed",4),("wire",5)):
                label(d,((X[column]+X[column+1])/2,y+height/2),amount(totals[key]),14,p["ink"],bold=True,anchor="mm")
        y+=height

    data_rows("AL")
    al_end=y
    band("TOTAL AL (TONE)",p["blue"],plan["totals"]["AL"],39)
    y+=16
    if not cu:
        d.rectangle((30,y,69,y+36),fill=p["green"])
        label(d,(41,y+18),"CU:",13,p["ink"],bold=True,anchor="lm")
        y+=36
    cu_start=y
    data_rows("CU")
    cu_end=y
    band("TOTAL CU (TONE)",p["green"],plan["totals"]["CU"])
    a,c=plan["totals"]["AL"],plan["totals"]["CU"]
    band("TOTAL GENERAL (TONE)",p["yellow"],{k:a[k]+c[k] for k in ("planned","handed","wire")},42)
    band("INTRĂRI METAL (TONE)",p["head"],None,42)
    label(d,((X[3]+X[4])/2,y-21),amount(plan["incoming"]),14,p["ink"],bold=True,anchor="mm")
    for x in X:
        if x in (X[1],X[2]):
            d.line((x,104,x,al_end),fill=p["line"])
            if cu_end>cu_start:d.line((x,cu_start,x,cu_end),fill=p["line"])
        else:d.line((x,104,x,y),fill=p["line"])
    d.line((30,156,1644,156),fill=p["line"])
    return png(image)


OPS_LABELS=["Asumat / Realizat (t) + %","Realizat vs status","Realizat vs plan","Previzionat schimbul 1",
            "Backlog aluminiu (t)","Backlog cupru (t)","SF așteptare · Rigid 1 (km)",
            "SF așteptare · Rigid 2 (km)","SF așteptare · Rigid 3 (km)",
            "SF așteptare · Multifir 8 căi 1 (t)","SF așteptare · Multifir 8 căi 2 (t)",
            "SF așteptare · 16 căi Niehoff (t)","SF așteptare · 16 căi Beta 3 (t)",
            "Stoc aluminiu","Stoc cupru"]


def production_image(report,page=0,theme="light"):
    days=report["days"]
    if page<0 or page>(len(days) if len(days)>1 else 0):raise ValueError("Pagină invalidă")
    total=len(days)>1 and page==len(days)
    r=report["total"] if total else days[page]
    vals={key:sum(day["values"][key] for day in days) if total else r["values"][key]
          for key in ("al","cu","backlogAl","backlogCu","wasteAl","wasteCu")}
    extras={} if total else r["extras"]
    stamp=(date.fromisoformat(days[0]["date"]).strftime("%d.%m.%Y")+" – "+date.fromisoformat(days[-1]["date"]).strftime("%d.%m.%Y")) if total else date.fromisoformat(r["date"]).strftime("%d.%m.%Y")
    p=DARK if theme=="dark" else LIGHT
    measure=ImageDraw.Draw(Image.new("RGB",(1,1)))
    indicators=[]
    for name,key in zip(OPS_LABELS,OPS):
        if not extras.get(key):continue
        left=wrapped(measure,name,15,390)
        right=wrapped(measure,extras[key],15,890)
        indicators.append((left,right,max(38,13+22*max(len(left),len(right)))))
    if extras.get("obs"):
        indicators.append((['Observații'],wrapped(measure,extras['obs'],15,890),max(38,13+22*len(wrapped(measure,extras['obs'],15,890)))))
    table_height=sum(x[2] for x in indicators)
    table_start=568
    bottom=table_start+51+table_height if indicators else 0
    height=max(770,bottom+72)
    image=Image.new("RGB",(1491,height),p["bg"])
    d=ImageDraw.Draw(image)
    brand(d,1491,stamp,"RAPORT",p)
    d.rounded_rectangle((16,89,1475,height-25),radius=14,fill=p["paper"],outline=p["line"])
    label(d,(42,113),"RAPORT DE PRODUCȚIE" if not total else "TOTAL WEEKEND",19,p["muted"],bold=True)
    label(d,(42,145),stamp,31,p["ink"],bold=True)
    d.line((42,196,1449,196),fill=p["line"],width=2)

    def metric_card(box,title,short,handed,backlog,fill):
        x1,y1,x2,y2=box
        d.rounded_rectangle(box,radius=12,fill=fill,outline=p["line"])
        label(d,(x1+24,y1+16),short,25,p["accent"],bold=True)
        label(d,(x1+75,y1+20),title,22,p["ink"],bold=True)
        label(d,(x1+26,y1+65),"Predat",14,p["muted"])
        label(d,(x1+26,y1+89),amount(handed,2)+" t",31,p["ink"],bold=True,width=250)
        d.line((x1+329,y1+63,x1+329,y2-18),fill=p["line"])
        label(d,(x1+353,y1+65),"Backlog",14,p["muted"])
        label(d,(x1+353,y1+89),amount(backlog,2)+" t",31,p["ink"],bold=True,width=x2-x1-378)

    metric_card((42,216,731,363),"Aluminiu","AL",vals["al"],vals["backlogAl"],p["head"])
    metric_card((749,216,1449,363),"Cupru","CU",vals["cu"],vals["backlogCu"],p["stripe"])
    d.rounded_rectangle((42,381,1449,461),radius=10,fill=p["blue"])
    for x,title,value in ((64,"TOTAL PREDAT AL + CU",r["handed"]),(544,"BACKLOG PREDAT",r["backlog"]),(1041,"TOTAL PROCESAT",r["processed"])):
        label(d,(x,393),title,13,p["muted"],bold=True)
        label(d,(x,416),amount(value,2)+" t",27,p["ink"],bold=True,width=320)
    d.rounded_rectangle((42,479,1449,548),radius=10,fill=p["green"])
    label(d,(64,489),"DEȘEU AL / CU",13,p["muted"],bold=True)
    label(d,(64,512),f'{amount(vals["wasteAl"],2)} t / {amount(vals["wasteCu"],2)} t',19,p["ink"],bold=True)
    label(d,(544,489),"TOTAL DEȘEU",13,p["muted"],bold=True)
    label(d,(544,512),amount(r["waste"],2)+" t",19,p["ink"],bold=True)
    label(d,(1041,489),"PROCENT DEȘEU",13,p["muted"],bold=True)
    label(d,(1041,509),amount(r["percent"],1)+"%",28,p["ink"],bold=True)
    if indicators:
        d.rounded_rectangle((42,table_start,1449,bottom),radius=10,fill=p["paper"],outline=p["line"])
        d.rectangle((43,table_start+1,1448,table_start+51),fill=p["head"])
        label(d,(60,table_start+15),"INDICATORI OPERAȚIONALI",16,p["ink"],bold=True)
        label(d,(565,table_start+15),"VALOARE",16,p["ink"],bold=True)
        yy=table_start+51
        for i,(left,right,row_height) in enumerate(indicators):
            if i%2:d.rectangle((43,yy,1448,yy+row_height),fill=p["stripe"])
            for j,line in enumerate(left):label(d,(60,yy+8+j*22),line,15,p["ink"])
            for j,line in enumerate(right):label(d,(565,yy+8+j*22),line,15,p["ink"])
            yy+=row_height
            d.line((43,yy,1448,yy),fill=p["line"])
        d.line((545,table_start+51,545,bottom),fill=p["line"])
    label(d,(43,height-53),"NRG Cables   |   PLUP Department",13,p["muted"])
    return png(image)
