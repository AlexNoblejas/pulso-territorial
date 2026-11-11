"""Actores recurrentes en los conflictos de cada empresa, desde la base de actores de la tesis.

Uso: python scripts/importar_actores.py RUTA/base_actores_CON_ID_CONFLICTO_FINAL_100.xlsx
La base (24,100 filas, 2012-2025) tiene, por conflicto y mes, los actores primarios, secundarios y
terciarios limpios de los reportes de la Defensoría. Un actor cuenta una vez por conflicto distinto en
el que aparece. Escribe demo_data/actors_<cartera>.json.
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = {'antamina': r'antamina', 'mineria': r'las bambas|mmg', 'hidrocarburos': r'petroper'}
ROLES = [('Actores_Primarios_LIMPIO', 'primario'), ('Actores_Secundarios_LIMPIO', 'secundario'), ('Actores_Terciarios_LIMPIO', 'terciario')]
STATE = r'ministerio|presidencia|pcm|defensor|polic|pnp|gobierno regional|municipalidad|prefectura|subprefectura|fiscal|ministerio p|oefa|ana\b|autoridad|direcci[oó]n regional|sunafil|osinergmin|congreso|programa nacional|provias'


def key(text):
    """Same actor under different spellings: no accents, no parenthesis, no S.A./S.A.C. suffix."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    text = re.sub(r'\([^)]*\)', ' ', text)
    text = re.sub(r'(s\.?\s?a\.?\s?c?\.?|s\.?r\.?l\.?)\s*$', ' ', text.strip(' .;'))
    return re.sub(r'\s+', ' ', text).strip(' .;')


def kind(name):
    k = key(name)
    if re.search(r'antamina|las bambas|mmg|petroper|xstrata|glencore|\bminera\b|\bempresa\b', k) and not re.search(r'asociaci|comunidad|frente|federaci', k):
        return 'Empresa'
    if re.search(STATE, k):
        return 'Estado'
    if re.search(r'comunidad|cc\b|poblad|frente|federaci|rondas|asociaci|organizaci|dirigent|comit|centro poblado|sindicato|mineros', k):
        return 'Sociedad'
    return 'Otro'


def main(workbook):
    df = pd.read_excel(workbook)
    df['period'] = df['Año'].astype(int).astype(str) + '-' + df['Mes (N°)'].astype(int).astype(str).str.zfill(2)
    text = (df['Actores_Primarios_LIMPIO'].astype(str) + ' ' + df['caso'].astype(str)).str.lower()
    for company, pattern in COMPANIES.items():
        rows = df[text.str.contains(pattern, regex=True)]
        actors = defaultdict(lambda: {'conflicts': set(), 'months': set(), 'roles': defaultdict(int), 'names': defaultdict(int), 'cases': {}})
        for row in rows.itertuples(index=False):
            record = row._asdict()
            for column, role in ROLES:
                value = record.get(column)
                if not isinstance(value, str) or value.lower() == 'nan':
                    continue
                for name in re.split(r'\s/\s|;', value):
                    name = name.strip(' .;-')
                    if len(name) < 3:
                        continue
                    entry = actors[key(name)]
                    entry['conflicts'].add(record['ID_conflicto'])
                    entry['months'].add(record['period'])
                    entry['roles'][role] += 1
                    entry['names'][name] += 1
                    entry['cases'][record['ID_conflicto']] = str(record['caso'])[:90]
        out = []
        for k, e in actors.items():
            name = max(e['names'], key=e['names'].get)
            out.append({'name': name, 'type': kind(name), 'role': max(e['roles'], key=e['roles'].get), 'conflicts': len(e['conflicts']),
                        'months': len(e['months']), 'first': min(e['months']), 'last': max(e['months']),
                        'cases': [e['cases'][c] for c in list(e['conflicts'])[:4]]})
        out.sort(key=lambda a: (-a['conflicts'], -a['months']))
        data = {'company': company, 'pattern': pattern, 'source_workbook': Path(workbook).name, 'conflicts': int(rows['ID_conflicto'].nunique()),
                'method': 'Actores de los reportes de la Defensoría 2012-2025 en los conflictos donde la empresa aparece como actor primario o en el nombre del caso. Un actor cuenta una vez por conflicto.',
                'actors': out[:60]}
        (ROOT / 'demo_data' / f'actors_{company}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        print(company, data['conflicts'], 'conflictos ·', len(out), 'actores ·', [(a['name'][:40], a['conflicts']) for a in out[:6]])


if __name__ == '__main__':
    main(sys.argv[1])
