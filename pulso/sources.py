"""Conectores automáticos de fuentes oficiales (sesiones 03 y 10).

- gob.pe: notas de prensa y comunicados de PCM, MINEM, MINAM, OEFA, ANA, PNP, Mininter y Petroperú.
  Se usa el buscador con sort_by=recent. robots.txt prohíbe la paginación (?sheet=), así que se lee
  sólo la primera página de cada consulta y se cubre la historia con varios términos.
- SINIA: informes mensuales de conflictos socioambientales de MINAM/OGASA (PDF).
- PCM: revista Willaqniki de la Secretaría de Gestión Social y Diálogo (PDF).

De los PDF se extraen con pypdf los pasajes que nombran un caso o activo, con su página, y se guardan
literalmente. Cada conector deja su resultado en data/sources/<nombre>.json.
"""
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin
import hashlib
import io
import json
import re
import time

import requests
from pypdf import PdfReader

from . import news, service

HEADERS={'User-Agent':news.USER_AGENT}
DIRECTORY=service.DATA/'sources'
SEED=service.ROOT/'demo_data'/'sources'
PDF_CACHE=service.DATA/'corpus'/'auto'
MONTHS={m:i for i,m in enumerate(['enero','febrero','marzo','abril','mayo','junio','julio','agosto','setiembre','octubre','noviembre','diciembre'],1)}
MONTHS['septiembre']=9
# Función de cada fuente: explica su encuadre (posible sesgo) al lector.
INSTITUTIONS={
    'defensoria':('Defensoría del Pueblo','Supervisión de derechos','Registra y clasifica el conflicto desde la mediación y la protección de derechos. Su fase es la clasificación oficial.'),
    'pcm':('PCM · Gestión Social y Diálogo','Ejecutivo · diálogo','Reporta la gestión del Ejecutivo en mesas y acuerdos; tiende a destacar avances.'),
    'minem':('MINEM','Ejecutivo · sector minero-energético','Promueve la actividad del sector; comunica acuerdos, convenios y espacios de diálogo.'),
    'minam':('MINAM','Ejecutivo · ambiente','Prioriza la dimensión socioambiental y el seguimiento de compromisos ambientales.'),
    'oefa':('OEFA','Fiscalización ambiental','Informa supervisiones, monitoreos y sanciones; no evalúa el conflicto social.'),
    'ana':('ANA','Autoridad del agua','Informa monitoreos y acciones sobre recursos hídricos.'),
    'pnp':('PNP','Orden público','Informa intervenciones; su encuadre es de seguridad y orden público.'),
    'mininter':('Mininter','Orden interno','Comunica medidas de orden interno y estados de emergencia.'),
    'petroperu':('Petroperú','Empresa','Comunicación corporativa de una de las partes.'),
    'prensa':('Prensa','Medios','Selección editorial; señal temprana, no prueba de un hecho.'),
}
GOBPE_TERMS={'mineria':['Las Bambas','Challhuahuacho','Fuerabamba','Cotabambas'],
             'hidrocarburos':['Oleoducto Norperuano','Sinchi Roca','Pijuayal','Petroperú derrame']}
GOBPE_FOCUS=['pcm','minem','minam','oefa','ana','pnp','mininter','petroperu']


def institution(key):
    name,role,lens=INSTITUTIONS.get(key,(key.upper(),'Otra entidad','Entidad pública.'))
    return {'institution_key':key,'institution':name,'role':role,'lens':lens}


def _get(url,binary=False):
    for _ in range(2):
        try:
            response=requests.get(url,headers=HEADERS,timeout=(10,60))
            if response.status_code==200:
                return response.content if binary else response.text
        except requests.RequestException:
            pass
        time.sleep(2)
    raise ValueError(f'No respondió: {url}')


def spanish_date(text):
    match=re.search(r'(\d{1,2}) de (\w+) de (\d{4})',service.norm(text or ''))
    if not match or match[2] not in MONTHS:
        return None
    return f'{int(match[3]):04d}-{MONTHS[match[2]]:02d}-{int(match[1]):02d}'


def _item(**fields):
    companies,cases,tags=news.classify({'title':fields['title'],'snippet':fields.get('quote') or fields.get('snippet') or ''})
    key=hashlib.sha256((fields['url']+str(fields.get('page',''))+fields.get('quote','')[:80]).encode()).hexdigest()[:16]
    return {'id':key,**fields,'companies':companies,'case_codes':cases,'tags':tags}


