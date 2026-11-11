"""Alertas tempranas por reglas explícitas y auditables.

Cada alerta dice qué regla la disparó y enlaza su evidencia. No predice conflictos: señala hechos
reportados que conviene gestionar a tiempo (medidas de fuerza, plazos, brechas de información,
discrepancias entre fuentes que pueden derivar en errores de comunicación).
"""
from collections import Counter
from datetime import date, timedelta
import re
from urllib.parse import urlsplit

SEVERITY={'alta':3,'media':2,'baja':1}
RULES={
    'violencia':'Nota de prensa u oficial con hechos de violencia en los últimos 21 días.',
    'medida':'Nota de prensa u oficial con medida de fuerza (paro, bloqueo, toma, movilización) en los últimos 21 días.',
    'seguridad':'Incidente de seguridad (robo, atentado, intervención policial) en la operación o su infraestructura en los últimos 21 días.',
    'emergencia':'Mención de estado de emergencia en los últimos 30 días.',
    'pico':'Las notas de los últimos 14 días duplican el promedio quincenal de las 8 semanas previas (mínimo 4 notas).',
    'plazo':'Compromiso reportado con fecha en los próximos 30 días.',
    'vencido':'Compromiso con fecha vencida y sin ningún registro posterior en el expediente.',
    'brecha':'Hay actividad en prensa en los últimos 30 días y ninguna fuente oficial sobre el caso en 45 días.',
    'fase':'La fase oficial del período es escalamiento o crisis.',
    'sin_cierre':'Conflicto histórico que figuraba activo o latente en su último registro y dejó de reportarse sin cierre (resuelto, retirado o fusionado).',
    'discrepancia':'Dos fuentes reportan el mismo hecho con datos distintos: riesgo de error de comunicación.',
}


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:7]+'-01')
        except ValueError:
            return None


def _source_ids(item):
    multiple=item.get('source_ids') or []
    values=[item.get('source_id')]+([multiple] if isinstance(multiple,str) else list(multiple))
    return list(dict.fromkeys(v for v in values if isinstance(v,str) and v))


def _evidence_url(value,source):
    """Keep existing public URLs; local PDFs must belong to this verified source."""
    if not isinstance(value,str) or not value:
        return None
    try:
        parts=urlsplit(value)
    except ValueError:
        return None
    if parts.scheme in {'https','http'} and parts.netloc:
        return value
    match=re.fullmatch(r'corpus/([A-Za-z0-9][A-Za-z0-9_.-]*\.pdf)(?:#page=([1-9][0-9]{0,5}))?',value)
    registered=(source.get('pdf_url') or '').split('#')[0]
    if not match or value.split('#')[0]!=registered or not isinstance(source.get('pages'),int):
        return None
    if match[2] and int(match[2])>source['pages']:
        return None
    return value


def _evidence(event,sources):
    source=sources.get(event.get('source_id'),{})
    candidates=[event.get('pdf_url'),event.get('url'),source.get('pdf_url'),source.get('url')]
    url=next((valid for candidate in candidates if (valid:=_evidence_url(candidate,source))),None)
    if not url:
        return None
    page=event.get('page') or source.get('page')
    if type(page) is not int or page<1 or (isinstance(source.get('pages'),int) and page>source['pages']):
        page=None
    return {'title':event.get('title') or source.get('title'),'url':url,
            'date':event.get('date') or event.get('period') or event.get('published') or source.get('date') or source.get('period'),
            'institution':event.get('institution') or event.get('outlet') or source.get('institution'),
            'source_id':event.get('source_id'),'page':page}


