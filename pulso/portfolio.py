"""Carteras empresariales con observaciones y fuentes independientes de la interfaz."""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from datetime import datetime, timedelta, timezone
import html
import json
import re
import threading
import shutil

from bs4 import BeautifulSoup
from . import alerts as alert_rules, corpus, geoperu, news, service
from . import sources as connectors

DIRECTORY = service.DATA / 'portfolio'
LOCK = threading.Lock()
COMPANIES = {
    'mineria': {'id':'mineria','name':'Las Bambas','legal_name':'Minera Las Bambas S.A.', 'sector':'Minería', 'operation':'Las Bambas · corredor sur', 'region':'Apurímac y Cusco', 'description':'Seguimiento de comunidades y espacios de diálogo de la cartera seleccionada.', 'initials':'LB','color':'#087d6b'},
    'hidrocarburos': {'id':'hidrocarburos','name':'Petroperú','legal_name':'Petróleos del Perú – Petroperú S.A.', 'sector':'Hidrocarburos', 'operation':'ONP · vínculos documentados con el Lote 192', 'region':'Loreto', 'description':'Seguimiento de casos con mención empresarial expresa. La ficha identifica actores; no verifica por sí misma quién opera hoy cada activo.', 'initials':'PP','color':'#2563b9'}
}
TARGETS = {'1285-0622':'mineria','1229-0621':'mineria','1162-0819':'mineria','1132-1218':'mineria','1403-0325':'hidrocarburos'}


def _read(name, default=None):
    path = DIRECTORY / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def _text(node):
    return service.clean(node.get_text(' ',strip=True)) if node else ''


def _chips(card):
    result = {}
    for chip in card.select('.caso-chip'):
        label = _text(chip.select_one('.caso-chip-label')).rstrip(':')
        text = _text(chip)
        if label:
            result[label] = text[len(label):].lstrip(': ').strip()
    return result


def _fields(card):
    result = {}
    for field in card.select('.ficha-campo'):
        label = _text(field.select_one('.ficha-lbl')).rstrip(':')
        value = _text(field.select_one('.ficha-val'))
        if label:
            result[label] = value
    return result


def _location(text):
    patterns = {'district':r'distrito(?:s)?\s+de\s+(.+?)(?:,|\.|;|$)', 'province':r'provincia(?:s)?\s+de\s+(.+?)(?:,|\.|;|$)', 'region':r'departamento(?:s)?\s+de\s+(.+?)(?:,|\.|;|$)'}
    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern,text,re.I)
        result[key] = match[1].strip() if match else ''
    return result