def gobpe(pause=1.0):
    """Notas y comunicados oficiales en gob.pe que mencionan los activos o comunidades."""
    queries=[(None,term) for terms in GOBPE_TERMS.values() for term in terms]
    queries+=[(slug,term) for slug in GOBPE_FOCUS for term in (GOBPE_TERMS['mineria'][0],GOBPE_TERMS['hidrocarburos'][0])]
    items,requests_made={},0
    for slug,term in queries:
        url=f'https://www.gob.pe/busquedas?contenido[]=noticias&term={quote_plus(term)}&sort_by=recent'+(f'&institucion[]={slug}' if slug else '')
        page=_get(url); requests_made+=1
        start=page.find('window.initialData=')
        data=json.loads(page[start+19:page.find('</script>',start)].strip().rstrip(';'))
        for result in data['data']['attributes'].get('results',[]):
            link=re.search(r'href="(/institucion/([a-z0-9-]+)/noticias/[^"]+)"',result.get('url') or '')
            date=spanish_date(result.get('publication'))
            if not link or not date:
                continue
            item=_item(url='https://www.gob.pe'+link[1],title=service.clean(result.get('name_with_parent') or ''),date=date,period=date[:7],
                       snippet=service.clean(re.sub(r'<[^>]+>',' ',result.get('content') or ''))[:280],kind=result.get('group_type') or 'Nota de prensa',
                       connector='gob.pe',literal=False,**institution(link[2]))
            if item['companies']:
                items[item['id']]=item
        time.sleep(pause)
    return sorted(items.values(),key=lambda i:i['date'],reverse=True),requests_made


def _pdf_passages(url,meta,max_pages=200,path=None):
    """Download (cached) and return literal passages that name a watched asset or community."""
    PDF_CACHE.mkdir(parents=True,exist_ok=True)
    path=path or PDF_CACHE/(hashlib.sha256(url.encode()).hexdigest()[:24]+'.pdf')
    if not path.exists():
        data=_get(url,binary=True)
        if not data.lstrip().startswith(b'%PDF-'):
            raise ValueError(f'No es PDF: {url}')
        path.write_bytes(data)
    reader=PdfReader(io.BytesIO(path.read_bytes()))
    words=sorted({w for ws in news.KEYWORDS.values() for w in ws}|set(news.CASES),key=len,reverse=True)
    pattern=re.compile(r'\b('+'|'.join(re.escape(w) for w in words)+r')\b')
    found={}
    for number,page in enumerate(reader.pages[:max_pages],1):
        text=re.sub(r'\s+',' ',re.sub(r'[-]','',page.extract_text() or '')).strip()
        plain=service.norm(text)  # same length as text for Spanish accents (NFKD drops combining marks)
        if len(plain)!=len(text):
            plain=''.join(service.norm(ch) or ch for ch in text)
        for match in pattern.finditer(plain):
            # From the start of the sentence that names the asset, up to ~480 characters.
            start=text.rfind('. ',0,match.start())+2 if '. ' in text[:match.start()] else 0
            if match.start()-start>260:
                start=text.find(' ',match.start()-200)+1
            quote=text[start:start+480].strip()
            if quote.rfind('. ')>200:
                quote=quote[:quote.rfind('. ')+1]
            item=_item(url=url,page=number,quote=quote,title=meta['title'],date=meta.get('date'),period=meta['period'],
                       connector=meta['connector'],literal=True,kind='Informe',document_url=meta.get('document_url',url),**institution(meta['institution_key']))
            if item['companies'] and (item['period'],number,tuple(item['case_codes']) or match[1]) not in found:
                found[(item['period'],number,tuple(item['case_codes']) or match[1])]=item
    return list(found.values())


def sinia_ogasa(latest=6):
    listing=_get('https://sinia.minam.gob.pe/taxonomy/term/146150')
    reports=sorted({(int(y),int(n),href) for href,n,y in re.findall(r'href="(/documentos/informe-ndeg-(\d+)-(\d{4})-ogasa[^"]*)"',listing)},reverse=True)[:latest]
    items,requests_made=[],1
    for year,number,href in reports:
        page=_get(urljoin('https://sinia.minam.gob.pe',href)); requests_made+=1
        pdf=re.search(r'href="([^"]+\.pdf)"',page)
        if not pdf:
            continue
        url=urljoin('https://sinia.minam.gob.pe',pdf[1]); requests_made+=1
        items+=_pdf_passages(url,{'title':f'Informe N.º {number:02d}-{year}-OGASA · conflictos socioambientales','period':f'{year}-{number:02d}',
                                  'connector':'SINIA · MINAM/OGASA','institution_key':'minam','document_url':urljoin('https://sinia.minam.gob.pe',href)})
        time.sleep(1)
    return items,requests_made


