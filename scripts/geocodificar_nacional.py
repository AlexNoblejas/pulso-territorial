"""Ubica los distritos de todos los conflictos del reporte vigente con el límite distrital de GEOPERÚ.

Uso: python scripts/geocodificar_nacional.py
Agrega a demo_data/geocodes.json claves 'DISTRITO|PROVINCIA' (y 'DISTRITO' si no existía) con el punto
representativo del polígono distrital, y reconstruye data/national.json.
"""
import json
import sys
from pathlib import Path

import requests
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pulso import national, service  # noqa: E402

LAYER = 'https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicio_Oportunidades_Inversion/MapServer/3/query'


def features(where):
    response = requests.get(LAYER, params={'where': where, 'outFields': 'NOMBDIST,NOMBPROV,NOMBDEP,IDDIST', 'returnGeometry': 'true',
                                           'outSR': 4326, 'maxAllowableOffset': 0.01, 'f': 'geojson'}, timeout=180)
    return response.json().get('features', [])


def quoted(names):
    return ','.join("'" + n.replace("'", "''") + "'" for n in names)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    data = national.build()
    parsed = [national.parse_location(c['location'], c['region']) for c in data['cases']]
    path = ROOT / 'demo_data' / 'geocodes.json'
    geocodes = json.loads(path.read_text(encoding='utf-8'))
    pairs = {(d, p) for d, p, _ in parsed if d}
    names = sorted({d for d, _ in pairs})
    for start in range(0, len(names), 40):
        for feature in features('NOMBDIST IN (' + quoted(names[start:start + 40]) + ')'):
            props = feature['properties']
            district, province = service.norm(props['NOMBDIST']).upper(), service.norm(props['NOMBPROV']).upper()
            if (district, province) in pairs or (district, '') in pairs:
                point = shape(feature['geometry']).representative_point()
                entry = {'coordinates': [round(point.x, 6), round(point.y, 6)], 'district': props['NOMBDIST'], 'province': props['NOMBPROV'],
                         'ubigeo': props['IDDIST'], 'source': 'GEOPERÚ límite distrital'}
                geocodes[f'{district}|{province}'] = entry
                geocodes[f'{district}|'] = entry if (district, '') in pairs else geocodes.get(f'{district}|', entry)
    # Province and department points: union of their districts (GEOPERÚ has one district layer).
    for field, key, values in [('NOMBPROV', 'PROV', sorted({p for _, p, _ in parsed if p})), ('NOMBDEP', 'DEP', sorted({d for _, _, d in parsed if d}))]:
        for start in range(0, len(values), 8):
            groups = {}
            for feature in features(f'{field} IN (' + quoted(values[start:start + 8]) + ')'):
                groups.setdefault(service.norm(feature['properties'][field]).upper(), []).append(shape(feature['geometry']))
            for name, shapes in groups.items():
                point = unary_union([g.buffer(0) for g in shapes]).representative_point()  # buffer(0) repairs simplified rings
                geocodes[f'{key}:{name}'] = {'coordinates': [round(point.x, 6), round(point.y, 6)], 'source': 'GEOPERÚ límite distrital (unión)'}
    path.write_text(json.dumps(geocodes, ensure_ascii=False, indent=1), encoding='utf-8')
    (service.DATA / 'portfolio').mkdir(parents=True, exist_ok=True)
    (service.DATA / 'portfolio' / 'geocodes.json').write_text(json.dumps(geocodes, ensure_ascii=False, indent=1), encoding='utf-8')
    data = national.build()
    from collections import Counter
    print(len(data['cases']), 'conflictos ·', dict(Counter(c['coordinate_precision'] for c in data['cases'])))
    for c in data['cases']:
        if not c['coordinates']:
            print('   sin punto:', c['code'], c['name'][:50], '|', c['location'][:70])


if __name__ == '__main__':
    main()
