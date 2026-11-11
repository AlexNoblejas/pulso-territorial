"""Exporta la plataforma como sitio estático (GitHub Pages).

Ejecutar: python -m pulso.export site
Genera los mismos JSON y reportes que sirve pulso.web, más los PDF del corpus verificado.
"""
import json
import shutil
import sys
from pathlib import Path

from . import corpus, portfolio, service


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        data = json.dumps(data, ensure_ascii=False)
    path.write_text(data, encoding='utf-8')


def export(target):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(service.ROOT / 'web', target)
    index = target / 'index.html'
    index.write_text(index.read_text(encoding='utf-8').replace('<html lang="es">', '<html lang="es" data-static="1">', 1), encoding='utf-8')
    (target / '.nojekyll').write_text('')
    service.init_db()
    portfolio.rebuild()
    static = target / 'static'
    for company in portfolio.COMPANIES:
        current = portfolio.portfolio(company)
        _write(static / f'portfolio_{company}.json', current)
        _write(static / f'geography_{company}.json', portfolio.geography(company))
        _write(static / f'report_{company}.html', portfolio.visual_report(company))
        for period in current['periods']:
            _write(static / f'portfolio_{company}_{period}.json', portfolio.portfolio(company, period))
            _write(static / f'report_{company}_{period}.html', portfolio.visual_report(company, period))
    from . import national
    _write(static / 'national.json', national.payload())
    readings = service.ROOT / 'demo_data' / 'ai_readings.json'
    _write(static / 'readings.json', json.loads(readings.read_text(encoding='utf-8')) if readings.exists() else {'readings': {}})
    state = target / 'state'
    state.mkdir()
    for path in [service.DATA / 'run_log.json', service.DATA / 'news.json', service.DATA / 'links.json', service.DATA / 'national.json', *service.DATA.glob('geoperu_*.json'), *(service.DATA / 'sources').glob('*.json')]:
        if path.exists():
            shutil.copy2(path, state / path.name)
    for document in corpus.load()['documents'].values():
        (target / 'corpus').mkdir(exist_ok=True)
        shutil.copy2(corpus.DIRECTORY / document['file'], target / 'corpus' / document['file'])
    return target


if __name__ == '__main__':
    print('Sitio estático en', export(sys.argv[1] if len(sys.argv) > 1 else 'site'))