def rebuild():
    """Rebuild from locally retained official HTML, not from model guesses."""
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    if not (DIRECTORY/'snapshot.json').exists():
        for path in (service.ROOT/'demo_data').glob('*.json'):
            if not (DIRECTORY/path.name).exists():
                shutil.copy2(path,DIRECTORY/path.name)
    documents = [d for d in service.list_documents() if d['format']=='html']
    if not documents:
        existing=_read('snapshot.json')
        if existing:
            return existing
        raise ValueError('Aún no se incorporó un reporte HTML con fichas estructuradas.')
    sources, by_case = {}, defaultdict(list)
    case_companies={}
    geocodes = _read('geocodes.json',{})
    supplementary=_read('supplementary.json',{'records':[],'newscases':[]})
    latest={}
    for document in documents:
        key=document['period']
        if key not in latest or document['ingested_at']>latest[key]['ingested_at']:
            latest[key]=document
    for document in sorted(latest.values(),key=lambda d:(d['period'],d['ingested_at'])):
        raw = service.DATA/'raw'/(document['sha256']+'.html')
        if not raw.exists():
            continue
        soup=BeautifulSoup(raw.read_bytes(),'html.parser')
        source_id='DP-'+(document['period'] or document['id'])
        sources[source_id]={'id':source_id,'institution':'Defensoría del Pueblo','title':document['title'], 'url':document['url'], 'date':None,'period':document['period'],'kind':'reporte oficial','method':'ficha HTML oficial','sha256':document['sha256'], 'review_status':'extracción estructurada; interpretación por revisar'}
        for card in soup.select('.caso-card[data-codigo]'):
            code=card.get('data-codigo')
            fields=_fields(card)
            primary=service.norm(fields.get('Actores primarios',''))
            company=TARGETS.get(code) or ('mineria' if 'las bambas' in primary else 'hidrocarburos' if 'petroperu' in primary else None)
            if not company:
                continue
            case_companies[code]=company
            chips=_chips(card)
            description=fields.get('Caso','') or _text(card.select_one('.caso-desc'))
            narrative=_text(card.select_one('.hechos-verbatim'))
            phase=_text(card.select_one('.badge')) or None
            dialogue=service.norm(_text(card.select_one('.dialogo-banner'))).startswith('hay dialogo')
            location=chips.get('Ubicación','')
            geo=_location(location)
            title_region=re.search(r'\(([^()]*)\)\s*$',_text(card.select_one('.caso-nombre')))
            if not geo['region'] and title_region:
                geo['region']=title_region[1]
            curated=next((r for r in supplementary['records'] if r['institution']=='Defensoría del Pueblo' and code in r.get('case_codes',[])),None)
            if curated:
                territory=curated.get('territory',{})
                for field,curation_key in [('region','department'),('province','province'),('district','district')]:
                    if territory.get(curation_key):
                        geo[field]=territory[curation_key]
            key=service.norm(geo['district']).upper()
            point=geocodes.get('HUANCUIRE' if code=='1229-0621' else key,{})
            page=next((p.get('id') for p in card.parents if str(p.get('id','')).startswith('page-')),None)
            by_case[code].append({'period':document['period'],'status':'Activo','phase':phase,'dialogue':dialogue,
                'description':description,'narrative':narrative,'location':location, **geo,
                'name':_text(card.select_one('.caso-nombre')),
                'source_id':source_id, 'source_anchor':page,
                'coordinates':point.get('coordinates'),'coordinate_precision':point.get('precision','sin georreferencia'),
                'phase_basis':'Clasificación de la ficha oficial del período, no predicción.',
                'demands':[{'text':description,'source_id':source_id,'status':'reclamos atribuidos por la fuente'}] if description else [],
                'actors_institutions':[name for name in ['OEFA','MINEM','MINAM','PNP','PCM','Defensoría'] if name.lower() in service.norm(' '.join(fields.values())).lower()]})
    if not by_case:
        raise ValueError('El formato del reporte no contiene las fichas esperadas; se conserva la última cartera.')
    for record in supplementary['records']:
        # Same report isn't another independent source just because it mentions two cases.
        if record['institution']=='Defensoría del Pueblo':
            continue
        sid=record['id']
        sources[sid]={'id':sid,'institution':record['institution'],'title':record['title'],'url':record['url'],
                     'date':record.get('date'),'period':record.get('period'),'kind':'prensa' if 'PRENSA' in sid or 'prensa' in record.get('institution','').lower() else 'comunicación institucional',
                     'method':'curación con fuente enlazada','review_status':'vínculo editorial identificado','link_basis':record.get('link_basis',''), 'claim_status':record.get('claim_status','reportado por la fuente')}
    snapshot={'schema_version':2,'built_at':service.now(),'companies':COMPANIES,'case_companies':case_companies,'observations':dict(by_case),'sources':list(sources.values()),
              'supplementary':supplementary,'author':'Alexander Noblejas'}
    path=DIRECTORY/'snapshot.json'
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
    return snapshot


LANES=['Defensoría','Ejecutivo','Fiscalización y agua','Policía','Empresa','Prensa']


def _lane(event,source):
    """Actor type of a source: lets the analyst compare framings (each institution sees through its function)."""
    if event.get('kind')=='prensa' or (source or {}).get('kind')=='prensa':
        return 'Prensa'
    text=service.norm((source or {}).get('institution','')+' '+(event.get('institution_key') or ''))
    for lane,pattern in [('Defensoría',r'defensor'),('Policía',r'\bpnp\b|polic'),('Fiscalización y agua',r'\boefa\b|\bana\b|autoridad nacional del agua|osinergmin|tribunal de fiscalizacion'),
                         ('Empresa',r'petroperu|las bambas|\bmmg\b'),('Ejecutivo',r'pcm|minem|minam|ministerio|mininter|minsa|pronis|vivienda|presidencia')]:
        if re.search(pattern,text):
            return lane
    return 'Ejecutivo'