def _willaqniki_period(slug):
    """Bimonthly editions: month words when present, else edition number N -> month 2N (approximate)."""
    text=service.norm(slug.replace('-',' '))
    year=re.findall(r'(20\d{2})',text)
    if not year:
        return None
    months=[MONTHS[w] for w in re.findall(r'[a-z]+',text) if w in MONTHS]
    if months:
        return f'{year[-1]}-{months[-1]:02d}'
    roman={'i':1,'ii':2,'iii':3,'iv':4,'v':5,'vi':6}
    edition=re.search(r'(?:edicion|n) (\d{1,2}|vi|v|iv|iii|ii|i)\b',text)
    if edition:
        number=int(edition[1]) if edition[1].isdigit() else roman[edition[1]]
        return f'{year[-1]}-{min(12,2*number):02d}'
    return f'{year[-1]}-12'


def pcm_willaqniki(latest=4):
    listing=_get('https://www.gob.pe/institucion/pcm/colecciones/12-reporte-willaqniki')
    links=[(href,service.clean(re.sub(r'<[^>]+>','',label))) for href,label in re.findall(r'href="(/institucion/pcm/informes-publicaciones/\d+-[^"]*willaqniki[^"]*)"[^>]*>(.*?)</a>',listing,re.S)]
    links=list(dict(links).items())
    items,requests_made=[],1
    for href,name in links[:latest]:
        page=_get('https://www.gob.pe'+href); requests_made+=1
        pdf=re.search(r'(https://cdn\.www\.gob\.pe/uploads/document/file/\d+/(?!preview_)[^"?]+\.pdf)',page)
        if not pdf:
            continue
        period=_willaqniki_period(href.rsplit('/',1)[-1]+' '+name)
        requests_made+=1
        items+=_pdf_passages(pdf[1],{'title':name or 'Willaqniki','period_basis':'edición bimestral; mes aproximado','period':period or '0000-00','connector':'gob.pe · PCM Willaqniki','institution_key':'pcm',
                                     'document_url':'https://www.gob.pe'+href})
        time.sleep(1)
    return items,requests_made


def defensoria_pdf():
    """Monthly Defensoría reports already downloaded by service.sync_sources (PDF): passages per case."""
    items,documents=[],[d for d in service.list_documents() if d['format']=='pdf']
    for document in documents:
        path=service.DATA/'raw'/(document['sha256']+'.pdf')
        if path.exists():
            number=re.search(r'n-?(\d{3})',service.norm(document['title']))
            items+=_pdf_passages(document['url'],{'title':f"Reporte de Conflictos Sociales N.º {number[1] if number else ''} · Defensoría",'period':document['period'],
                                                  'connector':'Defensoría · reporte mensual (PDF)','institution_key':'defensoria'},path=path)
    return items,0


CONNECTORS={'defensoria':('Reportes mensuales de la Defensoría en PDF (historial)',defensoria_pdf),
            'gobpe':('Notas y comunicados oficiales (gob.pe)',gobpe),
            'ogasa':('Informes mensuales MINAM/OGASA (SINIA)',sinia_ogasa),
            'willaqniki':('Willaqniki · PCM (gob.pe)',pcm_willaqniki)}


def run(name):
    label,function=CONNECTORS[name]
    started=time.time()
    previous=load(name)
    try:
        items,requests_made=function()
        merged={i['id']:i for i in previous.get('items',[])}
        new=[i for i in items if i['id'] not in merged]
        merged.update({i['id']:i for i in items})
        result={'name':name,'label':label,'ok':True,'items':sorted(merged.values(),key=lambda i:(i.get('date') or i.get('period') or ''),reverse=True),
                'fetched':len(items),'new':len(new),'requests':requests_made,'error':None}
    except Exception as exc:
        result={**previous,'name':name,'label':label,'ok':False,'fetched':0,'new':0,'error':f'{type(exc).__name__}: {str(exc)[:160]}'}
    result.update({'checked_at':service.now(),'seconds':round(time.time()-started,1)})
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    (DIRECTORY/f'{name}.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')
    return result


def load(name):
    for path in (DIRECTORY/f'{name}.json',SEED/f'{name}.json'):
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return {'items':[]}


def all_items():
    """Items of every connector, re-classified with the current rules (fixes apply retroactively)."""
    items=[]
    for name in CONNECTORS:
        for item in load(name).get('items',[]):
            companies,cases,tags=news.classify({'title':item['title'],'snippet':item.get('quote') or item.get('snippet') or ''})
            if companies:
                items.append({**item,'companies':companies,'case_codes':cases,'tags':tags})
    return items


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    for name in (sys.argv[1:] or CONNECTORS):
        r=run(name)
        print(f"{name}: ok={r['ok']} items={len(r.get('items',[]))} nuevos={r['new']} solicitudes={r.get('requests')} {r['seconds']}s {r['error'] or ''}")
        for item in r.get('items',[])[:5]:
            print(f"   {item.get('date') or item['period']} {item['institution']} p.{item.get('page','-')} casos={item['case_codes']} {item['title'][:70]}")
