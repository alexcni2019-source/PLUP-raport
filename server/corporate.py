"""Clean NRG PLUP image layouts with matching light and dark palettes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from PIL import Image, ImageDraw

from server.render import HEADERS, KEYS, OPS, amount, font, png, text, wrapped
from server.source_render import source_image, combined_image


LIGHT = {
    "bg":"#f5f5f7","paper":"#ffffff","ink":"#202329","muted":"#606673",
    "line":"#e0e3e8","head":"#f0f2f5","stripe":"#f8f9fb","pill":"#edf0f5",
    "blue":"#eaf2fd","green":"#eaf4ef","yellow":"#f2f3f6",
    "accent":"#0969da","success":"#267d4c","success_bg":"#e7f3ed"
}
DARK = {
    "bg":"#151619","paper":"#202125","ink":"#f1f3f7","muted":"#adb3bf",
    "line":"#383b43","head":"#292b31","stripe":"#24262c","pill":"#30343d",
    "blue":"#263950","green":"#263c32","yellow":"#303138",
    "accent":"#80b9ff","success":"#80c6a0","success_bg":"#263c32"
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
    label(draw,(339,31),"PLUP Department",24,p["muted"])
    caption=f"{stamp}  ·  {title}"
    caption_width=draw.textlength(caption,font=font(22,True))
    x=max(630,round(width-caption_width-57))
    label(draw,(x,35),caption,22,p["ink"],bold=True,width=width-x-42)


def _plan_table_image(plan,theme="light"):
    p=dict(DARK if theme=="dark" else LIGHT)
    p["green"]="#493628" if theme=="dark" else "#fff0df"
    p["yellow"]="#263b32" if theme=="dark" else "#e3f5ea"
    if plan.get("sourceTable"):return png(source_image(plan,p))
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
    end=184+body_height+39+16+36+40+42+42
    height=max(540,end+40)
    image=Image.new("RGB",(1672,height),p["bg"])
    d=ImageDraw.Draw(image)
    stamp=date.fromisoformat(plan["date"]).strftime("%d.%m.%Y")
    brand(d,1672,stamp,f"PLAN {plan['week'].upper()}",p)
    d.rounded_rectangle((14,87,1658,height-22),radius=14,fill=p["paper"],outline=p["line"],width=1)
    d.rectangle((30,104,1644,184),fill=p["head"])
    for index,head in enumerate(HEADERS):
        left,right=X[index+1],X[index+2]
        parts=[line for part in head.split("\n") for line in wrapped(measure,part,13,right-left-8,True)]
        for n,part in enumerate(parts):
            label(d,((left+right)/2,144+(n-(len(parts)-1)/2)*18),part,13,p["ink"],bold=True,anchor="mm")
    y=184
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
    d.line((30,184,1644,184),fill=p["line"])
    return png(image)


def plan_image(plan,theme="light",insights=None):
    from io import BytesIO
    from server.plan_analysis import build
    from server.source_render import MAX_PIXELS,SourceRenderError
    p=DARK if theme=="dark" else LIGHT
    table=Image.open(BytesIO(_plan_table_image(plan,theme)))
    if insights is None:
        # Direct render callers can still receive current totals without a DB comparison.
        raw={"rows":[{k:str(v) for k,v in row.items()} for row in plan['rows']]}
        if plan.get("sourceTable"):raw["sourceTable"]=plan["sourceTable"]
        insights=build(plan,raw)
    offset=790;width=table.width
    if width*(table.height+offset)>MAX_PIXELS:raise SourceRenderError("Tabelul și diagramele depășesc dimensiunea maximă a imaginii.")
    image=Image.new("RGB",(width,table.height+offset),p['bg']);image.paste(table.crop((0,0,width,87)),(0,0));image.paste(table.crop((0,87,width,table.height)),(0,87+offset));d=ImageDraw.Draw(image)
    left=(width-1672)//2
    def txt(x,y,t,size=16,color=None,bold=False,w=None):label(d,(left+x,y),t,size,color or p['ink'],bold=bold,width=w)
    def value(v,unit):return amount(v,2)+' '+unit if v is not None else 'Necompletat'
    txt(30,106,"PLAN DE PRODUCȚIE · SINTEZĂ ȘI EVOLUȚIE",20,bold=True)
    orange='#ef9b50' if theme=='dark' else '#b76517'
    colors=[p['accent'],p['success'],orange];fills=[p['blue'],p['green'],p['stripe']]
    cards=[('METAL PLANIFICAT',insights['planned'],'t'),('METAL PREDAT',insights['handed'],'t'),('REALIZARE ÎN TONE',insights['percent'],'%')]
    for i,(title,v,unit) in enumerate(cards):
        x=30+i*546;d.rounded_rectangle((left+x,148,left+x+520,259),radius=12,fill=fills[i],outline=p['line']);txt(x+20,168,title,14,p['muted'],True);txt(x+20,205,value(v,unit),30,colors[i],True,480)
    if insights['percent'] is not None:
        d.rounded_rectangle((left+1142,247,left+1622,254),radius=3,fill=p['head'])
        progress=480*max(0,min(1,float(insights['percent'])/100))
        if progress:d.rounded_rectangle((left+1142,247,left+1142+max(4,progress),254),radius=3,fill=p['success'])
    a,c=insights['groups']['AL'],insights['groups']['CU']
    txt(30,279,f"AL planificat / predat: {value(a['planned'] if insights['planned'] is not None else None,'t')} / {value(a['handed'] if insights['handed'] is not None else None,'t')}",16,p['accent'],True)
    txt(850,279,f"CU planificat / predat: {value(c['planned'] if insights['planned'] is not None else None,'t')} / {value(c['handed'] if insights['handed'] is not None else None,'t')}",16,orange,True)
    txt(30,305,f"Stoc sârmă: {value(insights['ton_stocks']['wire'],'t')}  ·  Stoc lită: {value(insights['ton_stocks']['spool'],'t')}",13,p['muted'])
    txt(30,322,"SITUAȚIA PE FLUX · TOATE POZIȚIILE · KM",18,bold=True)
    txt(30,351,"Stocuri pe etape și marfă predată; cantitățile nu se adună într-un procent din tone.",13,p['muted'])
    stages=insights['stages'];maximum=max([float(r['current']) for r in stages if r['current'] is not None]+[1])
    stage_colors=[p['accent'],'#43a9ac','#7a8fe7','#b084cd','#ef9b50',p['success'],'#4c9bb9']
    for i,row in enumerate(stages):
        y=391+i*50;txt(30,y,row['label'],16);txt(700,y,value(row['current'],'km'),16,bold=True,w=140)
        d.rounded_rectangle((left+240,y+3,left+670,y+19),radius=6,fill=p['head'])
        if row['current']:
            bar=430*float(row['current'])/maximum;d.rounded_rectangle((left+240,y+3,left+240+max(6,bar),y+19),radius=6,fill=stage_colors[i])
    comparison=insights['comparison'];txt(876,322,"EVOLUȚIE · POZIȚII COMUNE",18,bold=True)
    if comparison:
        txt(876,351,f"Față de {comparison['date']} · {comparison['common']} poziții comparabile",13,p['muted'])
        txt(876,375,f"Noi: {comparison['new']} · absente: {comparison['missing']} · ambigue: {comparison['ambiguous']}",13,p['muted'])
        txt(876,412,"INDICATOR",12,p['muted'],True);txt(1130,412,"ANTERIOR",12,p['muted'],True);txt(1305,412,"ACUM",12,p['muted'],True);txt(1470,412,"DIFERENȚĂ",12,p['muted'],True)
        for i,row in enumerate(comparison['metrics']):
            y=445+i*32
            if i%2:d.rectangle((left+866,y-6,left+1642,y+32),fill=p['stripe'])
            txt(876,y,row['label'],14,w=235);txt(1130,y,value(row['previous'],row['unit']) if row['previous'] is not None else '—',14,w=160);txt(1305,y,value(row['current'],row['unit']) if row['current'] is not None else '—',14,w=155)
            delta=row['delta'];txt(1470,y,('+' if delta is not None and delta>0 else '')+value(delta,row['unit']) if delta is not None else '—',14,p['accent'],True,165)
    else:
        for j,line in enumerate(['Comparația apare după ce există un plan','salvat sau generat la o dată anterioară.','Produsele noi nu intră în evoluția comparată.']):txt(876,399+j*28,line,16,p['muted'])
    txt(30,796,"Comparație după material, client și produs. Pozițiile duplicate sau lipsă nu sunt tratate automat ca finalizate.",14,p['muted'])
    txt(30,826,"Diferențele de stoc nu reprezintă predări. Celulele lipsă nu intră în comparații numerice.",14,p['muted'])
    if plan.get("sourceTable"):txt(30,852,"Sinteza folosește coloanele asociate; tabelul importat păstrează totalurile originale din sursă.",13,p["muted"])
    return png(image)


OPS_LABELS=["Asumat / Realizat (t) + %","Realizat vs status","Realizat vs plan","Previzionat schimbul 1",
            "Backlog aluminiu (t)","Backlog cupru (t)","SF așteptare · Rigid 1 (km)",
            "SF așteptare · Rigid 2 (km)","SF așteptare · Rigid 3 (km)",
            "SF așteptare · Multifir 8 căi 1 (t)","SF așteptare · Multifir 8 căi 2 (t)",
            "SF așteptare · 16 căi Niehoff (t)","SF așteptare · 16 căi Beta 3 (t)",
            "Stoc aluminiu","Stoc cupru"]


def weekend_image(report,theme="light"):
    p=DARK if theme=="dark" else LIGHT
    days=report["days"];total=report["total"]
    stamp=date.fromisoformat(days[0]["date"]).strftime("%d.%m.%Y")+" – "+date.fromisoformat(days[-1]["date"]).strftime("%d.%m.%Y")
    extras=days[-1]["extras"]
    measure=ImageDraw.Draw(Image.new("RGB",(1,1)));indicators=[]
    for name,key in list(zip(OPS_LABELS,OPS))+[("Observații","obs")]:
        if not extras.get(key):continue
        left=wrapped(measure,name,16,390);right=wrapped(measure,extras[key],16,890)
        indicators.append((left,right,max(42,16+24*max(len(left),len(right)))))
    height=max(1360,1243+sum(r[2] for r in indicators))
    image=Image.new("RGB",(1491,height),p["bg"]);d=ImageDraw.Draw(image)
    brand(d,1491,stamp,"RAPORT WEEKEND",p)
    label(d,(42,115),"PRODUCȚIE · VINERI / SÂMBĂTĂ / DUMINICĂ",18,p["muted"],bold=True)
    label(d,(42,151),stamp,30,p["ink"],bold=True)
    for x,title,value in [(42,"TOTAL PREDAT AL + CU",total["handed"]),(754,"BACKLOG PREDAT CUMULAT",total["backlog"])]:
        d.rounded_rectangle((x,212,x+695,334),radius=12,fill=p["blue"],outline=p["line"])
        label(d,(x+22,231),title,16,p["muted"],bold=True)
        label(d,(x+22,269),amount(value,2)+" t",34,p["ink"],bold=True)
    xs=[42,279,474,669,864,1059,1254,1449]
    headers=["ZI / DATA","PREDAT AL","PREDAT CU","TOTAL PREDAT","BACKLOG AL","BACKLOG CU","TOTAL BACKLOG"]
    d.rectangle((42,359,1449,407),fill=p["head"])
    for i,h in enumerate(headers):label(d,(xs[i]+12,375),h,13,p["muted"],bold=True)
    for i,day in enumerate(days):
        y=407+i*63;v=day["values"]
        d.rectangle((42,y,1449,y+63),fill=p["paper"] if i%2==0 else p["stripe"])
        label(d,(54,y+12),["Vineri","Sâmbătă","Duminică"][i],16,p["ink"],bold=True)
        label(d,(54,y+35),date.fromisoformat(day["date"]).strftime("%d.%m.%Y"),13,p["muted"])
        values=[v["al"],v["cu"],day["handed"],v["backlogAl"],v["backlogCu"],day["backlog"]]
        for j,value in enumerate(values,1):label(d,(xs[j]+12,y+21),amount(value,2)+" t",17,p["ink"],bold=j in (3,6),width=170)
    y=596;d.rectangle((42,y,1449,y+50),fill=p["blue"]);label(d,(54,y+16),"TOTAL WEEKEND",16,p["ink"],bold=True)
    values=[sum(day["values"][key] for day in days) for key in ("al","cu")]+[total["handed"]]+[sum(day["values"][key] for day in days) for key in ("backlogAl","backlogCu")]+[total["backlog"]]
    for j,value in enumerate(values,1):label(d,(xs[j]+12,y+16),amount(value,2)+" t",17,p["ink"],bold=True,width=170)
    label(d,(42,675),"PREDARE ȘI BACKLOG PE ZI",16,p["ink"],bold=True)
    maximum=max([float(day[k]) for day in days for k in ("handed","backlog")]+[1])
    for i,day in enumerate(days):
        x=42+i*480;label(d,(x,711),["Vineri","Sâmbătă","Duminică"][i],15,p["muted"])
        for offset,key,title,color in [(0,"handed","Predat",p["accent"]),(29,"backlog","Backlog",p["success"])]:
            y=739+offset;label(d,(x,y),title,12,p["muted"])
            d.rounded_rectangle((x+68,y,x+306,y+14),radius=5,fill=p["head"])
            width=238*float(day[key])/maximum
            if width:d.rounded_rectangle((x+68,y,x+68+max(5,width),y+14),radius=5,fill=color)
            label(d,(x+320,y-2),amount(day[key],2)+" t",14,p["ink"],bold=True,width=140)
    label(d,(42,817),"DEȘEU PE ZI · ALUMINIU ȘI CUPRU",17,p["ink"],bold=True)
    wx=[42,240,370,500,650,820,990]
    d.rectangle((42,854,990,896),fill=p["head"])
    for i,h in enumerate(["ZI","DEȘEU AL","DEȘEU CU","TOTAL DEȘEU","PROCESAT","DEȘEU %"]):label(d,(wx[i]+10,868),h,12,p["muted"],bold=True)
    for i,day in enumerate(days):
        y=896+i*46;v=day["values"]
        d.rectangle((42,y,990,y+46),fill=p["paper"] if i%2==0 else p["stripe"])
        values=[["Vineri","Sâmbătă","Duminică"][i],amount(v["wasteAl"],2)+" t",amount(v["wasteCu"],2)+" t",amount(day["waste"],2)+" t",amount(day["processed"],2)+" t",amount(day["percent"],1)+"%"]
        for j,val in enumerate(values):label(d,(wx[j]+10,y+14),val,15,p["ink"],bold=j==3,width=wx[j+1]-wx[j]-20)
    y=1034;d.rectangle((42,y,990,y+46),fill=p["green"])
    values=["TOTAL WEEKEND",amount(sum(day["values"]["wasteAl"] for day in days),2)+" t",amount(sum(day["values"]["wasteCu"] for day in days),2)+" t",amount(total["waste"],2)+" t",amount(total["processed"],2)+" t",amount(total["percent"],1)+"%"]
    for j,val in enumerate(values):label(d,(wx[j]+10,y+14),val,15,p["ink"],bold=True,width=wx[j+1]-wx[j]-20)
    ring=(1080,862,1260,1042)
    d.arc(ring,0,359,fill=p["line"],width=22)
    share=max(0,min(100,float(total["percent"])))
    if share:d.arc(ring,-90,-90+max(2,round(3.6*share)),fill=p["success"],width=22)
    label(d,(1170,940),amount(total["percent"],1)+"%",28,p["ink"],bold=True,anchor="mm")
    label(d,(1170,973),"deșeu / procesat",13,p["muted"],anchor="mm")
    label(d,(1170,1062),"Procent cumulat weekend",13,p["muted"],anchor="mm")
    y=1140
    label(d,(42,y),"INDICATORI OPERAȚIONALI · DUMINICĂ",17,p["ink"],bold=True)
    y+=37
    if not indicators:label(d,(42,y),"Nu au fost completați indicatori pentru duminică.",15,p["muted"])
    for i,(left,right,h) in enumerate(indicators):
        d.rectangle((42,y,1449,y+h),fill=p["paper"] if i%2==0 else p["stripe"])
        for j,line in enumerate(left):label(d,(54,y+9+24*j),line,16,p["ink"])
        for j,line in enumerate(right):label(d,(550,y+9+24*j),line,16,p["ink"])
        y+=h
    label(d,(42,height-34),"NRG Cables · PLUP Department",13,p["muted"])
    return png(image)


def production_image(report,page=0,theme="light"):
    if report["mode"]=="weekend":
        if page != 0:raise ValueError("Raportul de weekend are o singură pagină.")
        return weekend_image(report,theme)
    days=report["days"]
    if page<0 or page>(len(days) if len(days)>1 else 0):raise ValueError("Pagină invalidă")
    total=len(days)>1 and page==len(days)
    r=report["total"] if total else days[page]
    vals={key:sum(day["values"][key] for day in days) if total else r["values"][key]
          for key in ("al","cu","backlogAl","backlogCu","wasteAl","wasteCu")}
    extras={} if total else r["extras"]
    stamp=(date.fromisoformat(days[0]["date"]).strftime("%d.%m.%Y")+" – "+date.fromisoformat(days[-1]["date"]).strftime("%d.%m.%Y")) if total else date.fromisoformat(r["date"]).strftime("%d.%m.%Y")
    p=DARK if theme=="dark" else LIGHT
    if report.get("sourceTable") and not any(k in report["sourceTable"]["columns"] for k in ("al","cu","backlogAl","backlogCu","wasteAl","wasteCu")):
        return png(source_image(report,p,stamp=stamp))
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
    ring_base="#e3e8f0" if theme=="light" else "#3b424e"
    ring_value=p["success"]
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
                              (647,"Cupru",vals["cu"],p["success"])):
        label(d,(772,y-27),name,15,p["muted"])
        label(d,(1417,y-27),amount(value,2)+" t",16,p["ink"],bold=True,anchor="ra",width=180)
        d.rounded_rectangle((772,y,1419,y+24),radius=9,fill=p["head"])
        bar_width=round(647*float(value)/maximum)
        if bar_width:d.rounded_rectangle((772,y,772+max(9,bar_width),y+24),radius=9,fill=bar)
    label(d,(772,705),"Backlog / total predat",15,p["muted"])
    label(d,(1417,705),f'{amount(r["backlog"],2)} t / {amount(r["handed"],2)} t',16,p["ink"],bold=True,anchor="ra",width=360)
    d.rounded_rectangle((772,735,1419,759),radius=9,fill=p["head"])
    width=round(647*min(1,ratio/100))
    if width:d.rounded_rectangle((772,735,772+max(9,width),759),radius=9,fill=p["accent"])
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
    return combined_image(image,report,p,stamp) if report.get("sourceTable") else png(image)


def _forecast_table_image(forecast,theme="light",show_status=True):
    p=dict(DARK if theme=="dark" else LIGHT)
    p["green"]="#493628" if theme=="dark" else "#fff0df"
    p["yellow"]="#263b32" if theme=="dark" else "#e3f5ea"
    if forecast.get("sourceTable"):return png(source_image(forecast,p,show_status))
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
    table_end=173+body+43+14+(39 if not cu else 0)+43+47
    height=max(470,table_end+38)
    image=Image.new("RGB",(1672,height),p["bg"])
    d=ImageDraw.Draw(image)
    stamp=date.fromisoformat(forecast["date"]).strftime("%d.%m.%Y")
    brand(d,1672,stamp,"PREVIZ ZILNIC",p)
    d.rounded_rectangle((14,87,1658,height-22),radius=14,fill=p["paper"],outline=p["line"])
    d.rectangle((30,103,1644,173),fill=p["head"])
    for i,key in enumerate(keys):
        left,right=columns[i+1],columns[i+2]
        label(d,((left+right)/2,138),headers[key],18,p["ink"],bold=True,anchor="mm",width=right-left-8)
    y=173;layout_iter=iter(layouts)

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
                        is_done=status.upper().split()[0]=="PREDAT"
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


def forecast_image(forecast,theme="light",show_status=True):
    from io import BytesIO
    from server.source_render import MAX_PIXELS,SourceRenderError
    p=DARK if theme=="dark" else LIGHT
    table=Image.open(BytesIO(_forecast_table_image(forecast,theme,show_status)))
    offset=210;width=table.width
    if width*(table.height+offset)>MAX_PIXELS:raise SourceRenderError("Tabelul și sinteza depășesc dimensiunea maximă a imaginii.")
    image=Image.new("RGB",(width,table.height+offset),p['bg']);image.paste(table.crop((0,0,width,87)),(0,0));image.paste(table.crop((0,87,width,table.height)),(0,87+offset));d=ImageDraw.Draw(image)
    left=(width-1672)//2
    label(d,(left+30,103),"PREVIZ ZILNIC · SINTEZĂ",19,p['ink'],bold=True)
    for i,(material,title,color,fill) in enumerate([('AL','ALUMINIU',p['accent'],p['blue']),('CU','CUPRU','#ef9b50' if theme=='dark' else '#b76517','#493628' if theme=='dark' else '#fff0df'),('TOTAL','TOTAL PREVIZ',p['success'],p['green'])]):
        x=left+30+i*546;d.rounded_rectangle((x,140,x+520,262),radius=12,fill=fill,outline=p['line'])
        totals=forecast['totals'][material] if material!='TOTAL' else {k:sum(forecast['totals'][m][k] for m in ('AL','CU')) for k in ('km','tons')}
        known=lambda k:not forecast.get('sourceTable') or k in forecast['sourceTable']['columns']
        label(d,(x+20,157),title,14,p['muted'],bold=True)
        label(d,(x+20,188),amount(totals['tons'],2)+' t' if known('tons') else 'Tone neasociate',28,color,bold=True,width=480)
        label(d,(x+20,229),amount(totals['km'],2)+' km' if known('km') else 'KM neasociați',16,p['ink'])
    label(d,(left+30,276),"Cantități previzionate; kilometrii și tonele sunt afișate separat.",13,p['muted'])
    return png(image)