def system_status():
    from . import pipeline
    connectors_status=[{'name':name,'label':label,'ok':data.get('ok'),'checked_at':data.get('checked_at'),'items':len(data.get('items',[])),
                        'new':data.get('new'),'error':data.get('error'),'requests':data.get('requests')}
                       for name,(label,_) in connectors.CONNECTORS.items() for data in [connectors.load(name)]]
    media=news.load()
    connectors_status.insert(0,{'name':'prensa','label':'Prensa (RSS)','ok':bool(media.get('feeds')),'checked_at':media.get('updated_at'),'items':len(media.get('items',[])),
                                'error':None,'requests':len(media.get('feeds',[]))})
    for company in COMPANIES:
        geo=geoperu.load(company)
        connectors_status.append({'name':f'geoperu-{company}','label':f'GEOPERÚ · {COMPANIES[company]["name"]}','ok':all(l.get('ok') for l in geo.get('layers',{}).values()),
                                  'checked_at':geo.get('fetched_at'),'items':sum(l.get('count',0) for l in geo.get('layers',{}).values()),'error':None,'requests':len(geo.get('layers',{}))})
    return {'runs':pipeline.load().get('runs',[])[:15],'connectors':connectors_status,
            'repository':'https://github.com/AlexNoblejas/pulso-territorial','actions':'https://github.com/AlexNoblejas/pulso-territorial/actions/workflows/pages.yml'}


def _snapshot():
    return _read('snapshot.json') or rebuild()


def historical(company):
    raw=_read('historical.json',{'cases':[]})
    # Lote 8/192 historical associations are not attributed to today's Petroperú.
    ids={64,553,585} if company=='mineria' else {133,428}
    selected=[c for c in raw['cases'] if c['historical_research_id'] in ids]
    monthly=defaultdict(lambda:{'active':0,'latent':0,'dialogue':0,'observed':0,'unclassified':0})
    for case in selected:
        for obs in case['observations']:
            item=monthly[obs['period']]
            item['observed']+=1
            status=service.norm(obs.get('status') or '')
            if status=='activo': item['active']+=1
            elif status=='latente': item['latent']+=1
            else: item['unclassified']+=1
            if service.norm(obs.get('dialogue_status_text') or '').strip().startswith('hay dialogo'):
                item['dialogue']+=1
    series=[{'period':period,**value} for period,value in sorted(monthly.items())]
    for row in series:
        if row['unclassified']==row['observed']:
            row['active']=None
            row['latent']=None
    # Strip workstation paths from API responses while retaining workbook/row provenance.
    sanitized=_sanitize_paths(json.loads(json.dumps(selected)))
    for case in sanitized:
        for obs in case['observations']:
            provenance=obs.get('provenance',{})
            if provenance.get('file'):
                provenance['file']=Path(provenance['file']).name
            obs.pop('report_reference_metadata',None)
    return sanitized,series


def _sanitize_paths(value):
    if isinstance(value,list):
        return [_sanitize_paths(item) for item in value]
    if isinstance(value,dict):
        return {k:_sanitize_paths(v) for k,v in value.items()}
    if isinstance(value,str) and re.match(r'^[A-Za-z]:[\\/]',value):
        return value.replace('\\','/').rsplit('/',1)[-1]
    return value


