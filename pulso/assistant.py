"""Lore: retrieval from the selected portfolio, real source locators and bounded UI actions."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from . import portfolio, service

STOP = set('que quien quienes cual cuales como cuando donde para por con del los las una unos unas este esta estos estas esos sobre puedes podria podrias favor quiero saber dime explica explicame respuesta informacion tiene tienen tengo hay caso casos conflicto conflictos empresa'.split())
VIEWS = {'resumen','alertas','territorio','conflictos','pais','fuentes','reportes','sistema'}


def words(value):
    return {w for w in re.findall(r'\w+',service.norm(value)) if len(w)>2 and w not in STOP}


def safe_source_url(value):
    if not isinstance(value,str):
        return ''
    parsed=urlsplit(value)
    if parsed.scheme in {'https','http'} and parsed.hostname and not parsed.username:
        return value
    if parsed.scheme or parsed.netloc or '\\' in value or '..' in parsed.path.split('/'):
        return ''
    if re.fullmatch(r'/?corpus/[^/]+\.pdf',parsed.path,re.I):
        return value
    return ''


def navigation(question,p):
    q=service.norm(question).strip()
    if not re.match(r'^(?:abre|abrir|muestra(?:me)?|mostrar|lleva(?:me)?|ve a|ir a|quiero ver|ver)\b',q):
        return []
    matches=[]
    for case in p.get('cases',[]):
        terms=words(case['name'])-{'minera','sociambiental','social','socioambiental','comunidad','campesina'}
        score=len(terms & words(q))
        if case['id'] in q or score:
            matches.append((score,case['id']))
    if matches:
        matches.sort(reverse=True)
        if len(matches)==1 or matches[0][0]>matches[1][0]:
            return [{'type':'open_case','case_id':matches[0][1]}]
    for pattern,view in [(r'alertas?','alertas'),(r'mapa|territorio','territorio'),(r'reportes?|informe mensual','reportes'),(r'fuentes?|documentos','fuentes'),(r'estado del sistema|bitacora','sistema'),(r'pais|nacional','pais'),(r'conflictos?','conflictos'),(r'resumen|inicio','resumen')]:
        if re.search(r'\b(?:'+pattern+r')\b',q):
            return [{'type':'navigate','view':view}]
    return []


def candidates(p):
    sources={str(s['id']):s for s in p.get('sources',[])}
    result=[]
    for case in p.get('cases',[]):
        primary=sources.get(str((case.get('source_ids') or [''])[0]),{})
        raw=case.get('original_description') or case.get('summary','')
        actor_fields=case.get('actors',{})
        actors='\n'.join(f'{kind}: {value}' for kind,value in actor_fields.items() if isinstance(value,str) and value.strip())
        official=[event.get('summary','') for event in case.get('events',[]) if event.get('kind')=='reporte oficial']
        content=case['name']+'\n'+actors+'\n\n'+raw+'\n\n'+'\n'.join(official)
        if content.strip():
            result.append({'document_id':primary.get('id',case['id']), 'page':None,'method':'ficha_html_oficial', 'text':content,
                'case_id':case['id'],'case_name':case['name'],'title':primary.get('title',case['name']),
                'institution':primary.get('institution','Defensoría del Pueblo'), 'url':safe_source_url(primary.get('url','')),
                'locator':'Ficha del caso '+case['id'],'kind':'ficha oficial','period':p.get('period')})
        for event in case.get('events',[]):
            # Do not turn a news headline, alert or editorial paraphrase into a literal PDF source.
            if not event.get('literal') or not isinstance(event.get('page'),int) or event['page']<1:
                continue
            source=sources.get(str(event.get('source_id')), {})
            result.append({'document_id':event.get('source_id'), 'page':event['page'],'method':'pdf_pypdf','text':event.get('summary',''),
                'case_id':case['id'],'case_name':case['name'],'title':event.get('title') or source.get('title', 'Informe institucional'),
                'institution':source.get('institution', event.get('institution_key','Fuente institucional')),
                'url':safe_source_url(event.get('pdf_url') or source.get('url','')),
                'locator':f"Página PDF {event['page']}", 'kind':'pasaje PDF literal', 'period':event.get('period')})
    return result


def retrieve(question,p,limit=4):
    terms=words(question)
    if not terms:
        return []
    found=[]
    for item in candidates(p):
        content=words(item['text'])
        name=words(item['case_name'])
        score=len(terms&content)+4*len(terms&name)
        if score:
            found.append((score,item))
    found.sort(key=lambda x:-x[0])
    unique=[]
    seen=set()
    for _,item in found:
        key=(item['document_id'],item['page'],item['text'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique)>=limit:break
    return unique


def answer(question,company='antamina',view=None,period=None,case_id=None):
    if not isinstance(question,str) or not question.strip():
        raise ValueError('Escribe una pregunta sobre la cartera.')
    question=question.strip()[:400]
    p=portfolio.portfolio(company,period)
    if case_id:
        selected=[c for c in p.get('cases',[]) if c['id']==case_id]
        if not selected:
            raise ValueError('El expediente seleccionado no pertenece a esta cartera y período.')
        p={**p,'cases':selected}
    actions=navigation(question,p)
    if actions:
        return {'answer':'Puedes abrir la selección solicitada dentro de tu cartera.','records':[],'sources':[], 'actions':actions,'mode':'navegación de lectura','model':None,'usage':{}}
    hits=retrieve(question,p)
    if not hits:
        return {'answer':'No encontré evidencia suficiente en esta cartera para responder. Indica el nombre de un caso o el tema que quieres revisar.','records':[],'sources':[],'actions':[],'mode':'sin evidencia','model':None,'usage':{}}
    provider=next((k for k,v in service.provider_status().items() if v),None)
    if not provider:
        raise ValueError('No hay un proveedor de IA configurado en el servidor local.')
    service.init_db()
    task=('Responde la pregunta usando sólo la evidencia seleccionada: '+question+
          '\nFormato {"records":[{"type":"respuesta","claim":"afirmación breve atribuida a la fuente","quote":"cita literal suficiente","source_id":"E1"}]}. '
          'Distingue fechas y organismos. No conviertas una actuación preventiva en fase del conflicto ni una denuncia en un hecho probado. '
          'No infieras vigencia o cumplimiento. Si falta respaldo devuelve records vacío.')
    parsed,model,usage,context=service._call(provider,task,hits)
    records,rejected=service.validate_records(parsed,context)
    refs=[]
    used={r['source_id'] for r in records}
    for i,item in enumerate(hits,1):
        sid=f'E{i}'
        if sid in used:
            refs.append({k:item[k] for k in ['title','institution','url','locator','kind','period','case_id']}|{'id':sid,'page':item['page']})
    text='\n\n'.join(f"{r['claim']} [{r['source_id']}]" for r in records)
    return {'answer':text or 'No obtuve una respuesta respaldada por citas válidas en los documentos seleccionados.',
            'records':records,'sources':refs,'actions':[], 'model':model,'usage':usage,'rejected':rejected,
            'scope':'Cartera seleccionada; fichas originales y pasajes PDF. La coincidencia literal no sustituye revisión semántica.'}
