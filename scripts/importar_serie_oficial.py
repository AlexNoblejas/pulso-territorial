"""Serie mensual oficial 2004-2025 de la Defensoría (totales publicados), de la base histórica del autor.

Uso: python scripts/importar_serie_oficial.py RUTA/Base_historica_2004_2025_v31.xlsx
Lee la hoja SERIE_MENSUAL (cifras transcritas de cada reporte, con su página) y escribe
demo_data/series_oficial.json. Los meses sin reporte quedan sin dato, no en cero.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def number(value):
    try:
        return None if pd.isna(value) else int(value)
    except (TypeError, ValueError):
        return None


def main(workbook):
    df = pd.read_excel(workbook, sheet_name='SERIE_MENSUAL')
    rows = []
    for r in df.itertuples(index=False):
        record = r._asdict()
        period = pd.to_datetime(record['PERIODO'], errors='coerce')
        if pd.isna(period):
            continue
        rows.append({'period': period.strftime('%Y-%m'), 'total': number(record['TOTAL_PUBLICADO']), 'activos': number(record['ACTIVOS']),
                     'latentes': number(record['LATENTES']), 'dialogo': number(record['EN_DIALOGO']),
                     'socioambientales': number(record['SOCIOAMBIENTALES_TOTAL']), 'reporte': number(record['REPORTE_N']),
                     'revision': record.get('ESTADO_REVISION') if isinstance(record.get('ESTADO_REVISION'), str) else None})
    out = {'source_workbook': Path(workbook).name, 'sheet': 'SERIE_MENSUAL',
           'method': 'Totales publicados en cada reporte mensual de la Defensoría del Pueblo (transcritos con su página de PDF). Meses sin reporte o sin cifra quedan vacíos.',
           'series': rows}
    target = ROOT / 'demo_data' / 'series_oficial.json'
    target.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    filled = [r for r in rows if r['total']]
    print(f"{len(rows)} meses · {len(filled)} con total publicado · {filled[0]['period']} a {filled[-1]['period']} · último total {filled[-1]['total']}")


if __name__ == '__main__':
    main(sys.argv[1])