def portfolio(company='mineria',period=None):
    if company not in COMPANIES:
        raise ValueError('Selecciona una de las dos carteras de demostración.')
    snap=_snapshot()
    observations=snap['observations']
    mapping=snap.get('case_companies',TARGETS)
    periods=sorted({o['period'] for code,items in observations.items() if mapping.get(code)==company for o in items},reverse=True)
    selected_period=period or periods[0]
    if selected_period not in periods:
        raise ValueError('No hay una observación estructurada para ese período.')
    sources={s['id']:s for s in snap['sources']}
    library=corpus.load()
    for doc_id,document in library['documents'].items():
        source=sources.setdefault(doc_id,{'id':doc_id,'institution':document['institution'],'title':document['title'],'url':document['url'],
                                          'date':document['date'],'period':document['period'],'kind':'informe institucional',
                                          'method':'pasaje literal verificado con pypdf','review_status':'texto y página comprobados'})
        source.update({'pdf_url':document['pdf_url'],'sha256':document['sha256'],'url_kind':document['url_kind'],'pages':document['pages']})
    cases=[]
    for code,items in observations.items():
        if mapping.get(code)!=company:
            continue
        matching=[o for o in items if o['period']==selected_period]
        if not matching:
            continue
        obs=matching[-1]
        events=[]
        if obs['narrative']:
            events.append({'date':None,'period':selected_period,'title':'Hechos del período · Defensoría','summary':obs['narrative'],'source_id':obs['source_id'],'kind':'reporte oficial','relation':'ficha oficial del caso'})
        source_ids=[obs['source_id']]
        for record in snap['supplementary']['records']:
            if record['institution']=='Defensoría del Pueblo' or code not in record.get('case_codes',[]) or record.get('period','9999')>selected_period:
                continue
            sid=record['id']
            source_ids.append(sid)
            events.append({'date':record.get('event_date') or record.get('date'),'period':record['period'],'title':record['title'],'summary':record['claim'],'source_id':sid,'kind':sources[sid]['kind'],'relation':record.get('link_basis','vinculación editorial al expediente territorial'),'claim_status':record.get('claim_status','información reportada')})
        for passage in library['passages']:
            document=library['documents'][passage['document_id']]
            if code not in passage['case_codes'] or (document['period'] or '0000')>selected_period:
                continue
            source_ids.append(document['id'])
            events.append({'date':document['date'],'period':document['period'],'title':passage['title'],'summary':passage['quote'],'source_id':document['id'],
                           'kind':'informe institucional','relation':passage['relation'],'claim_status':'cita literal',
                           'page':passage['page'],'pdf_url':passage['pdf_url'],'literal':True})
        cases.append({'id':code,'official_code':code,'company_id':company,**{k:obs[k] for k in ['name','region','province','district','status','phase','phase_basis','coordinates','coordinate_precision','location']},
                      'dialogue':obs['dialogue'],'summary':obs['description'],'demands':obs['demands'],
                      'commitments':[], 'commitments_note':'No se han consolidado compromisos individuales con responsable y plazo verificables.',
                      'events':sorted(events,key=lambda e:e.get('date') or e['period'],reverse=True),
                      'source_ids':list(dict.fromkeys(source_ids)),
                      'observations':[{k:o[k] for k in ['period','status','phase','dialogue','source_id']} for o in items],
                      'review_status':'ficha oficial extraída; vínculos adicionales curados','source_anchor':obs.get('source_anchor'),
                      'company_relation':'Mención empresarial expresa en el expediente; el operador y las obligaciones se verifican por activo.'})
    # Press is the daily pulse between monthly official reports; older periods only see older notes.
    media=news.load()
    company_items=[i for i in media['items'] if company in i['companies'] and (selected_period==periods[0] or i['published'][:7]<=selected_period)]
    for case in cases:
        for item in [i for i in company_items if case['id'] in i['case_codes']][:6]:
            sid='NEWS-'+item['id']
            sources[sid]={'id':sid,'institution':item['outlet'],'title':item['title'],'url':item['url'],'date':item['published'][:10],
                          'period':item['published'][:7],'kind':'prensa','method':'RSS del medio','review_status':'mención en prensa · no verificada'}
            case['source_ids'].append(sid)
            case['events'].append({'date':item['published'][:10],'period':item['published'][:7],'title':item['title'],
                                   'summary':item['snippet'] or 'Nota de prensa que menciona el caso.','source_id':sid,'kind':'prensa',
                                   'relation':'mención en prensa · no verificada','claim_status':'reportado por el medio','tags':item['tags']})
        case['events'].sort(key=lambda e:e.get('date') or e['period'],reverse=True)
    weeks=defaultdict(Counter)
    for item in company_items:
        day=datetime.fromisoformat(item['published']).date()
        weeks[(day-timedelta(days=day.weekday())).isoformat()][item['tags'][0]]+=1
    media_summary={'updated_at':media.get('updated_at'),'total':len(company_items),'items':company_items[:40],
                   'outlets':Counter(i['outlet'] for i in company_items).most_common(),
                   'weekly':[{'week':w,'counts':dict(c),'total':sum(c.values())} for w,c in sorted(weeks.items())][-12:],
                   'feeds_ok':sum(f['ok'] for f in media.get('feeds',[])),'feeds':len(media.get('feeds',[])),
                   'method':media.get('method','')}
    official_items=[i for i in connectors.all_items() if company in i['companies'] and (selected_period==periods[0] or (i.get('date') or i.get('period') or '')[:7]<=selected_period)]
    for case in cases:
        for item in [i for i in official_items if case['id'] in i['case_codes']][:30]:
            sid='OF-'+item['id']
            page_url=item['url']+f"#page={item['page']}" if item.get('page') else None
            sources[sid]={'id':sid,'institution':item['institution'],'title':item['title'],'url':item.get('document_url') or item['url'],'pdf_url':page_url,
                          'date':item.get('date'),'period':item.get('period'),'kind':'informe institucional' if item.get('literal') else 'comunicación institucional',
                          'method':item['connector'],'review_status':'extracción automática; revisar alcance'}
            case['source_ids'].append(sid)
            case['events'].append({'date':item.get('date'),'period':item.get('period'),'title':item['title'],'summary':item.get('quote') or item.get('snippet') or '',
                                   'source_id':sid,'kind':sources[sid]['kind'],'relation':'el caso se nombra en la fuente · extracción automática','literal':bool(item.get('literal')),
                                   'page':item.get('page'),'pdf_url':page_url,'tags':item.get('tags',[]),'institution_key':item.get('institution_key'),'automatic':True})
        for event in case['events']:
            event['lane']=_lane(event,sources.get(event.get('source_id')))
        case['events'].sort(key=lambda e:e.get('date') or e['period'] or '',reverse=True)
        case['territory']=geoperu.context(company,case.get('coordinates'),case.get('coordinate_precision',''),case['name'])
    linked={i['id'] for i in official_items if i['case_codes']}
    state_actions=[{**i,'lane':_lane(i,{'institution':i['institution']})} for i in official_items if i['id'] not in linked and i.get('institution_key')!='defensoria']
    state_actions=sorted(state_actions,key=lambda i:i.get('date') or i.get('period') or '',reverse=True)[:60]
    selected_ids={sid for c in cases for sid in c['source_ids']}
    selected_sources=[sources[sid] for sid in selected_ids]
    historical_cases,series=historical(company)
    annotation_file=service.ROOT/'config'/'case_annotations.json'
    annotations=json.loads(annotation_file.read_text(encoding='utf-8')) if annotation_file.exists() else {}
    milestones=[]
    for case in cases:
        if annotations.get('period')==selected_period and annotations.get('source_sha256')==sources[case['source_ids'][0]].get('sha256'):
            annotation=annotations.get('cases',{}).get(case['id'],{})
            if annotation:
                case['original_description']=case['summary']
                case['summary']=annotation['summary']
                case['summary_method']=annotations['method']
                case['demands']=[{'text':text,'source_id':case['source_ids'][0],'status':'Síntesis atribuida a la fuente'} for text in annotation['demands']]
                case['commitments']=annotation['commitments']
                case['commitments_note']='Acuerdos reportados; sin verificación automática de cumplimiento.'
                milestones.extend({'case_id':case['id'],'case_name':case['name'],**item} for item in case['commitments'] if item.get('due_date'))
        match=next((h for h in historical_cases if h.get('official_case_code_candidate')==case['id']),None)
        if match:
            case['historical_observations']=match['observations']
            case['historical_link_note']='Empate por código candidato y denominación del archivo histórico. Clasificaciones importadas; no se tratan como nuevas fases oficiales.'
    matrix=[]
    for institution in ['Defensoría del Pueblo','OEFA','MINAM','MINEM','PCM','PNP','ANA','Vivienda','Prensa']:
        aliases={'ANA':['autoridad nacional del agua'],'Vivienda':['ministerio de vivienda']}
        matches=[s for s in selected_sources if institution.lower() in s['institution'].lower() or any(a in s['institution'].lower() for a in aliases.get(institution,[])) or (institution=='Prensa' and s['kind']=='prensa')]
        matrix.append({'institution':institution,'count':len(matches),'status':'directa' if matches else 'sin_fuente_directa',
                       'note':'Fuente vinculada al expediente; revisar alcance de cada afirmación.' if matches else 'Sin publicación directa incorporada para esta cartera; una mención como actor no cuenta como fuente.'})
    insights=[]
    curated_current=any(annotations.get('source_sha256')==source.get('sha256') for source in selected_sources)
    if not curated_current:
        insights.append({'type':'seguimiento','title':'Nueva versión documental por revisar','text':'La ficha conserva el texto y la fase de la versión más reciente. Las síntesis y comparaciones editoriales anteriores no se aplican automáticamente a un documento modificado.','case_id':cases[0]['id'] if cases else None,'source_ids':list(selected_ids)})
    elif company=='hidrocarburos':
        insights.append({'type':'discrepancia','title':'Una fecha que las fuentes no cuentan igual','text':'El relato histórico del RCS 271 consigna 19 de febrero de 2025; OEFA y MINAM sitúan el derrame de referencia el 19 de marzo. Las emergencias de marzo y mayo se mantienen como acontecimientos distintos.','case_id':'1403-0325','source_ids':['DP-2026-09','PP-OEFA-20250319','PP-MINAM-202503']})
        insights.append({'type':'seguimiento','title':'Agua: una entrega no acredita continuidad del servicio','text':'Vivienda documenta la entrega de una cisterna en mayo de 2026; la ficha de septiembre recoge reclamos sobre regularidad del abastecimiento. Son alcances diferentes que requieren seguimiento.','case_id':'1403-0325','source_ids':['DP-2026-09','PP-VIVIENDA-20260513']})
    else:
        insights.append({'type':'seguimiento','title':'El diálogo convive con reclamos documentados','text':'La fase oficial describe un momento del proceso. No implica que las demandas o acuerdos estén resueltos. Consulta cada ficha antes de atribuir una obligación.','case_id':'1229-0621','source_ids':['DP-2026-09']})
        insights.append({'type':'contexto','title':'Huancuire: geografía y jurisdicción requieren conciliación','text':'El reporte ubica el caso en Coyllurqui; la copia local del polígono comunal tiene Challhuahuacho como atributo. El mapa conserva la precisión de cada fuente y no corrige esa diferencia automáticamente.','case_id':'1229-0621','source_ids':['DP-2026-09']})
    alert_list=alert_rules.compute(cases,company_items,official_items,insights)
    geo=_read(f'geography_{company}.json',{})
    phases=Counter(c['phase'] or 'Sin fase reportada' for c in cases)
    return {'company':COMPANIES[company],'period':selected_period,'periods':periods,'author':snap['author'],
            'summary':{'cases':len(cases),'active':sum(c['status']=='Activo' for c in cases),'latent':sum(c['status']=='Latente' for c in cases),'dialogue':sum(c['dialogue'] for c in cases),'sources':len(selected_sources),'observations':sum(len(c['observations']) for c in cases),'historical_observations':sum(len(c['observations']) for c in historical_cases)},
            'cases':cases,'sources':sorted(selected_sources,key=lambda s:s['institution']),'source_matrix':matrix,'insights':insights,'milestones':sorted(milestones,key=lambda m:m['due_date']),
            'phase_distribution':dict(phases),'historical_series':series,'historical_cases':historical_cases,
            'related_news':[r for r in snap['supplementary'].get('newscases',[]) if company=='mineria']+
                           [{'id':s['document_id']+f"-p{s['page']}",'institution':library['documents'][s['document_id']]['institution'],'title':s['title'],
                             'claim':s['claim'],'quote':s['quote'],'page':s['page'],'pdf_url':s['pdf_url'],'url':library['documents'][s['document_id']]['url'],
                             'date':library['documents'][s['document_id']]['date']} for s in library['signals'] if s['company']==company],
            'corpus_problems':library['problems'],'media':media_summary,'alerts':alert_list,'alert_summary':alert_rules.summary(alert_list),'alert_rules':alert_rules.RULES,
            'state_actions':state_actions,'lanes':LANES,'lenses':{k:dict(zip(['institution','role','lens'],v)) for k,v in connectors.INSTITUTIONS.items()},'system':system_status(),
            'geography':{k:geo.get(k) for k in ['center','zoom','extent','metadata','map_style_url','terrain_url']},
            'coverage':{'period_label':'Setiembre de 2026' if selected_period=='2026-09' else selected_period,'built_at':snap['built_at'],'current_source':'RCS 271 · fichas estructuradas oficiales',
                        'scope':'Cartera piloto de casos seleccionados, no totalidad de conflictos de la empresa ni del país.',
                        'historical_status':'Base de investigación importada; dos pasajes cotejados, resto pendiente de auditoría. No se imputan meses ni operadores actuales.',
                        'interpretation':'Lectura documental editorial; generación IA opcional, nunca chatbot obligatorio.',
                        'updated_documents':service.stats()['documents'], 'realtime':False,
                        'ai_available':any(service.provider_status().values()),'ai_provider':next((k for k,v in service.provider_status().items() if v),'groq')},
            'providers':service.provider_status()}


def geography(company):
    if company not in COMPANIES:
        raise ValueError('Cartera no válida.')
    data=_read(f'geography_{company}.json',{})
    data['geoperu']=geoperu.load(company)
    return data


def visual_report(company,period=None):
    from .reports import create_report
    return create_report(portfolio(company,period),geography(company))

