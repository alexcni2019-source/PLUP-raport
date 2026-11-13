"""Approved Teal / Cream / Emerald production exports from validated Python data."""
from datetime import date
from decimal import Decimal
from PIL import Image,ImageDraw
from server.render import amount,font,png,wrapped,OPS
from server.source_render import combined_image,source_image,MAX_PIXELS,SourceRenderError

class Canvas:
    def __init__(self,p):
        self.p=p;self.width=2000;self.y=0
        self.image=Image.new('RGB',(self.width,11000),p['bg']);self.draw=ImageDraw.Draw(self.image)
    def text(self,x,y,value,size=30,bold=False,color=None,anchor='lt'):
        self.draw.text((x,y),str(value),font=font(size,bold),fill=color or self.p['ink'],anchor=anchor)
    def panel(self,box,fill=None):
        self.draw.rounded_rectangle(box,24,fill=fill or self.p['paper'],outline=self.p['line'],width=2)
    def header(self,title,stamp):
        p=self.p;self.draw.rectangle((0,0,2000,12),fill=p['accent'])
        self.text(60,42,'NRG Cables',40,True);self.text(345,50,'PLUP Department',28,color=p['muted'])
        self.text(1940,48,stamp,32,True,p['muted'],'rt')
        self.text(60,144,title,60,True);self.y=260
    def metric(self,x,y,w,label,value,note='',hero=False):
        p=self.p;ink=p['hero_ink'] if hero else p['ink']
        self.panel((x,y,x+w,y+218),p['hero'] if hero else p['paper'])
        self.text(x+29,y+25,label,30,True,ink if hero else p['muted'])
        self.text(x+29,y+78,amount(value,2)+' t',78,True,ink)
        if note:self.text(x+29,y+170,note,26,color=ink if hero else p['muted'])
    def materials(self,v):
        p=self.p;w=928
        for i,(material,label,key,back,color) in enumerate([('AL','Aluminiu','al','backlogAl',p['al']),('CU','Cupru','cu','backlogCu',p['cu'])]):
            x=60+i*952;y=self.y
            self.panel((x,y,x+w,y+220),p['head'] if material=='AL' else p['paper'])
            self.text(x+30,y+25,material+' · '+label,34,True,color)
            self.text(x+30,y+88,amount(v[key],2)+' t',74,True)
            self.text(x+w-29,y+167,'Backlog '+amount(v[back],2)+' t',28,color=p['muted'],anchor='rt')
        self.y+=248
    def summary(self,t):
        for i,(label,key,note) in enumerate([('Total predat','handed','AL + CU'),('Backlog','backlog','Din materialul predat'),('Total procesat','processed','Predat + deșeu')]):
            self.metric(60+i*634.66,self.y,610.66,label,t[key],note,i==0)
        self.y+=246
    def table(self,headers,rows,widths):
        p=self.p;top=self.y;layouts=[wrapped(self.draw,h,30,w-36,True) for h,w in zip(headers,widths)]
        hh=32+40*max(map(len,layouts));self.draw.rectangle((60,top,1940,top+hh),fill=p['head'])
        x=60
        for lines,w in zip(layouts,widths):
            for j,line in enumerate(lines):self.text(x+18,top+16+j*40,line,30,True)
            x+=w
        self.y+=hh
        for i,row in enumerate(rows):
            lines=[wrapped(self.draw,value,30,w-38) for value,w in zip(row,widths)];height=max(76,30+42*max(map(len,lines)))
            self.draw.rectangle((60,self.y,1940,self.y+height),fill=p['paper'] if i%2==0 else p['stripe'])
            x=60
            for cell,w in zip(lines,widths):
                for j,line in enumerate(cell):self.text(x+18,self.y+15+j*42,line,30)
                x+=w
            self.y+=height;self.draw.line((60,self.y,1940,self.y),fill=p['line'])
        self.y+=35
    def charts(self,t,v):
        p=self.p;y=self.y;self.panel((60,y,988,y+355));self.panel((1012,y,1940,y+355))
        self.text(88,y+24,'Deșeu / material procesat',34,True)
        ring=(95,y+104,295,y+304);pct=float(t['percent']);self.draw.arc(ring,0,360,fill=p['line'],width=24)
        if pct:self.draw.arc(ring,-90,-90+min(100,pct)*3.6,fill=p['success'],width=24)
        self.text(195,y+180,amount(t['percent'],1)+'%',42,True,anchor='mt')
        self.text(329,y+116,'TOTAL DEȘEU',28,True,p['muted']);self.text(329,y+158,amount(t['waste'],2)+' t',44,True,p['success'])
        self.text(329,y+228,amount(t['processed'],2)+' t procesate',28,True)
        self.text(329,y+280,'AL '+amount(v['wasteAl'],2)+' t · CU '+amount(v['wasteCu'],2)+' t',27,color=p['muted'])
        self.text(1040,y+24,'Predare și backlog',34,True)
        for i,(name,value,color) in enumerate([('Aluminiu',v['al'],p['al']),('Cupru',v['cu'],p['cu']),('Backlog / total predat',t['backlog'],p['accent'])]):
            yy=y+94+i*84;ratio=value/t['handed']*100 if t['handed'] else None
            self.text(1040,yy,name,28)
            self.text(1912,yy,amount(value,2)+' t · '+(amount(ratio,1)+'%' if ratio is not None else '—'),28,True,anchor='rt')
            self.draw.rounded_rectangle((1040,yy+42,1912,yy+57),7,fill=p['line'])
            if ratio:self.draw.rounded_rectangle((1040,yy+42,1040+872*min(1,float(ratio)/100),yy+57),7,fill=color)
        self.y+=387
    def finish(self):
        self.draw.line((60,self.y+10,1940,self.y+10),fill=self.p['line'],width=2)
        self.text(60,self.y+36,'NRG Cables · PLUP Department',25,color=self.p['muted'])
        height=self.y+104
        if height>11000 or 2000*height>MAX_PIXELS:raise SourceRenderError('Raportul depășește dimensiunea maximă a imaginii.')
        return self.image.crop((0,0,2000,height))

