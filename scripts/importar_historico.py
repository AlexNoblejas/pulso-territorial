"""Importa de la base de tesis los conflictos vinculados a una empresa, con estado mensual y actores.

Uso: python scripts/importar_historico.py RUTA/base_unificada_conflictos_2012_2025.xlsx antamina Antamina
     python scripts/importar_historico.py RUTA/... mineria 'las bambas|mmg'
La base (33,845 filas, 2012-2025) se construyó con los reportes mensuales de la Defensoría del Pueblo.
Se vincula un caso cuando el nombre de la empresa aparece en la denominación, la descripción, la
columna Empresas o los actores. Escribe demo_data/historical_<cartera>.json.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def last(series):
    values = [v for v in series if isinstance(v, str) and v.strip() and v.strip().lower() != 'nan']
    return values[-1].strip() if values else None


def main(workbook, company, term):
    df = pd.read_excel(workbook, sheet_name='02_base_unificada')
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    text = df[['Denominacion_caso', 'caso_act', 'Descripcion_act', 'Empresas', 'Actores_Primarios', 'Actores_Secundarios', 'Actores_Terciarios']].astype(str).agg(' '.join, axis=1)
    rows = df[text.str.contains(term, case=False, regex=True)].sort_values('fecha')  # term may be 'las bambas|mmg'
    cases = []
    for number, group in rows.groupby('Numero'):
        name = last(group['Denominacion_caso']) or last(group['caso_act'])
        if not name:
            continue  # provisional rows without a case name cannot be shown as a conflict
        observations = [{'period': r.fecha.strftime('%Y-%m'), 'status': r.Estado if isinstance(r.Estado, str) else None,
                         'phase': r.Fase_activos if isinstance(r.Fase_activos, str) else None,
                         'dialogue_status_text': r.Estado_dialogo_act if isinstance(r.Estado_dialogo_act, str) else (r.Momento_dialogo if isinstance(r.Momento_dialogo, str) else None)}
                        for r in group.itertuples() if pd.notna(r.fecha)]
        cases.append({
            'historical_research_id': int(number), 'name': name,
            'description': last(group['Descripcion_act']) or last(group['caso_act']),
            'department': last(group['Departamento_num']) or last(group['Departamento_act']),
            'province': last(group['Provincia_num']) or last(group['Provincia_act']),
            'district': last(group['Distrito_num']) or last(group['Distrito_act']),
            'type': last(group['Tipo_conflicto_act']),
            'actors': {'primarios': last(group['Actores_Primarios']), 'secundarios': last(group['Actores_Secundarios']), 'terciarios': last(group['Actores_Terciarios'])},
            'first_period': observations[0]['period'], 'last_period': observations[-1]['period'],
            'last_status': next((o['status'] for o in reversed(observations) if o['status']), None),
            'last_phase': next((o['phase'] for o in reversed(observations) if o['phase']), None),
            'provisional_id': int(number) >= 9000,
            'observations': observations})
    cases.sort(key=lambda c: c['last_period'], reverse=True)
    out = {'company': company, 'term': term, 'source_workbook': Path(workbook).name, 'sheet': '02_base_unificada',
           'method': f'Casos de la base de tesis (reportes mensuales de la Defensoría 2012-2025) donde "{term}" aparece en la denominación, la descripción, las empresas o los actores.',
           'cases': cases}
    target = ROOT / 'demo_data' / f'historical_{company}.json'
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(cases)} casos · {sum(len(c["observations"]) for c in cases)} observaciones mensuales en {target}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