def compute(cases,media_items,official_items,insights,today=None,history=(),sources=None):
    today=today or date.today()
    sources=sources or {}
    if not isinstance(sources,dict):
        sources={s['id']:s for s in sources}
    alerts=[]
    def references(item,case=None):
        rows=[]
        for sid in _source_ids(item):
            matches=[e for e in (case or {}).get('events',[]) if e.get('source_id')==sid
                     and (not item.get('page') or e.get('page')==item['page'])]
            # A source may also have a curated summary event. Prefer its existing original-page link.
            event=next((e for e in matches if e.get('pdf_url') and e.get('page')),None) or next(iter(matches),None)
            rows.append(event or {'source_id':sid,'page':item.get('page')})
        return rows
    def add(rule,severity,title,detail,case=None,evidence=()):
        resolved,missing,seen=[],[],set()
        for item in evidence:
            ids=_source_ids(item)
            expanded=[{**item,'source_id':sid} for sid in ids] if ids else [item]
            for event in expanded:
                row=_evidence(event,sources)
                if row:
                    identity=(row.get('source_id'),row['url'],row.get('page'))
                    if identity not in seen:
                        resolved.append(row)
                        seen.add(identity)
                elif event.get('source_id'):
                    missing.append(event['source_id'])
        alerts.append({'id':f"{rule}-{case['id'] if case else 'cartera'}-{len(alerts)}",'rule':rule,'rule_text':RULES[rule],'severity':severity,
                       'title':title,'detail':detail,'case_id':case['id'] if case else None,'case_name':case['name'] if case else None,
                       'evidence':resolved[:6],'source_ids':list(dict.fromkeys(r['source_id'] for r in resolved if r.get('source_id'))),
                       'unresolved_source_ids':list(dict.fromkeys(missing)),
                       'evidence_status':'parcial' if resolved and missing else 'disponible' if resolved else 'sin_enlace_incorporado',
                       'date':max((str(e.get('date') or '') for e in resolved),default=today.isoformat())})
    recent=[i for i in media_items+official_items if (_day(i.get('date') or i.get('published')) or date.min)>=today-timedelta(days=21)]
    for tag,rule,severity in [('Violencia','violencia','alta'),('Medida de fuerza','medida','media'),('Seguridad','seguridad','media')]:
        hits=[i for i in recent if tag in i.get('tags',[])]
        by_case={}
        for item in hits:
            for code in item.get('case_codes') or [None]:
                by_case.setdefault(code,[]).append(item)
        for code,items in by_case.items():
            case=next((c for c in cases if c['id']==code),None)
            where=case['name'] if case else 'el entorno de la operación'
            add(rule,severity,f"{tag} reportada · {where}",f"{len(items)} publicación(es) de {', '.join(sorted({i.get('outlet') or i.get('institution') for i in items}))} en los últimos 21 días.",case,
                [{**i,'date':(i.get('date') or i.get('published') or '')[:10]} for i in items])
    emergency=[i for i in media_items+official_items if 'Estado de emergencia' in i.get('tags',[]) and (_day(i.get('date') or i.get('published')) or date.min)>=today-timedelta(days=30)]
    if emergency:
        add('emergencia','alta','Estado de emergencia mencionado en el área',f'{len(emergency)} publicación(es) en 30 días. Verificar alcance y vigencia en El Peruano.',None,
            [{**i,'date':(i.get('date') or i.get('published') or '')[:10]} for i in emergency])
    dates=[_day(i.get('published') or i.get('date')) for i in media_items]
    last=sum(1 for d in dates if d and d>=today-timedelta(days=14))
    previous=sum(1 for d in dates if d and today-timedelta(days=70)<=d<today-timedelta(days=14))/4
    if last>=4 and last>=2*max(previous,1):
        add('pico','media','Aumento de la cobertura de prensa',f'{last} notas en 14 días frente a un promedio de {previous:.1f} por quincena en las 8 semanas previas.',None,
            [{**i,'date':i['published'][:10]} for i in media_items[:5]])
    for case in cases:
        events=case.get('events',[])
        if service_phase(case.get('phase')):
            add('fase','alta',f"Fase oficial: {case['phase']}",'La Defensoría clasifica el caso en una fase de riesgo alto en el período.',case,[e for e in events if e.get('kind')=='reporte oficial'][:1])
        for item in case.get('commitments',[]):
            due=_day(item.get('due_date'))
            if not due:
                continue
            later=[e for e in events if (_day(e.get('date') or e.get('period')) or date.min)>due]
            basis=references(item,case) or [e for e in events if e.get('kind')=='reporte oficial'][:1]
            if today<=due<=today+timedelta(days=30):
                add('plazo','media',f"Plazo próximo: {item['text'][:80]}",f"Fecha reportada {due.isoformat()}. Responsable: {item.get('responsible') or 'no individualizado'}.",case,basis)
                alerts[-1]['date']=due.isoformat()
            elif today-timedelta(days=90)<=due<today and not later:
                add('vencido','media',f"Compromiso vencido sin registro posterior: {item['text'][:70]}",f"La fecha {due.isoformat()} pasó y ninguna fuente incorporada reporta qué ocurrió.",case,basis)
                alerts[-1]['date']=due.isoformat()
        press=[e for e in events if e.get('kind')=='prensa' and (_day(e.get('date')) or date.min)>=today-timedelta(days=30)]
        official=[e for e in events if e.get('kind')!='prensa']
        last_official=max((_day(e.get('date') or e.get('period')) for e in official if _day(e.get('date') or e.get('period'))),default=None)
        if press and (not last_official or last_official<today-timedelta(days=45)):
            add('brecha','media','Brecha de información oficial',f"{len(press)} nota(s) de prensa en 30 días; la última fuente oficial incorporada es de {last_official.isoformat() if last_official else 'fecha desconocida'}.",case,press)
    current={service_name(c['name']) for c in cases}
    unclosed=[]
    for row in history:
        if row.get('official_code') in {c['id'] for c in cases}:
            continue  # same conflict, still reported under its official code
        if tokens(row.get('name') or '') & set().union(*(tokens(c['name']) for c in cases)) if cases else False:
            continue  # same community still reported in a current case (e.g. 'CC Chuicuni' in both)
        if (row.get('last_status') or '').lower() in ('activo','latente') and service_name(row.get('name') or '') not in current:
            unclosed.append(row)
    if len(unclosed)>3:
        # One grouped alert: a dozen separate low alerts would bury the urgent ones.
        add('sin_cierre','baja',f'{len(unclosed)} conflictos históricos sin cierre reportado',
            'Figuraban activos o latentes en su último registro y dejaron de reportarse sin cierre: '+'; '.join(f"{(r.get('name') or '')[:50]} ({r.get('last_period')})" for r in unclosed[:10])+('…' if len(unclosed)>10 else '.'),None,[])
        alerts[-1]['date']=max(r.get('last_period') or '' for r in unclosed)
        alerts[-1]['cases']=[{'name':r.get('name'),'last_period':r.get('last_period'),'district':r.get('district'),'last_status':r.get('last_status')} for r in unclosed]
    else:
        for row in unclosed:
            add('sin_cierre','baja',f"Sin cierre reportado: {(row.get('name') or '')[:70]}",
                f"Último registro {row.get('last_period')} como {row.get('last_status').lower()} en {row.get('district') or 'distrito no informado'}. Actores primarios: {((row.get('actors') or {}).get('primarios') or 'no informados')[:140]}.",None,[])
            alerts[-1]['date']=row.get('last_period') or ''
    for insight in insights:
        if insight.get('type')=='discrepancia':
            case=next((c for c in cases if c['id']==insight.get('case_id')),None)
            add('discrepancia','baja',insight['title'],insight['text'],case,references(insight,case))
    alerts.sort(key=lambda a:a['date'],reverse=True)
    alerts.sort(key=lambda a:-SEVERITY[a['severity']])
    return alerts


GENERIC={'las','bambas','minera','minero','antamina','petroperu','comunidad','comunidades','campesina','campesinas','empresa','apurimac','ancash','huanuco','loreto','cusco',
         'derrame','petroleo','corredor','distrito','provincia','poblacion','compania','frente','defensa','nativa','nativas','sector','caso'}


def tokens(name):
    import unicodedata
    text=unicodedata.normalize('NFKD',name.lower()).encode('ascii','ignore').decode()
    return {w for w in __import__('re').findall(r'[a-z]{5,}',text) if w not in GENERIC}


def service_name(name):
    return ' '.join(name.lower().replace('(',' ').split())[:40]


def service_phase(phase):
    text=(phase or '').lower()
    return 'escalamiento' in text and 'desescalamiento' not in text or 'crisis' in text


def summary(alerts):
    return dict(Counter(a['severity'] for a in alerts))
