"""Resume la base de tesis a nivel nacional para la vista 'Conflictos del país' y para Lore.

Uso: python scripts/importar_historico_nacional.py RUTA/base_unificada_conflictos_2012_2025.xlsx
Escribe demo_data/historical_national.json con:
- series: casos registrados por mes y estado (activo, latente, otros);
- departments: casos registrados por mes y departamento;
- types_by_year: conflictos distintos por año y tipo;
- cases: un resumen por conflicto (nombre, ubicación, tipo, período, último estado, empresas).
Cada fila de la base es un conflicto en un mes, según el reporte mensual de la Defensoría.
"""
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


DEPARTMENTS = ['Amazonas', 'Áncash', 'Apurímac', 'Arequipa', 'Ayacucho', 'Cajamarca', 'Callao', 'Cusco', 'Huancavelica', 'Huánuco', 'Ica', 'Junín',
               'La Libertad', 'Lambayeque', 'Lima', 'Loreto', 'Madre de Dios', 'Moquegua', 'Pasco', 'Piura', 'Puno', 'San Martín', 'Tacna', 'Tumbes', 'Ucayali']


def key(text):
    return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode().strip().upper()


CANONICAL = {key(d): d for d in DEPARTMENTS}


def department(value):
    """One spelling per department (the base mixes ANCASH, Ancash and ÁNCASH); other values become 'Multirregional'."""
    value = clean(value)
    if not value:
        return None
    return CANONICAL.get(key(value), 'Multirregional')


def clean(value):
    return value.strip() if isinstance(value, str) and value.strip() and value.strip().lower() != 'nan' else None


def last(series):
    values = [clean(v) for v in series]
    values = [v for v in values if v]
    return values[-1] if values else None


def main(workbook):
    df = pd.read_excel(workbook, sheet_name='02_base_unificada')
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df[df['fecha'].notna()].copy()
    df['period'] = df['fecha'].dt.strftime('%Y-%m')
    df['estado'] = df['Estado'].map(lambda v: clean(v) or 'Sin estado')
    df['departamento'] = df['Departamento_num'].map(department).fillna(df['Departamento_act'].map(department)).fillna('Sin departamento')
    df['tipo'] = df['Tipo_conflicto_act'].map(clean).fillna('Sin tipo')
    series = []
    for period, group in df.groupby('period'):
        counts = group['estado'].value_counts()
        series.append({'period': period, 'total': int(group['Numero'].nunique()), 'activo': int(counts.get('Activo', 0)), 'latente': int(counts.get('Latente', 0))})
    departments = {}
    for (name, period), group in df.groupby(["departamento", "period"]):
        departments.setdefault(name, []).append({'period': period, 'total': int(group['Numero'].nunique())})
    df['year'] = df['fecha'].dt.year
    types_by_year = [{'year': int(year), 'type': tipo, 'conflicts': int(group['Numero'].nunique())} for (year, tipo), group in df.groupby(['year', 'tipo'])]
    cases = []
    for number, group in df.sort_values('fecha').groupby('Numero'):
        name = last(group['Denominacion_caso']) or last(group['caso_act'])
        if not name:
            continue
        cases.append({'id': int(number), 'name': name[:140], 'department': last(group['departamento']), 'province': last(group['Provincia_num']) or last(group['Provincia_act']),
                      'district': last(group['Distrito_num']) or last(group['Distrito_act']), 'type': last(group['tipo']),
                      'first_period': group['period'].iloc[0], 'last_period': group['period'].iloc[-1], 'months': int(group['period'].nunique()),
                      'last_status': last(group['Estado']), 'companies': last(group['Empresas']), 'activity': last(group['Actividad'])})
    out = {'source_workbook': Path(workbook).name, 'source_rows': int(len(df)),
           'method': 'Base de tesis construida con los reportes mensuales de la Defensoría del Pueblo (2012-2025). Una fila es un conflicto en un mes.',
           'series': series, 'departments': departments, 'types_by_year': types_by_year, 'cases': cases}
    target = ROOT / 'demo_data' / 'historical_national.json'
    target.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f'{len(cases)} conflictos · {len(series)} meses · {len(departments)} departamentos · {target.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main(sys.argv[1])
