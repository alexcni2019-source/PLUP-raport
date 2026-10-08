"""Bounded, in-memory Excel/clipboard input. No macros or formula execution."""
import base64
import binascii
import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import re
import zipfile
import xml.etree.ElementTree as ET

N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

def xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('XML neacceptat.')
    return ET.fromstring(raw)

def read(body):
    if not isinstance(body,dict) or len(body)!=1:raise ValueError('Fișier invalid.')
    if 'text' in body:
        text=body['text']
        if not isinstance(text,str) or len(text)>500000:raise ValueError('Tabel prea mare.')
        delimiter='\t' if '\t' in text else ';' if ';' in text else ','
        rows=list(csv.reader(StringIO(text),delimiter=delimiter))
        if not rows or len(rows)>500 or any(len(row)>40 for row in rows):raise ValueError('Folosește un tabel de maximum 500 rânduri și 40 coloane.')
        return {'sheets':[{'name':'Clipboard / CSV','rows':rows,'warnings':[]}],'message':'Celulele au fost citite direct. Verifică asocierea coloanelor.'}
    if 'file' not in body or not isinstance(body['file'],str):raise ValueError('Fișier invalid.')
    try:data=base64.b64decode(body['file'],validate=True)
    except (ValueError,binascii.Error):raise ValueError('Fișier invalid.')
    if len(data)>6000000:raise ValueError('Fișierul depășește 6 MB.')
    try:z=zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:raise ValueError('Folosește un fișier .xlsx sau lipește celulele din Excel.')
    entries=z.infolist()
    if len(entries)>500 or sum(i.file_size for i in entries)>25000000 or any(i.file_size>10000000 for i in entries):raise ValueError('Fișier Excel prea mare după decomprimare.')
    if any('vbaproject' in i.filename.lower() for i in entries):raise ValueError('Macrocomenzile nu sunt acceptate. Salvează în format .xlsx.')
    try:
        workbook=xml(z.read('xl/workbook.xml'));relations=xml(z.read('xl/_rels/workbook.xml.rels'))
        refs={r.attrib['Id']:r.attrib['Target'] for r in relations}
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(si.itertext()) for si in xml(z.read('xl/sharedStrings.xml')).findall('m:si',N)]
        formats={};styles=[]
        if 'xl/styles.xml' in z.namelist():
            style=xml(z.read('xl/styles.xml'));formats={int(n.attrib['numFmtId']):n.attrib.get('formatCode','') for n in style.findall('m:numFmts/m:numFmt',N)}
            styles=[int(n.attrib.get('numFmtId','0')) for n in style.findall('m:cellXfs/m:xf',N)]
        epoch=datetime(1904,1,1) if workbook.find('m:workbookPr',N) is not None and workbook.find('m:workbookPr',N).attrib.get('date1904') in ('1','true') else datetime(1899,12,30)
        sheets=[]
        for sheet in workbook.findall('m:sheets/m:sheet',N)[:10]:
            target=refs.get(sheet.attrib.get('{'+N['r']+'}id'),'')
            if target.startswith('/'):target=target.lstrip('/')
            elif not target.startswith('xl/'):target='xl/'+target
            if '..' in target or target not in z.namelist():continue
            root=xml(z.read(target));cells={};warnings=[];mr=0;mc=0
            for c in root.findall('m:sheetData/m:row/m:c',N):
                match=re.fullmatch(r'([A-Z]+)(\d+)',c.attrib.get('r',''))
                if not match:continue
                col=0
                for char in match[1]:col=col*26+ord(char)-64
                row=int(match[2]);v=c.find('m:v',N);value=v.text or '' if v is not None else ''
                if row>500 or col>40:
                    if value or c.find('m:is',N) is not None:raise ValueError('Tabelul depășește 500 rânduri sau 40 coloane. Copiază doar zona raportului.')
                    continue
                if c.attrib.get('t')=='s':value=strings[int(value)] if value else ''
                elif c.attrib.get('t')=='inlineStr':value=''.join(c.find('m:is',N).itertext()) if c.find('m:is',N) is not None else ''
                elif c.attrib.get('t')=='e':warnings.append('Celula '+c.attrib['r']+' conține o eroare Excel.');value=''
                else:
                    styleid=int(c.attrib.get('s','0'));fmt=styles[styleid] if styleid<len(styles) else 0
                    if value and ((14<=fmt<=22) or re.search(r'[dy]',formats.get(fmt,'').lower())):
                        try:value=(epoch+timedelta(days=float(value))).date().isoformat()
                        except (ValueError,OverflowError):pass
                if c.find('m:f',N) is not None:warnings.append('Formula din '+c.attrib['r']+' folosește rezultatul memorat de Excel; verifică valoarea. Nu executăm formule.')
                if len(value)>1000:raise ValueError('O celulă conține prea mult text.')
                cells[(row-1,col-1)]=value;mr=max(mr,row);mc=max(mc,col)
            if mr:sheets.append({'name':sheet.attrib.get('name','Foaie'),'rows':[[cells.get((r,c),'') for c in range(mc)] for r in range(mr)],'warnings':warnings[:50]})
        if not sheets:raise ValueError('Nu am găsit celule în fișier.')
        return {'sheets':sheets,'message':'Fișier citit local pe serverul privat. Alege foaia și verifică asocierea coloanelor.'}
    except (KeyError,ET.ParseError,IndexError,TypeError):raise ValueError('Structura Excel nu este acceptată. Copiază și lipește zona tabelului.')
    finally:z.close()
