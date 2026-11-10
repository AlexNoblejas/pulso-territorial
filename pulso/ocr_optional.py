"""Optional PaddleOCR 3.x adapter. Does not mutate PDF bytes or database pages.

Only pages with fewer than 40 normalized characters and method=pypdf qualify.
Results are candidates pending human review; recognition scores are not accuracy.
Real Paddle engine is NOT exercised by the simulated unit tests.
"""
from __future__ import annotations

import hashlib
import math
import re
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Callable, Iterable, Mapping


def candidates(pages: Iterable[Mapping], limit: int = 2) -> list[dict]:
    if not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError('El límite OCR debe estar entre 1 y 10 páginas.')
    eligible = []
    for page in pages:
        if page.get('method') != 'pypdf':
            continue
        text = page.get('text', '')
        number = page.get('page')
        if not isinstance(text, str) or type(number) is not int or number < 1:
            raise ValueError('Página PDF o texto original no válido.')
        if len(re.sub(r'\s+', ' ', text).strip()) < 40:
            eligible.append(dict(page))
    return sorted(eligible, key=lambda p: p['page'])[:limit]


def create_engine():
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError('OCR opcional no instalado. Consulta docs/OCR_OPCIONAL.md.') from exc
    return PaddleOCR(lang='es', device='cpu', ocr_version='PP-OCRv5',
                     use_doc_orientation_classify=False,
                     use_doc_unwarping=False, use_textline_orientation=False)


def normalize_prediction(result) -> dict:
    """Read documented Paddle result.json or dict representation; fail closed.

    PaddleX result JSON generally wraps OCR fields under `res`; direct dicts
    are also accepted to allow supported result objects and deterministic tests.
    """
    data = result if isinstance(result, Mapping) else getattr(result, 'json', None)
    if not isinstance(data, Mapping):
        raise ValueError('PaddleOCR no devolvió un objeto JSON reconocido.')
    data = data.get('res', data)
    if not isinstance(data, Mapping) or 'rec_texts' not in data or 'rec_scores' not in data:
        raise ValueError('Faltan rec_texts o rec_scores en PaddleOCR.')
    try:
        texts, scores = list(data['rec_texts']), list(data['rec_scores'])
    except TypeError as exc:
        raise ValueError('Listas OCR no válidas.') from exc
    if isinstance(data['rec_texts'], (str, bytes)) or len(texts) != len(scores):
        raise ValueError('Textos y puntuaciones OCR no están alineados.')
    lines = []
    for text, score in zip(texts, scores):
        if not isinstance(text, str):
            raise ValueError('Una línea OCR no es texto.')
        try:
            score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError('Puntuación OCR no numérica.') from exc
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Puntuación OCR fuera de rango.')
        if text.strip():
            lines.append({'text': text, 'score': score})
    return {'text': '\n'.join(line['text'] for line in lines), 'lines': lines}


def render_page(pdf_data: bytes, number: int, target: Path, *, dpi: int = 160):
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('Instala PyMuPDF para renderizar las páginas OCR.') from exc
    with fitz.open(stream=pdf_data, filetype='pdf') as doc:
        if number > len(doc):
            raise ValueError('El número de página no existe en el PDF original.')
        page = doc[number - 1]
        # Bound memory independently of a malicious or unusually large page size.
        zoom = min(dpi / 72, (12_000_000 / max(1, page.rect.width * page.rect.height)) ** .5)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False)
        pix.save(str(target))


def recognize_pending(pdf_data: bytes, pages: Iterable[Mapping], *, limit: int = 2,
                      engine=None, renderer: Callable = render_page,
                      temp_root: str | Path | None = None) -> list[dict]:
    """Return append-only OCR candidates. Caller persists them separately.

    Failure never replaces original pypdf text. Reusing the engine avoids costly
    model initialization. Real engine may download model weights on first use.
    """
    selected = candidates(pages, limit)
    if not selected:
        return []
    if not isinstance(pdf_data, bytes) or not pdf_data.lstrip().startswith(b'%PDF-'):
        raise ValueError('Se necesita el PDF original para ejecutar OCR.')
    engine = engine if engine is not None else create_engine()
    try:
        engine_version = version('paddleocr')
    except Exception:
        engine_version = 'no_verificada'
    digest = hashlib.sha256(pdf_data).hexdigest()
    output = []
    with tempfile.TemporaryDirectory(prefix='pulso_ocr_', dir=temp_root) as folder:
        for page in selected:
            row = {'page': page['page'], 'document_id': page.get('document_id'),
                   'original_sha256': digest, 'original_method': 'pypdf',
                   'original_text': page['text'], 'method': 'paddleocr3',
                   'engine_version': engine_version, 'text': '', 'lines': [],
                   'review_status': 'pendiente_revision_ocr', 'status': 'failed'}
            try:
                png = Path(folder) / f'page_{page["page"]}.png'
                renderer(pdf_data, page['page'], png)
                predictions = list(engine.predict(input=str(png)))
                if len(predictions) != 1:
                    raise ValueError('Se esperaba un único resultado OCR por imagen.')
                parsed = normalize_prediction(predictions[0])
                row.update(parsed)
                row['status'] = 'candidate' if parsed['text'].strip() else 'empty'
                row['low_confidence_lines'] = [i + 1 for i, line in enumerate(parsed['lines']) if line['score'] < .8]
            except Exception as exc:
                row['error'] = type(exc).__name__
            output.append(row)
    return output


if __name__ == '__main__':
    import argparse
    import json
    from contextlib import closing
    from . import service
    parser = argparse.ArgumentParser(description='OCR opcional: candidatos para revisión, sin reemplazar originales')
    parser.add_argument('document_id')
    parser.add_argument('--limit', type=int, default=2)
    args = parser.parse_args()
    service.init_db()
    document = next((d for d in service.list_documents() if d['id'] == args.document_id), None)
    if not document or document['format'] != 'pdf':
        parser.error('Selecciona un identificador de documento PDF de la biblioteca.')
    with closing(service.connect()) as db:
        pages = [dict(r) for r in db.execute('SELECT * FROM pages WHERE document_id=?', (document['id'],))]
    raw = (service.DATA / 'raw' / (document['sha256'] + '.pdf')).read_bytes()
    folder = service.DATA / 'ocr_candidates'
    folder.mkdir(parents=True, exist_ok=True)
    result = recognize_pending(raw, pages, limit=args.limit, temp_root=folder)
    target = folder / (document['id'] + '.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(result)} candidatos OCR guardados para revisión en {target}')