def production_image(report,page=0,theme='light'):
    from server.corporate import LIGHT,DARK,OPS_LABELS
    p=DARK if theme=='dark' else LIGHT
    if page!=0:raise ValueError('Raportul de producție are o singură pagină.')
    if report.get('sourceTable') and not any(k in report['sourceTable']['columns'] for k in ('al','cu','backlogAl','backlogCu','wasteAl','wasteCu')):
        return png(source_image(report,p))
    days=report['days'];weekend=report['mode']=='weekend';t=report['total'];last=days[-1]
    v={key:sum(day['values'][key] for day in days) for key in ('al','cu','backlogAl','backlogCu','wasteAl','wasteCu')}
    stamp=date.fromisoformat(days[0]['date']).strftime('%d.%m.%Y')
    if weekend:stamp+=' – '+date.fromisoformat(last['date']).strftime('%d.%m.%Y')
    canvas=Canvas(p);canvas.header('Raport de weekend' if weekend else 'Raport de producție',stamp)
    canvas.materials(v);canvas.summary(t)
    if weekend:
        rows=[]
        for day,name in zip(days,['Vineri','Sâmbătă','Duminică']):
            d=day['values'];rows.append([name+'\n'+date.fromisoformat(day['date']).strftime('%d.%m.%Y'),amount(d['al'],2)+' t',amount(d['cu'],2)+' t',amount(day['backlog'],2)+' t',amount(day['waste'],2)+' t',amount(day['processed'],2)+' t',amount(day['percent'],1)+'%'])
        canvas.table(['Zi / Data','Predat AL','Predat CU','Backlog','Deșeu','Procesat','Deșeu %'],rows,[350,255,255,255,255,255,255])
    canvas.charts(t,v)
    extras=last['extras'];rows=[]
    for label,key in [*zip(OPS_LABELS,OPS),('Observații','obs')]:
        if extras.get(key):rows.append([label,extras[key]])
    if rows:
        canvas.text(60,canvas.y,'Indicatori operaționali',38,True);canvas.y+=65;canvas.table(['Indicator','Valoare'],rows,[650,1230])
    image=canvas.finish()
    return combined_image(image,report,p,stamp) if report.get('sourceTable') else png(image)
