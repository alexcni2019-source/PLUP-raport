"""Clean NRG PLUP image layouts with matching light and dark palettes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
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


def cell_text(value):
    """Display only populated, nonzero detail cells; totals use amount directly."""
    value=str(value or "").strip()
    if value in ("", "—", "–", "-"):
        return ""
    try:
        if Decimal(value.replace(",", ".")) == 0:
            return ""
    except InvalidOperation:
        pass
    return value


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
        note=cell_text(row["notes"])
        notes=wrapped(measure,note,11,X[15]-X[14]-20) if note else []
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
                if not row[key]:continue
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
    table_start=815
    bottom=table_start+51+table_height if indicators else 0
    height=max(970,bottom+72)
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
    # Restore the report's visual summaries: a real waste ratio and AL/CU bars.
    d.rounded_rectangle((42,479,731,795),radius=10,fill=p["green"],outline=p["line"])
    label(d,(65,495),"DEȘEU · MATERIAL PROCESAT",17,p["ink"],bold=True)
    label(d,(65,546),"Aluminiu",14,p["muted"])
    label(d,(65,571),amount(vals["wasteAl"],2)+" t",22,p["ink"],bold=True,width=170)
    label(d,(65,613),"Cupru",14,p["muted"])
    label(d,(65,638),amount(vals["wasteCu"],2)+" t",22,p["ink"],bold=True,width=170)
    d.line((246,532,246,695),fill=p["line"],width=2)
    ring=(338,525,520,707)
    ring_base="#b5c9d6" if theme=="light" else "#356477"
    ring_value="#20a965" if theme=="light" else "#55e19b"
    d.arc(ring,0,359,fill=ring_base,width=26)
    share=max(0,min(100,float(r["percent"])))
    if share:d.arc(ring,-90,-90+max(2,round(3.6*share)),fill=ring_value,width=26)
    label(d,(429,589),amount(r["percent"],1)+"%",28,p["ink"],bold=True,anchor="mm",width=146)
    label(d,(429,619),"procent deșeu",13,p["muted"],anchor="mm")
    label(d,(552,554),"Total deșeu",14,p["muted"])
    label(d,(552,579),amount(r["waste"],2)+" t",20,p["ink"],bold=True,width=150)
    label(d,(552,624),"Total procesat",14,p["muted"])
    label(d,(552,649),amount(r["processed"],2)+" t",20,p["ink"],bold=True,width=150)
    ratio=float(r["backlog"])/float(r["handed"])*100 if r["handed"] else 0
    d.line((64,724,709,724),fill=p["line"])
    label(d,(65,739),"Backlog / total predat",14,p["muted"])
    label(d,(552,736),(amount(Decimal(str(ratio)),1)+"%") if r["handed"] else "—",22,p["ink"],bold=True,width=155)

    d.rounded_rectangle((749,479,1449,795),radius=10,fill=p["stripe"],outline=p["line"])
    label(d,(772,495),"PREDARE ȘI BACKLOG",17,p["ink"],bold=True)
    maximum=max(float(vals["al"]),float(vals["cu"]),1)
    for y,name,value,bar in ((562,"Aluminiu",vals["al"],p["accent"]),
                              (647,"Cupru",vals["cu"],"#27ae78" if theme=="light" else "#4fd0a1")):
        label(d,(772,y-27),name,15,p["muted"])
        label(d,(1417,y-27),amount(value,2)+" t",16,p["ink"],bold=True,anchor="ra",width=180)
        d.rounded_rectangle((772,y,1419,y+24),radius=9,fill=p["head"])
        bar_width=round(647*float(value)/maximum)
        if bar_width:d.rounded_rectangle((772,y,772+max(9,bar_width),y+24),radius=9,fill=bar)
    label(d,(772,705),"Backlog / total predat",15,p["muted"])
    label(d,(1417,705),f'{amount(r["backlog"],2)} t / {amount(r["handed"],2)} t',16,p["ink"],bold=True,anchor="ra",width=360)
    d.rounded_rectangle((772,735,1419,759),radius=9,fill=p["head"])
    width=round(647*min(1,ratio/100))
    if width:d.rounded_rectangle((772,735,772+max(9,width),759),radius=9,fill="#e2a638")
    label(d,(772,765),f'{amount(Decimal(str(ratio)),1)}% din totalul predat' if r["handed"] else "Fără tone predate",12,p["muted"])
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


def forecast_image(forecast,theme="light",show_status=True):
    p=DARK if theme=="dark" else LIGHT
    columns=(30,75,450,568,686,879,1089,1236,1644) if show_status else (30,75,490,620,750,970,1190,1644)
    keys=["product","km","tons","client","measure"]+(["status"] if show_status else [])+["notes"]
    headers={"product":"PRODUS","km":"KM","tons":"TONE","client":"CLIENT",
             "measure":"MĂSURĂRI","status":"STADIU","notes":"OBSERVAȚII"}
    al=[row for row in forecast["rows"] if row["material"]=="AL"]
    cu=[row for row in forecast["rows"] if row["material"]=="CU"]
    measure=ImageDraw.Draw(Image.new("RGB",(1,1)))
    def layout(row):
        wraps={}
        for i,key in enumerate(keys):
            if key not in ("product","notes","measure"):continue
            value=row[key] if key=="product" else cell_text(row[key])
            wraps[key]=wrapped(measure,value,13,columns[i+2]-columns[i+1]-18) if value else []
        return wraps,max(38,12+18*max((len(q) for q in wraps.values()),default=1))
    layouts=[layout(row) for row in al+cu]
    body=sum(height for _,height in layouts)
    table_end=153+body+43+14+(39 if not cu else 0)+43+47
    height=max(470,table_end+38)
    image=Image.new("RGB",(1672,height),p["bg"])
    d=ImageDraw.Draw(image)
    stamp=date.fromisoformat(forecast["date"]).strftime("%d.%m.%Y")
    brand(d,1672,stamp,"PREVIZ ZILNIC",p)
    d.rounded_rectangle((14,87,1658,height-22),radius=14,fill=p["paper"],outline=p["line"])
    d.rectangle((30,103,1644,153),fill=p["head"])
    for i,key in enumerate(keys):
        left,right=columns[i+1],columns[i+2]
        label(d,((left+right)/2,128),headers[key],14,p["ink"],bold=True,anchor="mm",width=right-left-8)
    y=153;layout_iter=iter(layouts)

    def rows(material,items):
        nonlocal y
        for i,row in enumerate(items):
            lines,row_height=next(layout_iter)
            if i%2:d.rectangle((30,y,1644,y+row_height),fill=p["stripe"])
            if i==0:
                d.rectangle((30,y,75,y+row_height),fill=p["blue"] if material=="AL" else p["green"])
                label(d,(40,y+row_height/2),material+":",14,p["ink"],bold=True,anchor="lm")
            for j,key in enumerate(keys):
                left,right=columns[j+1],columns[j+2]
                if key=="status":
                    status=cell_text(row[key])
                    if status:
                        is_done="PREDAT" in status.upper()
                        d.rounded_rectangle((left+8,y+5,right-8,y+row_height-5),radius=12,
                                            fill=p["success_bg"] if is_done else p["pill"])
                        label(d,((left+right)/2,y+row_height/2),status,12,p["success"] if is_done else p["ink"],bold=True,anchor="mm",width=right-left-23)
                elif key in lines:
                    for n,line in enumerate(lines[key]):
                        label(d,(left+8,y+(row_height-18*len(lines[key]))/2+n*18),line,13,p["ink"],width=right-left-16)
                elif key in ("km","tons"):
                    if not row[key]:continue
                    label(d,((left+right)/2,y+row_height/2),amount(row[key]),14,p["ink"],anchor="mm",width=right-left-12)
                else:
                    label(d,((left+right)/2,y+row_height/2),cell_text(row[key]),13,p["ink"],anchor="mm",width=right-left-12)
            y+=row_height
            d.line((30,y,1644,y),fill=p["line"])

    def total_band(title,fill,totals,height):
        nonlocal y
        d.rectangle((30,y,1644,y+height),fill=fill)
        label(d,(42,y+height/2),title,16,p["ink"],bold=True,anchor="lm",width=columns[2]-55)
        for key in ("km","tons"):
            index=keys.index(key)
            left,right=columns[index+1],columns[index+2]
            label(d,((left+right)/2,y+height/2),amount(totals[key]),16,p["ink"],bold=True,anchor="mm")
        y+=height

    rows("AL",al)
    al_end=y
    total_band("TOTAL AL",p["blue"],forecast["totals"]["AL"],43)
    y+=14
    if not cu:
        d.rectangle((30,y,75,y+39),fill=p["green"])
        label(d,(40,y+19),"CU:",14,p["ink"],bold=True,anchor="lm")
        y+=39
    cu_start=y
    rows("CU",cu)
    cu_end=y
    total_band("TOTAL CU",p["green"],forecast["totals"]["CU"],43)
    total_band("TOTAL AL + CU",p["yellow"],
               {key:forecast["totals"]["AL"][key]+forecast["totals"]["CU"][key] for key in ("km","tons")},47)
    for x in columns:
        if x in (columns[1],columns[2]):
            d.line((x,103,x,al_end),fill=p["line"])
            if cu_end>cu_start:d.line((x,cu_start,x,cu_end),fill=p["line"])
        else:d.line((x,103,x,y),fill=p["line"])
    d.line((30,153,1644,153),fill=p["line"])
    return png(image)
