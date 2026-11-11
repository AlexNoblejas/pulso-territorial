"""Ciclo automático completo: todas las fuentes, verificación y bitácora.

Ejecutar: python -m pulso.pipeline
GitHub Actions lo corre cada día; localmente lo corre iniciar.ps1 -Automatizar o el botón
"Actualizar monitoreo". Cada paso queda en data/run_log.json con su resultado, aunque falle.
"""
import json
import os
import sys
import time

from . import corpus, geoperu, news, service, sources

LOG=service.DATA/'run_log.json'
SEED=service.ROOT/'demo_data'/'run_log.json'


def _step(name,label,function):
    started=time.time()
    try:
        detail=function()
        return {'step':name,'label':label,'ok':True,'detail':detail,'seconds':round(time.time()-started,1)}
    except Exception as exc:
        detail=str(exc) if isinstance(exc,RuntimeError) else f'{type(exc).__name__}: {exc}'
        return {'step':name,'label':label,'ok':False,'detail':detail[:220],'seconds':round(time.time()-started,1)}


def _defensoria():
    result=service.sync_sources(limit=2)
    if result['errors'] and not (result['downloaded'] or result['existing']):
        raise ValueError('; '.join(result['errors'])[:160])
    return f"{result['discovered']} enlaces en el catálogo · {result['downloaded']} reportes nuevos · {result['existing']} ya conocidos"


def _news():
    data=news.update()
    return f"{len(data['items'])} notas en {WINDOW} días · {sum(f['ok'] for f in data['feeds'])}/{len(data['feeds'])} feeds respondieron"


def _connector(name):
    def run():
        result=sources.run(name)
        if not result['ok']:
            raise RuntimeError(f"{result['error']} · se conserva la copia del {(result.get('last_ok_at') or 'sin fecha')[:10]} ({len(result.get('items',[]))} registros)")
        return f"{result['fetched']} registros leídos · {result['new']} nuevos · {len(result['items'])} acumulados · {result['requests']} solicitudes"
    return run


def _geoperu():
    counts,failures=[],[]
    for company in geoperu.EXTENTS:
        data=geoperu.update(company)
        failed=[v for v in data['layers'].values() if not v['ok']]
        counts.append(f"{company}: {sum(v['count'] for v in data['layers'].values())} elementos en {len(data['layers'])} capas")
        if failed:
            failures.append(f"{company}: {len(failed)} capas con {failed[0]['error'][:60]} · se conserva la copia del {(geoperu.load(company).get('fetched_at') or 'sin fecha')[:10]}")
    if failures:
        raise RuntimeError(' · '.join(failures))
    return ' · '.join(counts)


def _corpus():
    corpus.load.cache_clear()
    library=corpus.load()
    if library['problems']:
        raise ValueError('; '.join(library['problems']))
    return f"{len(library['documents'])} PDF con hash correcto · {len(library['passages'])+len(library['signals'])} citas literales comprobadas"


def _links():
    from . import links
    data=links.run()
    t=data['totals']
    detail=f"{data['total']} enlaces · {t.get('ok',0)} responden · {t.get('bloqueado',0)} bloquean al verificador · {t.get('roto',0)} rotos · {t.get('sin respuesta',0)} sin respuesta"
    if t.get('roto'):
        raise RuntimeError(detail)
    return detail


WINDOW=news.WINDOW_DAYS
STEPS=[('defensoria','Reporte mensual de la Defensoría (HTML/PDF)',_defensoria),
       ('defensoria_pdf','Defensoría: pasajes por caso en reportes PDF (historial)',_connector('defensoria')),
       ('prensa','Prensa: El Comercio, La República, Andina y Google News',_news),
       ('gobpe','gob.pe: PCM, MINEM, MINAM, OEFA, ANA, PNP, Mininter, Petroperú',_connector('gobpe')),
       ('ogasa','SINIA: informes mensuales MINAM/OGASA (PDF)',_connector('ogasa')),
       ('willaqniki','PCM: revista Willaqniki (PDF)',_connector('willaqniki')),
       ('geoperu','GEOPERÚ: capas territoriales por ArcGIS REST',_geoperu),
       ('corpus','Verificación del corpus curado (SHA-256 y cita literal)',_corpus)]


def load():
    for path in (LOG,SEED):
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return {'runs':[]}


def run(only=None):
    service.init_db()
    started=service.now()
    steps=[_step(name,label,function) for name,label,function in STEPS if not only or name in only]
    from . import portfolio
    steps.append(_step('cartera','Reconstrucción de carteras y alertas',lambda:f"{sum(len(portfolio.portfolio(c)['cases']) for c in portfolio.COMPANIES)} casos · {sum(len(portfolio.portfolio(c)['alerts']) for c in portfolio.COMPANIES)} alertas activas" if portfolio.rebuild() else ''))
    steps.append(_step('enlaces','Verificación automática de todos los enlaces mostrados',_links))
    record={'started_at':started,'finished_at':service.now(),'trigger':os.getenv('PULSO_TRIGGER','local'),
            'run_url':os.getenv('PULSO_RUN_URL'),'ok':all(s['ok'] for s in steps),'steps':steps}
    log=load()
    log['runs']=([record]+log.get('runs',[]))[:90]
    LOG.parent.mkdir(parents=True,exist_ok=True)
    LOG.write_text(json.dumps(log,ensure_ascii=False,indent=1),encoding='utf-8')
    return record


STATION_LOG=service.ROOT/'demo_data'/'station_log.json'


def station():
    """Local station: MINAM servers (SINIA, GEOPERÚ) answer 403 to GitHub's IPs, so a laptop in Peru
    refreshes them and versions the result in demo_data/; Actions then publishes the newest copy."""
    import shutil
    os.environ.setdefault('PULSO_TRIGGER','estación local (laptop en Perú)')
    record=run(['ogasa','geoperu'])
    (service.ROOT/'demo_data'/'sources').mkdir(parents=True,exist_ok=True)
    shutil.copy2(sources.DIRECTORY/'ogasa.json',service.ROOT/'demo_data'/'sources'/'ogasa.json')
    for company in geoperu.EXTENTS:
        shutil.copy2(service.DATA/f'geoperu_{company}.json',service.ROOT/'demo_data'/f'geoperu_{company}.json')
    log=json.loads(STATION_LOG.read_text(encoding='utf-8')) if STATION_LOG.exists() else {'runs':[]}
    log['runs']=([record]+log['runs'])[:30]
    STATION_LOG.write_text(json.dumps(log,ensure_ascii=False,indent=1),encoding='utf-8')
    return record


def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    record=station() if sys.argv[1:]==['--estacion'] else run(sys.argv[1:] or None)
    for step in record['steps']:
        print(f"{'OK ' if step['ok'] else 'ERR'} {step['label']} · {step['detail']} · {step['seconds']}s")
    return 0


if __name__=='__main__':
    raise SystemExit(main())
