"""Reporte mensual portable: visuales SVG y evidencia, sin servicios externos."""
from collections import Counter,defaultdict
import html
import math
from urllib.parse import urlsplit


def esc(value):
    return html.escape(str(value or ''),quote=True)


def href(value):
    return esc(value) if urlsplit(value or '').scheme in {'http','https'} else '#'


def territory_svg(p,geo):
    bounds=geo.get('extent',[-79,-19,-68,0])
    w,h=900,330
    left,bottom,right,top=bounds
    cosine=math.cos(math.radians((bottom+top)/2))
    scale=min((w-60)/((right-left)*cosine),(h-40)/(top-bottom))
    cx,cy=(right+left)/2,(top+bottom)/2
    def xy(coords):
        return f'{w/2+(coords[0]-cx)*cosine*scale:.1f},{h/2-(coords[1]-cy)*scale:.1f}'
    paths=[]
    for feature in geo.get('boundary',{}).get('features',[]):
        geometry=feature.get('geometry') or {}
        polygons=[geometry['coordinates']] if geometry.get('type')=='Polygon' else geometry.get('coordinates',[]) if geometry.get('type')=='MultiPolygon' else []
        for polygon in polygons:
            d=' '.join('M'+' L'.join(xy(pt) for pt in ring)+' Z' for ring in polygon)
            paths.append(f'<path d="{d}"/>')
    roads=[]
    for feature in geo.get('roads',{}).get('features',[]):
        g=feature.get('geometry') or {}
        lines=[g['coordinates']] if g.get('type')=='LineString' else g.get('coordinates',[]) if g.get('type')=='MultiLineString' else []
        roads.extend(f'<polyline points="{" ".join(xy(pt) for pt in line)}"/>' for line in lines)
    groups=defaultdict(list)
    for case in p['cases']:
        if case.get('coordinates'):
            groups[tuple(case['coordinates'][:2])].append(case)
    points=[]
    for coords,cases in groups.items():
        x,y=xy(coords).split(',')
        names='; '.join(c['name'] for c in cases)
        points.append(f'<g><title>{esc(names)}</title><circle cx="{x}" cy="{y}" r="10" fill="#e2ac58" stroke="white" stroke-width="3"/><text x="{x}" y="{float(y)+3}" text-anchor="middle" font-size="9" fill="#17372c">{len(cases)}</text></g>')
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Mapa referencial de casos"><defs><clipPath id="mapclip"><rect width="{w}" height="{h}" rx="12"/></clipPath></defs><g clip-path="url(#mapclip)"><rect width="{w}" height="{h}" fill="#eef3ed"/><g fill="#dfebdf" stroke="#a9bca6" stroke-width=".65">{"".join(paths)}</g><g fill="none" stroke="#c4a064" stroke-width=".8" opacity=".75">{"".join(roads)}</g>{"".join(points)}</g></svg>'


def phase_svg(p):
    stages=[('Temprana',50,100),('Escalamiento',240,53),('Crisis',430,22),('Desescalamiento',620,66),('Acuerdos',810,100)]
    counts=Counter()
    for case in p['cases']:
        phase=(case.get('phase') or '').lower()
        if 'desescal' in phase:counts['Desescalamiento']+=1
        elif 'escal' in phase:counts['Escalamiento']+=1
        elif 'crisis' in phase:counts['Crisis']+=1
        elif 'temprana' in phase:counts['Temprana']+=1
        elif 'acuerdo' in phase:counts['Acuerdos']+=1
    markers=[]
    for name,x,y in stages:
        count=counts[name]
        markers.append(f'<circle cx="{x}" cy="{y}" r="{16 if count else 6}" fill="{"#11755e" if count else "#dce6df"}"/>'+ (f'<text x="{x}" y="{y+4}" text-anchor="middle" fill="white" font-size="12">{count}</text>' if count else '')+f'<text x="{x}" y="136" text-anchor="middle" fill="#587267" font-size="12">{esc(name)}</text>')
    return f'<svg viewBox="0 0 870 155" aria-label="Fases documentadas" role="img"><path d="M50 100 C140 100 165 66 240 53 S350 0 430 22 S540 36 620 66 S725 100 810 100" fill="none" stroke="#c7d9cf" stroke-width="3"/>{"".join(markers)}</svg>'


def trend_svg(p):
    rows=p.get('historical_series',[])
    if not rows:return '<p>Sin serie histórica incorporada.</p>'
    w,h=870,150
    maximum=max(1,max((r.get('active') or 0)+(r.get('latent') or 0) for r in rows))
    x=lambda i:35+i*800/max(1,len(rows)-1)
    y=lambda n:110-(n or 0)*90/maximum
    lines=[]
    for key,color in [('active','#12866c'),('latent','#d19a49')]:
        d=''
        pen=False
        for i,row in enumerate(rows):
            if row.get(key) is None or not row.get('observed'):
                pen=False
                continue
            if i:
                a,b=map(int,rows[i-1]['period'].split('-'));c,e=map(int,row['period'].split('-'))
                if c*12+e-(a*12+b)>1:pen=False
            d+=f'{"L" if pen else "M"}{x(i):.1f},{y(row[key]):.1f} '
            pen=True
        lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
    labels=''.join(f'<text x="{x(i):.1f}" y="140" text-anchor="middle" fill="#6b8076" font-size="10">{esc(rows[i]["period"])}</text>' for i in sorted({0,len(rows)//2,len(rows)-1}))
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Activos y latentes observados en la muestra histórica"><path d="M35 110H835" stroke="#dce6df"/>{"".join(lines)}{labels}</svg><p class="small">Verde: activos · Ocre: latentes. Muestra histórica, no total empresarial. Los vacíos no se imputan como cero ni se prolongan hasta hoy.</p>'


def lane_bars_svg(p):
    """Publications per actor type and conflict: who is talking about each case."""
    lanes=p.get('lanes') or []
    colors={'Defensoría':'#167b70','Ejecutivo':'#2563b9','Fiscalización y agua':'#3f8f8a','Policía':'#8a6d9e','Empresa':'#b58438','Prensa':'#c0794f'}
    rows=[(case['name'],Counter(e.get('lane') for e in case['events'])) for case in p['cases']]
    if not rows:
        return '<p>Sin conflictos activos en el período.</p>'
    total=max(1,max(sum(c.values()) for _,c in rows))
    h=34*len(rows)+40
    bars=[]
    for i,(name,counts) in enumerate(rows):
        y=20+i*34
        x=250
        bars.append(f'<text x="0" y="{y+14}" font-size="11" fill="#34503f">{esc(name[:38])}</text>')
        for lane in lanes:
            width=counts.get(lane,0)/total*600
            if width:
                bars.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="20" fill="{colors.get(lane,"#999")}"><title>{esc(lane)}: {counts[lane]}</title></rect>')
                if width>18:
                    bars.append(f'<text x="{x+width/2:.1f}" y="{y+14}" font-size="10" fill="white" text-anchor="middle">{counts[lane]}</text>')
                x+=width
    legend=''.join(f'<span><i style="background:{colors.get(l)}"></i>{esc(l)}</span>' for l in lanes)
    return f'<svg viewBox="0 0 870 {h}" role="img" aria-label="Publicaciones por tipo de actor y conflicto">{"".join(bars)}</svg><div class="legend">{legend}</div>'


def media_svg(p):
    weeks=(p.get('media') or {}).get('weekly') or []
    if not weeks:
        return '<p>Sin notas de prensa en la ventana.</p>'
    maximum=max(1,max(w['total'] for w in weeks))
    bw=800/len(weeks)
    bars=''.join(f'<rect x="{40+i*bw+bw*.15:.1f}" y="{120-w["total"]/maximum*100:.1f}" width="{bw*.7:.1f}" height="{w["total"]/maximum*100:.1f}" fill="#c0794f"><title>Semana del {esc(w["week"])}: {w["total"]} notas</title></rect><text x="{40+i*bw+bw/2:.1f}" y="{114-w["total"]/maximum*100:.1f}" font-size="10" text-anchor="middle" fill="#6b5240">{w["total"]}</text>' for i,w in enumerate(weeks))
    labels=''.join(f'<text x="{40+i*bw+bw/2:.1f}" y="138" font-size="9" text-anchor="middle" fill="#6b8076">{esc(w["week"][5:])}</text>' for i,w in enumerate(weeks))
    return f'<svg viewBox="0 0 870 145" role="img" aria-label="Notas de prensa por semana"><path d="M40 120H840" stroke="#dce6df"/>{bars}{labels}</svg>'


def figure(number,title,body,what,source,cutoff,how):
    return (f'<figure><figcaption class="figtitle">Figura {number}. {esc(title)}</figcaption>{body}<dl class="figmeta"><div><dt>Qué muestra</dt><dd>{esc(what)}</dd></div>'
            f'<div><dt>Fuente</dt><dd>{esc(source)}</dd></div><div><dt>Corte</dt><dd>{esc(cutoff)}</dd></div><div><dt>Cómo leerla</dt><dd>{esc(how)}</dd></div></dl></figure>')


def _plural(n,one,many):
    return f'{n} {one if n==1 else many}'


def narrative(p):
    """Executive summary written only from the portfolio data; each sentence states its source."""
    company=p['company']
    cases=p['cases']
    phases=Counter(c.get('phase') or 'sin fase reportada' for c in cases)
    paragraphs=[]
    if cases:
        names='; '.join(c['name']+('' if (c.get('district') or '').lower() in c['name'].lower() else f" ({c.get('district') or c.get('region')})") for c in cases)
        paragraphs.append(f"Al corte de {p['coverage']['period_label'].lower()}, el reporte mensual de la Defensoría del Pueblo registra "
                          f"{_plural(len(cases),'conflicto activo','conflictos activos')} en {'el' if len(cases)==1 else 'los'} que {company['legal_name']} figura como actor: {names}. "
                          f"Por fase: {', '.join(f'{n} en {k.lower()}' for k,n in phases.items())}. "
                          f"{_plural(sum(1 for c in cases if c.get('dialogue')),'caso reporta','casos reportan')} un espacio de diálogo.")
    else:
        paragraphs.append(f"Al corte de {p['coverage']['period_label'].lower()}, la Defensoría no registra conflictos activos con {company['legal_name']} como actor primario.")
    history=p.get('linked_history') or []
    if history:
        closed=sum(1 for h in history if (h.get('last_status') or '').lower() in ('resuelto','retirado','fusionado'))
        active=sum(1 for h in history if (h.get('last_status') or '').lower()=='activo')
        paragraphs.append(f"La base histórica de reportes de la Defensoría (2012-2025) vincula {_plural(len(history),'conflicto','conflictos')} a la empresa: "
                          f"{active} figuraban activos en su último registro y {closed} fueron resueltos, retirados o fusionados. Los más recientes: "
                          f"{'; '.join(h['name'][:60] + ' (' + (h.get('district') or 's/d') + ', hasta ' + (h.get('last_period') or '') + ')' for h in history[:3])}.")
    alerts=p.get('alerts') or []
    if alerts:
        s=p.get('alert_summary') or {}
        paragraphs.append(f"El sistema activó {_plural(len(alerts),'alerta','alertas')} ({s.get('alta',0)} altas, {s.get('media',0)} medias y {s.get('baja',0)} bajas). "
                          f"Prioridades: {'; '.join(a['title'] for a in alerts[:3])}.")
    media=p.get('media') or {}
    if media.get('total'):
        tags=Counter(t for i in media['items'] for t in i['tags'] if t!='Contexto').most_common(3)
        paragraphs.append(f"En los últimos 120 días, {_plural(media['total'],'nota de prensa','notas de prensa')} de {_plural(len(media['outlets']),'medio','medios')} mencionaron la operación o su entorno"
                          f"{'; predominan los temas ' + ', '.join(t.lower() for t,_ in tags) if tags else ''}.")
    actions=p.get('state_actions') or []
    if actions:
        lanes=Counter(a['lane'] for a in actions)
        paragraphs.append(f"Además, las entidades del Estado publicaron {_plural(len(actions),'comunicación o pasaje','comunicaciones o pasajes')} sobre el territorio que no nombran un conflicto de la cartera "
                          f"({', '.join(f'{k}: {v}' for k,v in lanes.items())}).")
    return paragraphs


AGENDA={'plazo':'Confirmar la reunión o el plazo con los actores y preparar la posición de la empresa.',
        'vencido':'Pedir al responsable el estado del compromiso y registrar la respuesta antes del próximo reporte.',
        'brecha':'Contrastar lo que dice la prensa con la Defensoría o la PCM antes de fijar una posición.',
        'discrepancia':'Unificar la fecha o la cifra en la comunicación de la empresa para evitar un error público.',
        'medida':'Revisar el protocolo de prevención y abrir comunicación con los actores primarios del caso.',
        'violencia':'Activar el protocolo de crisis y coordinar con la PCM y la Defensoría.',
        'seguridad':'Coordinar con seguridad y operaciones; confirmar si el incidente afecta a la comunidad.',
        'emergencia':'Verificar alcance y vigencia del estado de emergencia en El Peruano.',
        'pico':'Revisar las notas del período para identificar el tema que crece.',
        'sin_cierre':'Confirmar con el área de relaciones comunitarias si el conflicto se cerró y documentar el acta de cierre.',
        'fase':'Priorizar el caso en la agenda semanal de gestión social.'}


def create_report(p,geo):
    from .links import load as load_links
    links=load_links().get('results',{})
    def status(url):
        result=links.get((url or '').split('#')[0])
        return f' <span class="link {esc(result["state"].replace(" ","-"))}">{esc(result["state"])}</span>' if result else ''
    sources={s['id']:s for s in p['sources']}
    company=p['company']
    period=p['coverage']['period_label']
    built=p['coverage'].get('built_at','')[:10]
    lenses=p.get('lenses') or {}
    cards=[]
    for case in p['cases']:
        actors=case.get('actors') or {}
        actor_rows=''.join(f'<tr><th>{label}</th><td>{esc(actors.get(key) or "No informado en la ficha")}</td></tr>' for key,label in [('primarios','Primarios (partes)'),('secundarios','Secundarios (intervienen)'),('terciarios','Terciarios (median o supervisan)')])
        period_events=[e for e in case['events'] if e.get('kind')=='reporte oficial']
        commitments=''.join(f'<tr><td>{esc(i["text"])}</td><td>{esc(i.get("responsible") or "No individualizado")}</td><td>{esc(i.get("due_date") or i.get("due_precision") or "Sin plazo")}</td><td>{esc(i.get("reported_status") or "Sin verificación posterior")}</td></tr>' for i in case.get('commitments',[]))
        lanes=Counter(e.get('lane') for e in case['events'])
        other=[]
        for lane in (p.get('lanes') or []):
            items=[e for e in case['events'] if e.get('lane')==lane and e.get('kind')!='reporte oficial'][:2]
            if items:
                lens=next((lenses[e['institution_key']]['lens'] for e in items if e.get('institution_key') in lenses),'')
                other.append(f'<li><b>{esc(lane)}</b> · {lanes[lane]} publicación(es){(" · <i>" + esc(lens) + "</i>") if lens else ""}<ul>'+''.join(
                    f'<li>{esc(e.get("date") or e.get("period"))} · <a href="{href(e.get("pdf_url") or sources.get(e["source_id"],{}).get("url"))}">{esc(e["title"])}</a>{" (p. " + esc(e["page"]) + ")" if e.get("page") else ""}{status(e.get("pdf_url") or sources.get(e["source_id"],{}).get("url"))}</li>' for e in items)+'</ul></li>')
        case_alerts=''.join(f'<li><b>{esc(a["severity"].upper())}</b> · {esc(a["title"])} — {esc(a["detail"])}</li>' for a in p.get('alerts',[]) if a.get('case_id')==case['id'])
        territory=''.join(f'<tr><th>{esc(r["label"])}</th><td>{esc(r["value"])}</td></tr>' for r in case.get('territory') or [])
        cards.append(f'''<article class="case"><span class="eyebrow">{esc(case["id"])} · {esc(", ".join(x for x in [case.get("district"),case.get("province"),case.get("region")] if x))}</span><h2>{esc(case["name"])}</h2>
<span class="badge">{esc(case["status"])} · {esc(case["phase"] or "Sin fase")} · {"con diálogo" if case.get("dialogue") else "sin diálogo reportado"}</span>
<h3>Situación</h3><p>{esc(case.get("original_description") or case["summary"])}</p>
<h3>Qué pasó en el período</h3>{"".join(f"<p>{esc(e['summary'])}</p>" for e in period_events) or "<p>La ficha no describe hechos del período.</p>"}<p class="small">Fuente: Defensoría del Pueblo, reporte de {esc(period.lower())}.</p>
<h3>Con quién gestionar</h3><table>{actor_rows}</table><p class="small">Actores tal como los nombra la ficha oficial de la Defensoría.</p>
{f"<h3>Compromisos y plazos reportados</h3><table><tr><th>Compromiso</th><th>Responsable</th><th>Plazo</th><th>Estado</th></tr>{commitments}</table>" if commitments else ""}
<h3>Qué dicen las demás fuentes</h3>{f"<ul class='sources'>{''.join(other)}</ul>" if other else "<p>Ninguna otra fuente incorporada nombra el caso.</p>"}
{f"<h3>Alertas del caso</h3><ul>{case_alerts}</ul>" if case_alerts else ""}
{f"<h3>Contexto territorial (GEOPERÚ)</h3><table>{territory}</table><p class='small'>La cercanía no acredita afectación.</p>" if territory else ""}</article>''')
    agenda=''.join(f'<li><b>{esc(a["title"])}</b>{(" · " + esc(a["case_name"])) if a.get("case_name") else ""}<br>{esc(AGENDA.get(a["rule"],"Revisar la evidencia."))}</li>' for a in p.get('alerts',[]))
    history_rows=''.join(f'<tr><td>{esc(h["name"])}{" <small>(registro provisional)</small>" if h.get("provisional") else ""}</td><td>{esc(h.get("district") or "s/d")}</td><td>{esc(h.get("first_period"))} – {esc(h.get("last_period"))}</td><td>{esc(h.get("last_status") or "s/d")}</td><td>{esc((h.get("actors") or {}).get("primarios") or "s/d")}</td></tr>' for h in p.get('linked_history') or [])
    source_list=''.join(f'<li>{esc(s["institution"])} · <a href="{href(s.get("url") or s.get("pdf_url"))}">{esc(s["title"])}</a>{status(s.get("url"))}</li>' for s in p['sources'])
    checked=load_links().get('checked_at','')[:16].replace('T',' ')
    summary=''.join(f'<p>{esc(t)}</p>' for t in narrative(p))
    media=p.get('media') or {}
    style='''*{box-sizing:border-box}body{font:15px/1.65 system-ui;background:#f1f4f1;color:#193b30;margin:0}main{max-width:1080px;margin:auto;padding:45px}header{background:#123a32;color:white;padding:42px;border-radius:18px}.eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#759486}header .eyebrow{color:#9bd9bc}h1{font-size:42px;line-height:1.12;margin:18px 0}h2{font-size:23px;line-height:1.35}h3{line-height:1.4;margin-top:22px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:20px 0}.metric{background:white;padding:22px;border-radius:14px}.metric b{display:block;font-size:32px}.metric span{font-size:12px;color:#759486}article{background:white;padding:30px;border-radius:15px;margin:20px 0}.case{break-before:page}.badge{display:inline-block;background:#e4f2ea;padding:4px 12px;border-radius:20px;font-size:12px}a{color:#178268;overflow-wrap:anywhere}.small{font-size:12px;color:#6c8176}table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}th,td{text-align:left;vertical-align:top;padding:7px 8px;border-bottom:1px solid #e3ebe5}th{color:#4d6a6a;width:26%}figure{margin:0}.figtitle{font-weight:700;font-size:15px;margin-bottom:10px}.figmeta{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;background:#f5f7f2;border-radius:10px;padding:12px 14px;font-size:12px;margin:12px 0 0}.figmeta dt{font-weight:700;color:#4d6a6a}.figmeta dd{margin:0;color:#4b6553}svg{display:block;width:100%;height:auto}.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;margin-top:8px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}.sources>li{margin-bottom:10px}.link{font-size:10px;padding:1px 6px;border-radius:8px;background:#e4f2ea;color:#167b70}.link.roto,.link.sin-respuesta{background:#f6e3df;color:#a5483c}.link.bloqueado{background:#f6eedc;color:#8a6a24}.agenda li{margin-bottom:10px}button{border:0;background:#13816a;color:white;border-radius:9px;padding:12px 20px;cursor:pointer}@media(max-width:650px){main{padding:18px}header{padding:24px}h1{font-size:32px}.metrics{grid-template-columns:1fr 1fr}.figmeta{grid-template-columns:1fr}}@media print{body{background:white}main{padding:0;max-width:none}header{print-color-adjust:exact}button{display:none}article{border:1px solid #e3ebe5}}'''
    geo_layers=(geo.get('geoperu') or {}).get('layers') or {}
    return f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Reporte mensual · {esc(company['name'])} · {esc(period)}</title><style>{style}</style><main>
<header><span class="eyebrow">PulsoTerritorial · reporte mensual de gestión social</span><h1>{esc(company['legal_name'])}<br>{esc(period)}</h1><p>{esc(company['operation'])} · {esc(company['region'])}</p><p id="prepared" class="small" style="color:#cfe3da"></p></header>
<section class="metrics"><div class="metric"><b>{p['summary']['cases']}</b><span>CONFLICTOS ACTIVOS (DEFENSORÍA)</span></div><div class="metric"><b>{len(p.get('linked_history') or [])}</b><span>CONFLICTOS EN EL HISTORIAL 2012-2025</span></div><div class="metric"><b>{len(p.get('alerts') or [])}</b><span>ALERTAS ACTIVAS</span></div><div class="metric"><b>{media.get('total',0)}</b><span>NOTAS DE PRENSA (120 DÍAS)</span></div></section>
<article><h2>Resumen ejecutivo</h2>{summary}<p class="small">Texto generado a partir de los datos de la cartera; cada cifra proviene de las fuentes listadas al final. No incluye información interna de la empresa.</p></article>
{f'<article><h2>Agenda sugerida para el analista</h2><ol class="agenda">{agenda}</ol><p class="small">Sugerencias derivadas de las reglas de alerta. Requieren el criterio del analista y no sustituyen el protocolo de la empresa.</p></article>' if agenda else ''}
<article>{figure(1,'Conflictos de la cartera en el territorio',territory_svg(p,geo),
    f"Ubicación de los conflictos activos ({p['summary']['cases']}) sobre los límites distritales de la zona; el número indica casos que comparten una misma referencia.",
    'Defensoría del Pueblo (casos); límites distritales y capas de GEOPERÚ (MINAM) consultadas por ArcGIS REST.' if geo_layers else 'Defensoría del Pueblo (casos); límites de la copia local de cartografía.',
    f"Casos: {period}. Capas: {(geo.get('geoperu') or {}).get('fetched_at','')[:10] or 'copia versionada'}.",
    'Los puntos son referencias distritales o comunales, no el lugar exacto de un hecho. Estar cerca de una operación no prueba afectación.')}</article>
<article>{figure(2,'Fase oficial de cada conflicto',phase_svg(p),
    'Cuántos conflictos activos hay en cada fase del ciclo que usa la Defensoría: temprana, escalamiento, crisis, desescalamiento y acuerdos.',
    'Defensoría del Pueblo, ficha de cada caso.',period,
    'Las fases altas (escalamiento, crisis) piden atención inmediata. El diálogo se informa aparte y no implica que los acuerdos se cumplan.')}</article>
<article>{figure(3,'Quién habla de cada conflicto',lane_bars_svg(p),
    'Número de publicaciones que nombran cada conflicto, por tipo de actor: Defensoría, Ejecutivo (PCM, MINEM, MINAM), Fiscalización y agua (OEFA, ANA), Policía, Empresa y Prensa.',
    'Defensoría (HTML y PDF), gob.pe, SINIA, PCM Willaqniki y RSS de prensa; vinculación automática por nombre del caso.',f'Hasta {built}.',
    'Un conflicto del que solo habla la prensa, sin fuente oficial reciente, es una brecha de información. Cada fuente mira desde su función.')}</article>
<article>{figure(4,'Pulso de prensa por semana',media_svg(p),
    'Notas de prensa por semana que mencionan la operación, sus comunidades o su entorno.',
    f"RSS de El Comercio, La República, Andina y Google News ({', '.join(o for o,_ in (media.get('outlets') or [])[:5])}).",
    f"Ventana de 120 días hasta {(media.get('updated_at') or '')[:10]}.",
    'Un aumento brusco es una señal para revisar las notas; una nota no prueba un hecho.')}
{figure(5,'Historia de los conflictos vinculados',trend_svg(p),
    'Conflictos activos y latentes por mes en la base histórica de la empresa.',
    'Base de tesis construida con los reportes mensuales de la Defensoría (2012-2025).','Hasta diciembre de 2025.',
    'Los meses sin dato no se imputan como cero. La serie muestra la carga histórica de conflictividad, no la situación actual.')}</article>
{''.join(cards)}
{f'<article class="case"><h2>Historial de conflictos vinculados a la empresa</h2><table><tr><th>Conflicto</th><th>Distrito</th><th>Período</th><th>Último estado</th><th>Actores primarios</th></tr>{history_rows}</table><p class="small">Fuente: base de reportes de la Defensoría 2012-2025. Un conflicto se vincula cuando la empresa aparece en su denominación, descripción o actores.</p></article>' if history_rows else ''}
<article class="case"><h2>Fuentes consultadas</h2><ul>{source_list}</ul><p class="small">Enlaces verificados automáticamente el {esc(checked)}: «ok» responde; «bloqueado» significa que el servidor no deja verificar (no que el documento falte); «roto» o «sin respuesta» requieren revisión.</p>
<h3>Método y límites</h3><p class="small">Las fuentes se descargan solas cada día. Los pasajes de PDF se extraen con pypdf y conservan su página. Las alertas son reglas explícitas sobre lo ya reportado, no predicciones. Los nombres ambiguos solo se vinculan a un caso con un término de anclaje. No se usan datos personales ni información interna de la empresa.</p></article>
<button onclick="window.print()">Imprimir / guardar PDF</button><p class="small">PulsoTerritorial · demostración académica de Alexander Noblejas (Python Intermedio, Q-Lab PUCP) con información pública. No representa a la empresa.</p></main>
<script>const n=new URLSearchParams(location.search).get('analista');if(n)document.getElementById('prepared').textContent='Preparado para: '+n.slice(0,60)+' · '+new Date().toLocaleDateString('es-PE');</script></html>'''
