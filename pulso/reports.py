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


def create_report(p,geo):
    sources={s['id']:s for s in p['sources']}
    cards=[]
    for case in p['cases']:
        events=[]
        for event in case['events']:
            source=sources.get(event['source_id'],{})
            events.append(f'<li><div class="date">{esc(event["date"] or event["period"])}</div><b>{esc(event["title"])}</b><p>{esc(event["summary"])}</p><a href="{href(source.get("url"))}">{esc(source.get("institution","Consultar fuente"))} ↗</a></li>')
        commitments=''.join(f'<li><b>{esc(item["text"])}</b><p>{esc(item.get("responsible"))} · {esc(item.get("due_date") or item.get("due_precision"))}</p><p class="small">{esc(item.get("reported_status"))}</p></li>' for item in case.get('commitments',[]))
        schedule=f'<h3>Compromisos y agenda reportada</h3><ul>{commitments}</ul>' if commitments else ''
        cards.append(f'<article><span class="eyebrow">{esc(case["id"])} · {esc(case["region"])}</span><h2>{esc(case["name"])}</h2><span class="badge">{esc(case["status"])} · {esc(case["phase"] or "Sin fase")}</span><p>{esc(case["summary"])}</p>{schedule}<h3>Hechos y comunicaciones</h3><ol class="timeline">{"".join(events)}</ol></article>')
    insights=''.join(f'<div class="insight"><span class="eyebrow">{esc(i["type"])}</span><h3>{esc(i["title"])}</h3><p>{esc(i["text"])}</p></div>' for i in p['insights'])
    source_list=''.join(f'<li>{esc(s["institution"])} · <a href="{href(s["url"])}">{esc(s["title"])}</a></li>' for s in p['sources'])
    unavailable=', '.join(s['institution'] for s in p['source_matrix'] if not s['count'])
    style='''*{box-sizing:border-box}body{font:15px/1.65 system-ui;background:#f1f4f1;color:#193b30;margin:0}main{max-width:1080px;margin:auto;padding:45px}header{background:#123a32;color:white;padding:42px;border-radius:18px}.eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#759486}header .eyebrow{color:#9bd9bc}h1{font-size:46px;line-height:1.12;margin:18px 0}h2{font-size:24px;line-height:1.35}h3{line-height:1.4}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:20px 0}.metric{background:white;padding:22px;border-radius:14px}.metric b{display:block;font-size:34px}.metric span{font-size:12px;color:#759486}article{background:white;padding:30px;border-radius:15px;margin:20px 0;break-inside:avoid}.badge{display:inline-block;background:#e4f2ea;padding:4px 12px;border-radius:20px;font-size:12px}a{color:#178268}.small{font-size:12px;color:#6c8176}.insights{display:grid;grid-template-columns:1fr 1fr;gap:20px}.insight{padding:20px;background:#f5f7ed;border:1px solid #e8ebdb;border-radius:12px}svg{display:block;width:100%;height:auto}.timeline{list-style:none;padding:0 0 0 18px;border-left:2px solid #d9e7df}.timeline li{padding:5px 0 20px 16px}.date{font-size:11px;letter-spacing:.05em;color:#799183}button{border:0;background:#13816a;color:white;border-radius:9px;padding:12px 20px;cursor:pointer}@media(max-width:650px){main{padding:18px}header{padding:24px}h1{font-size:34px}.insights{grid-template-columns:1fr}.metric{padding:15px}.metrics{gap:8px}}@media print{body{background:white}main{padding:0;max-width:none}header{print-color-adjust:exact}button{display:none}article{border:1px solid #e3ebe5}a{overflow-wrap:anywhere}}'''
    return f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Reporte mensual · {esc(p['company']['name'])}</title><style>{style}</style><main><header><span class="eyebrow">PulsoTerritorial · inteligencia que conecta</span><h1>{esc(p['company']['name'])}<br>{esc(p['coverage']['period_label'])}</h1><p>{esc(p['company']['operation'])} · {esc(p['company']['region'])}</p></header><section class="metrics"><div class="metric"><b>{p['summary']['cases']}</b><span>CASOS DOCUMENTADOS</span></div><div class="metric"><b>{p['summary']['dialogue']}</b><span>CON DIÁLOGO REPORTADO</span></div><div class="metric"><b>{p['summary']['sources']}</b><span>PUBLICACIONES DE REFERENCIA</span></div></section><p class="small">{esc(p['coverage']['scope'])} Los estados corresponden al período del reporte.</p><article><h2>La cartera, en el territorio</h2>{territory_svg(p,geo)}<p class="small">Puntos representativos, no ubicación exacta de incidentes. Límites: copia local INEI / GeoGPSPerú. Carreteras: copia local diciembre2018; no acreditan transitabilidad ni afectación. Los marcadores agrupan casos que comparten referencia administrativa.</p></article><article><h2>Momento documentado del proceso</h2>{phase_svg(p)}<p class="small">Secuencia conceptual; se muestran sólo fases publicadas. Diálogo se registra aparte y no acredita cumplimiento.</p><h3>Antecedentes de los casos de la cartera</h3>{trend_svg(p)}</article><article><h2>Qué requiere atención documental</h2><div class="insights">{insights}</div></article>{''.join(cards)}<article><h2>Fuentes y cobertura</h2><ul>{source_list}</ul><p class="small">Sin fuente directa incorporada para esta cartera: {esc(unavailable)}. Los vínculos editoriales se revisan por expediente; no equivalen a comprobación de campo. No se envía correo desde esta versión.</p></article><button onclick="window.print()">Imprimir / guardar PDF</button><p class="small">Proyecto de Alexander Noblejas · Python Intermedio · Documento generado desde la cartera seleccionada.</p></main></html>'''
