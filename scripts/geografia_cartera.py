"""Geografía base de una cartera desde GEOPERÚ: límites distritales de sus provincias y puntos
representativos distritales para ubicar los casos (mismo criterio que las otras carteras).

Uso: python scripts/geografia_cartera.py antamina
"""
import json
import sys
from pathlib import Path

import requests
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
LAYER = 'https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicio_Oportunidades_Inversion/MapServer/3'
CARTERAS = {'antamina': {'provinces': ['HUARI', 'BOLOGNESI', 'RECUAY', 'HUARMEY', 'HUAMALIES'],
                         'extent': [-78.35, -10.35, -76.6, -9.0], 'center': [-77.35, -9.75], 'zoom': 8.2}}


def main(company):
    spec = CARTERAS[company]
    where = 'NOMBPROV IN (' + ','.join(f"'{p}'" for p in spec['provinces']) + ')'
    data = requests.get(LAYER + '/query', params={'where': where, 'outFields': 'NOMBDEP,NOMBPROV,NOMBDIST,IDDIST', 'returnGeometry': 'true',
                                                   'outSR': 4326, 'maxAllowableOffset': 0.002, 'f': 'geojson'}, timeout=120).json()
    features = [{'type': 'Feature', 'geometry': f['geometry'], 'properties': {'district': f['properties']['NOMBDIST'], 'province': f['properties']['NOMBPROV'],
                 'department': f['properties']['NOMBDEP'], 'ubigeo': f['properties']['IDDIST']}} for f in data['features']]
    base = json.loads((ROOT / 'demo_data' / 'geography_mineria.json').read_text(encoding='utf-8'))
    geography = {'center': spec['center'], 'zoom': spec['zoom'], 'extent': spec['extent'],
                 'boundary': {'type': 'FeatureCollection', 'features': features},
                 'map_style_url': base['map_style_url'], 'terrain_url': base['terrain_url'],
                 'metadata': [{'layer': 'boundary', 'label': 'Límites distritales', 'source': 'GEOPERÚ · Servicio_Oportunidades_Inversion/3 (límite distrital)',
                               'crs': 'EPSG:4326', 'precision': 'administrativa, simplificada a ~200 m'},
                              next(m for m in base['metadata'] if m['layer'] == 'terrain')]}
    (ROOT / 'demo_data' / f'geography_{company}.json').write_text(json.dumps(geography, ensure_ascii=False), encoding='utf-8')
    path = ROOT / 'demo_data' / 'geocodes.json'
    geocodes = json.loads(path.read_text(encoding='utf-8'))
    for feature in features:
        point = shape(feature['geometry']).representative_point()
        geocodes.setdefault(feature['properties']['district'], {'coordinates': [round(point.x, 6), round(point.y, 6)], 'precision': 'punto representativo distrital',
                                                                'district': feature['properties']['district'], 'ubigeo': feature['properties']['ubigeo'], 'source': 'GEOPERÚ límite distrital'})
    path.write_text(json.dumps(geocodes, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(features)} distritos en {len(spec["provinces"])} provincias')


if __name__ == '__main__':
    main(sys.argv[1])
