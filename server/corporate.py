"""Clean NRG PLUP image layouts with matching light and dark palettes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from PIL import Image, ImageDraw

from server.render import HEADERS, KEYS, OPS, amount, font, png, text, wrapped
from server.source_render import source_image, combined_image


LIGHT = {
    "bg":"#fffdf1","paper":"#fffef9","ink":"#1e342e","muted":"#53645a",
    "line":"#d9e2d3","head":"#e8f5e8","stripe":"#f5f6ec","pill":"#e8f5e8",
    "blue":"#e8f5ef","green":"#edf5df","yellow":"#f5f5d6",
    "accent":"#006b65","success":"#147549","success_bg":"#dff0cb",
    "al":"#255ab7","cu":"#b44c16","hero":"#006b65","hero_ink":"#fff9e9"
}
DARK = {
    "bg":"#141f1a","paper":"#1e2c24","ink":"#fff9e9","muted":"#c4d2be",
    "line":"#425748","head":"#293b2e","stripe":"#223429","pill":"#293b2e",
    "blue":"#243c32","green":"#293c28","yellow":"#353d26",
    "accent":"#64dbc4","success":"#b6de83","success_bg":"#344b2a",
    "al":"#9dbdff","cu":"#ffb277","hero":"#0a443d","hero_ink":"#fff9e9"
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


def plan_image(plan,theme="light",insights=None,section="all",page=0):
    from io import BytesIO
    from server.plan_analysis import build
    from server.source_render import MAX_PIXELS,SourceRenderError
    p=DARK if theme=="dark" else LIGHT
    if section not in ("all","summary","table","clients","stock"):raise ValueError("Secțiune invalidă")
    if section=="table":return _plan_table_image(plan,theme)
    table=Image.open(BytesIO(_plan_table_image(plan,theme))) if section=="all" else None
    if insights is None:
        raw={"rows":[{k:str(v) for k,v in row.items()} for row in plan['rows']]}
        if plan.get('sourceTable'):raw['sourceTable']=plan['sourceTable']
        insights=build(plan,raw)
    if section=='stock':
        from server.section_stock import image
        return image(plan,insights,theme)
    if section=='clients':
        from server.client_flow_render import image
        return image(plan,insights,theme,page)
    stages=[r for r in insights['stages'] if r['current'] is not None]
    from server import plan_visuals
    clients=insights.get('clients',[])
    cards=[(title,insights[key],unit) for title,key,unit in [('METAL PLANIFICAT','planned','t'),('METAL PREDAT','handed','t'),('REALIZARE ÎN TONE','percent','%')] if insights[key] is not None]
    group_lines=[]
    for m in ('AL','CU'):
        parts=[title+': '+amount(insights['groups'][m][key],2)+' t' for key,title in [('planned','planificat'),('handed','predat')] if insights['group_present'][m][key] and insights[key] is not None]
        if parts:group_lines.append((m,m+' · '+' / '.join(parts)))
    stock_parts=[title+': '+amount(insights['ton_stocks'][key],2)+' t' for key,title in [('wire','Sârmă'),('spool','Lită')] if insights['ton_stocks'][key] is not None]
    if not cards and not stages and not clients and not stock_parts and table is not None:return png(table)
    y=140
    if cards:y=280
    if group_lines:y+=30
    chart_top=y+15
    end=chart_top+plan_visuals.height(insights,ImageDraw.Draw(Image.new('RGB',(1,1))))
    offset=end-87+20;width=table.width if table is not None else 1672
    height=table.height+offset if table is not None else end+30
    if width*height>MAX_PIXELS:raise SourceRenderError('Tabelul și diagramele depășesc dimensiunea maximă a imaginii.')
    image=Image.new('RGB',(width,height),p['bg']);d=ImageDraw.Draw(image);left=(width-1672)//2
    if table is not None:
        image.paste(table.crop((0,0,width,87)),(0,0));image.paste(table.crop((0,87,width,table.height)),(0,87+offset))
    else:brand(d,width,date.fromisoformat(plan['date']).strftime('%d.%m.%Y'),f"PLAN {plan['week'].upper()}",p)
    def txt(x,y,t,size=16,color=None,bold=False,w=None):label(d,(left+x,y),t,size,color or p['ink'],bold=bold,width=w)
    txt(30,103,'PLAN DE PRODUCȚIE',20,bold=True)
    orange='#ef9b50' if theme=='dark' else '#b76517'
    colors={'METAL PLANIFICAT':p['accent'],'METAL PREDAT':p['success'],'REALIZARE ÎN TONE':orange};fills={'METAL PLANIFICAT':p['blue'],'METAL PREDAT':p['green'],'REALIZARE ÎN TONE':p['stripe']}
    for i,(title,v,unit) in enumerate(cards):
        width_card=(1612-24*(len(cards)-1))/len(cards);x=30+i*(width_card+24)
        d.rounded_rectangle((left+x,140,left+x+width_card,256),radius=12,fill=fills[title],outline=p['line']);txt(x+20,159,title,14,p['muted'],True);txt(x+20,198,amount(v,2)+' '+unit,30,colors[title],True,width_card-40)
    yy=280 if cards else 140
    for i,(m,line) in enumerate(group_lines):txt(30+i*820,yy,line,16,p['accent'] if m=='AL' else orange,True)
    if group_lines:yy+=30
    plan_visuals.draw(d,left,chart_top,insights,p,theme)
    return png(image)

OPS_LABELS=["Asumat / Realizat (t) + %","Realizat vs status","Realizat vs plan","Previzionat schimbul 1",
            "Backlog aluminiu (t)","Backlog cupru (t)","SF așteptare · Rigid 1 (km)",
            "SF așteptare · Rigid 2 (km)","SF așteptare · Rigid 3 (km)",
            "SF așteptare · Multifir 8 căi 1 (t)","SF așteptare · Multifir 8 căi 2 (t)",
            "SF așteptare · 16 căi Niehoff (t)","SF așteptare · 16 căi Beta 3 (t)",
            "Stoc aluminiu","Stoc cupru"]


def weekend_image(report,theme="light"):
    from server.signature_render import production_image as signature_production
    return signature_production(report,0,theme)


def production_image(report,page=0,theme="light"):
    from server.signature_render import production_image as signature_production
    return signature_production(report,page,theme)


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


def forecast_image(forecast,theme="light",show_status=True,section="all"):
    from io import BytesIO
    from server.source_render import MAX_PIXELS,SourceRenderError
    p=DARK if theme=="dark" else LIGHT
    if section not in ("all","summary","table"):raise ValueError("Secțiune invalidă")
    if section=="table":return _forecast_table_image(forecast,theme,show_status)
    table=Image.open(BytesIO(_forecast_table_image(forecast,theme,show_status))) if section=="all" else None
    from server.forecast_clients import distribution
    clients,note=distribution(forecast)
    clients=[r for r in clients if not r.get("unknown")]
    measure=ImageDraw.Draw(Image.new('RGB',(1,1)))
    client_lines=[wrapped(measure,row['material']+' · '+row['client'],16,535) for row in clients]
    client_heights=[max(46,18+24*len(lines)) for lines in client_lines]
    chart_height=64+sum(client_heights) if clients else 0
    from server.forecast_work import build
    from server.forecast_work_render import work_image
    execution=work_image(forecast.get('work',build(forecast['rows'])),p)
    work_height=execution.height+14 if execution else 0
    source=forecast.get('sourceTable');known=lambda k:not source or k in source['columns']
    summary_height=210 if known('tons') or known('km') else 0
    offset=summary_height+chart_height+work_height;width=table.width if table is not None else 1672
    height=table.height+offset if table is not None else 87+offset+30
    if width*height>MAX_PIXELS:raise SourceRenderError("Tabelul și sinteza depășesc dimensiunea maximă a imaginii.")
    image=Image.new("RGB",(width,height),p['bg']);d=ImageDraw.Draw(image)
    if table is not None:
        image.paste(table.crop((0,0,width,87)),(0,0));image.paste(table.crop((0,87,width,table.height)),(0,87+offset))
    else:brand(d,width,date.fromisoformat(forecast['date']).strftime('%d.%m.%Y'),"PREVIZ ZILNIC",p)
    left=(width-1672)//2
    if summary_height:label(d,(left+30,103),'PREVIZ ZILNIC',19,p['ink'],bold=True)
    for i,(material,title,color,fill) in enumerate([('AL','ALUMINIU',p['accent'],p['blue']),('CU','CUPRU','#ef9b50' if theme=='dark' else '#b76517','#493628' if theme=='dark' else '#fff0df'),('TOTAL','TOTAL PREVIZ',p['success'],p['green'])]):
        if not summary_height:continue
        x=left+30+i*546;d.rounded_rectangle((x,140,x+520,262),radius=12,fill=fill,outline=p['line'])
        totals=forecast['totals'][material] if material!='TOTAL' else {k:sum(forecast['totals'][m][k] for m in ('AL','CU')) for k in ('km','tons')}
        known=lambda k:not forecast.get('sourceTable') or k in forecast['sourceTable']['columns']
        label(d,(x+20,157),title,14,p['muted'],bold=True)
        if known('tons'):label(d,(x+20,188),amount(totals['tons'],2)+' t',28,color,bold=True,width=480)
        if known('km'):label(d,(x+20,229),amount(totals['km'],2)+' km',16,p['ink'])

    if clients:label(d,(left+30,summary_height+99),'DISTRIBUȚIA TONELOR PE CLIENȚI',18,p['ink'],bold=True)
    material_totals={material:sum(float(row['tons']) for row in distribution(forecast)[0] if row['material']==material) for material in ('AL','CU')}
    y=summary_height+134
    colors=[p['accent'],p['success'],'#ef9b50' if theme=='dark' else '#b76517','#8b84d5','#42a5ac']
    for i,(row,lines,h) in enumerate(zip(clients,client_lines,client_heights)):
        for j,line in enumerate(lines):label(d,(left+30,y+(h-24*len(lines))/2+j*24),line,16,p['ink'])
        center=y+h/2
        d.rounded_rectangle((left+595,center-8,left+1330,center+8),radius=6,fill=p['head'])
        bar=735*float(row['tons'])/(material_totals[row['material']] or 1)
        d.rounded_rectangle((left+595,center-8,left+595+max(6,bar),center+8),radius=6,fill=colors[i%len(colors)])
        label(d,(left+1350,center-11),amount(row['tons'],2)+' t · '+amount(row['materialPercent'],1)+'% '+row['material'],17,p['ink'],bold=True,width=290)
        y+=h

    if execution:image.paste(execution,(left,87+summary_height+chart_height))
    return png(image)
