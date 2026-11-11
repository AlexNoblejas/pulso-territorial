"""Monitoreo de medios: RSS de El Comercio, La República, Andina y Google News.

Reutiliza la estrategia de la tarea 1 (sesión 03): sólo RSS y sitemaps permitidos por robots.txt,
User-Agent académico, pausas y un reintento. Se guarda titular, medio, fecha, enlace y un extracto
breve del feed; nunca el artículo completo.
Ejecutar: python -m pulso.news
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import hashlib
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

from . import service

USER_AGENT='PulsoTerritorial/0.2 (proyecto academico QLAB PUCP; contacto via GitHub AlexNoblejas)'
FEEDS=[('El Comercio','https://elcomercio.pe/arc/outboundfeeds/rss/?outputType=xml'),
       ('El Comercio','https://elcomercio.pe/arc/outboundfeeds/google-news-feed/category/peru/?outputType=xml'),
       ('El Comercio','https://elcomercio.pe/arc/outboundfeeds/google-news-feed/category/economia/?outputType=xml'),
       ('La República','https://larepublica.pe/rss/sociedad.xml'),
       ('La República','https://larepublica.pe/rss/economia.xml'),
       ('Andina','https://andina.pe/agencia/rss/3.xml')]
# Google News agrega otros medios (RPP, Gestión, Infobae, regionales) por consulta.
SEARCHES={'antamina':['Antamina comunidad','Antamina conflicto','"Punta Lobitos" Huarmey','Antamina Llata OR Aquia OR "San Marcos"'],
          'mineria':['"Las Bambas"','Fuerabamba','Challhuahuacho','"corredor minero" Apurímac'],
          'hidrocarburos':['Petroperú derrame','"Oleoducto Norperuano"','"Sinchi Roca" OR Pijuayal','"Lote 192"']}
KEYWORDS={'antamina':['antamina','punta lobitos'],
          'mineria':['las bambas','fuerabamba','chuicuni','huancuire','challhuahuacho','cotabambas','corredor minero','mmg'],
          'hidrocarburos':['petroperu','oleoducto norperuano','oleoducto','pijuayal','lote 192','manseriche','datem del maranon','altamesa','andoas']}
CASES={'llata':'1333-0923','fuerabamba':'1132-1218','chuicuni':'1285-0622','huancuire':'1229-0621','corredor minero':'1162-0819',
       'sinchi roca':'1403-0325','pijuayal':'1403-0325','manseriche':'1403-0325','altamesa':'1459-1125'}
CASE_COMPANY={'1333-0923':'antamina','1132-1218':'mineria','1285-0622':'mineria','1229-0621':'mineria','1162-0819':'mineria','1403-0325':'hidrocarburos','1459-1125':'hidrocarburos'}
# Homonyms: a name only links to the case when an anchor term appears in the same text.
# (e.g. there is a CN Sinchi Roca in Huánuco with an unrelated conflict).
ANCHORS={'llata':['antamina','huamalies','fredill'],
         'sinchi roca':['manseriche','datem','oleoducto','petroperu','derrame','pijuayal','loreto'],
         'corredor minero':['las bambas','apurimac','cotabambas','mara','mmg','chumbivilcas'],
         'pijuayal':['manseriche','datem del maranon','oleoducto norperuano']}
# A shared community name is insufficient when the text identifies another place or sport.
CASE_EXCLUSIONS={'pijuayal':['iparia','ucayali'],
                 'fuerabamba':['linfa','patibamba','futbol','copa peru']}
TAGS=[('Medida de fuerza',r'bloque|paro\b|protest|moviliz|toma de|marcha'),
      ('Violencia',r'enfrentamiento|herid|fallec|muert|detenid'),
      ('Diálogo y acuerdos',r'di[aá]logo|mesa de|acuerdo|acta\b|convenio|reuni[oó]n'),
      ('Ambiental',r'derrame|contamina|oefa|ambiental|agua'),
      ('Seguridad',r'robo|clandestin|pnp|polic|delito|atentado'),
      ('Estado de emergencia',r'estado de emergencia'),
      ('Operación y producción',r'producci[oó]n|cobre|exporta|inversi[oó]n|operaci[oó]n')]
WINDOW_DAYS=120
PATH=service.DATA/'news.json'
SEED=service.ROOT/'demo_data'/'news.json'


def _get(url):
    for attempt in range(2):
        try:
            response=requests.get(url,headers={'User-Agent':USER_AGENT},timeout=(10,30))
            if response.status_code==200:
                return response.content
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


def _text(value,limit=None):
    value=re.sub(r'<[^>]+>',' ',html.unescape(value or ''))
    value=re.sub(r'\s+',' ',value).strip()
    return value if not limit or len(value)<=limit else value[:limit].rsplit(' ',1)[0]+'…'


def _date(value):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError,ValueError):
        try:
            return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
        except (AttributeError,ValueError):
            return None


def parse(content,outlet,feed):
    """Items of an RSS document; Google News carries the real outlet in <source>."""
    items=[]
    for item in ET.fromstring(content).iter('item'):
        title=_text(item.findtext('title'))
        link=(item.findtext('link') or '').strip()
        source=item.find('source')
        name=_text(source.text) if source is not None and source.text else outlet
        if name!=outlet and title.endswith(' - '+name):
            title=title[:-len(name)-3]
        published=_date(item.findtext('pubDate') or item.findtext('{http://purl.org/dc/elements/1.1/}date'))
        if title and link.startswith('http') and published:
            snippet=_text(item.findtext('description'),220)
            items.append({'title':title,'url':link,'outlet':name,'published':published.isoformat(timespec='minutes'),
                          'snippet':'' if service.norm(snippet).startswith(service.norm(title)[:40]) else snippet,'feed':feed})
    return items


def classify(item):
    text=service.norm(item['title']+' '+item['snippet'])
    found=lambda word:re.search(r'\b'+re.escape(word)+r'\b',text)
    excluded={word for word,terms in CASE_EXCLUSIONS.items() if found(word) and any(found(term) for term in terms)}
    cases=sorted({code for word,code in CASES.items() if found(word) and word not in excluded and (word not in ANCHORS or any(found(a) for a in ANCHORS[word]))})
    # Ambiguous excluded names alone must not imply that the company is involved either.
    companies=[c for c,words in KEYWORDS.items() if any(w not in excluded and found(w) for w in words) or any(CASE_COMPANY[code]==c for code in cases)]
    tags=[name for name,pattern in TAGS if re.search(pattern,text)] or ['Contexto']
    return companies,cases,tags


def collect(pause=1.0):
    sources=[(outlet,url) for outlet,url in FEEDS]
    sources+=[('Google News',f'https://news.google.com/rss/search?q={quote_plus(q)}&hl=es-419&gl=PE&ceid=PE:es-419')
              for queries in SEARCHES.values() for q in queries]
    found,report=[],[]
    for outlet,url in sources:
        content=_get(url)
        try:
            items=parse(content,outlet,url) if content else []
        except ET.ParseError:
            items=[]
        report.append({'feed':url,'ok':content is not None,'items':len(items)})
        found+=items
        time.sleep(pause)
    return found,report


def update(pause=1.0):
    previous=load()
    found,report=collect(pause)
    cutoff=(datetime.now(timezone.utc)-timedelta(days=WINDOW_DAYS)).isoformat()
    merged,seen_titles={},set()
    for item in found+previous['items']:
        companies,cases,tags=classify(item)
        title_key=service.norm(item['title'])[:90]
        if not companies or item['published']<cutoff or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        key=hashlib.sha256(item['url'].encode()).hexdigest()[:16]
        merged.setdefault(key,{**item,'id':key,'companies':companies,'case_codes':cases,'tags':tags,
                               'first_seen':item.get('first_seen') or service.now()})
    items=sorted(merged.values(),key=lambda i:i['published'],reverse=True)
    data={'updated_at':service.now(),'window_days':WINDOW_DAYS,'feeds':report,'items':items,
          'method':'RSS y sitemaps permitidos; titular, fecha, medio, enlace y extracto breve del feed. Etiquetas por reglas, no verificadas.'}
    PATH.parent.mkdir(parents=True,exist_ok=True)
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data


def load():
    for path in (PATH,SEED):
        if path.exists():
            data=json.loads(path.read_text(encoding='utf-8'))
            items=[]
            for item in data.get('items',[]):
                companies,cases,tags=classify(item)
                if companies:
                    items.append({**item,'companies':companies,'case_codes':cases,'tags':tags})
            return {**data,'items':items}
    return {'updated_at':None,'items':[],'feeds':[]}


def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    data=update()
    print(f"{len(data['items'])} notas en la ventana de {WINDOW_DAYS} días · {sum(f['ok'] for f in data['feeds'])}/{len(data['feeds'])} feeds respondieron")
    for company in KEYWORDS:
        mine=[i for i in data['items'] if company in i['companies']]
        print(f'  {company}: {len(mine)} notas · con caso: {sum(bool(i["case_codes"]) for i in mine)}')
        for item in mine[:4]:
            print(f"    {item['published'][:10]} {item['outlet']}: {item['title'][:90]} {item['tags']}")


if __name__=='__main__':
    main()
