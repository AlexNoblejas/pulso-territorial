import importlib.util
from pathlib import Path

import pytest

from pulso import ocr_optional as ocr


def test_selects_only_sparse_pdf_pages():
    pages = [{'page': 3, 'method': 'html_section', 'text': ''},
             {'page': 2, 'method': 'pypdf', 'text': 'x' * 39},
             {'page': 1, 'method': 'pypdf', 'text': 'x' * 40}]
    assert [p['page'] for p in ocr.candidates(pages)] == [2]


def test_documented_wrapped_json():
    class Result:
        json = {'res': {'rec_texts': ['Texto público', ''], 'rec_scores': [.99, .5]}}
    assert ocr.normalize_prediction(Result()) == {'text': 'Texto público', 'lines': [{'text': 'Texto público', 'score': .99}]}


@pytest.mark.parametrize('value', [
    {'rec_texts': ['one'], 'rec_scores': []},
    {'rec_texts': ['one'], 'rec_scores': [float('nan')]},
    {'rec_texts': ['one'], 'rec_scores': [1.1]},
    {'unknown': []},
])
def test_rejects_invalid_result(value):
    with pytest.raises(ValueError):
        ocr.normalize_prediction(value)


def test_mock_ocr_preserves_original_and_marks_review(tmp_path):
    class Engine:
        def predict(self, input):
            assert Path(input).exists()
            return [{'rec_texts': ['Línea OCR'], 'rec_scores': [.7]}]
    pages = [{'document_id': 'D1', 'page': 1, 'method': 'pypdf', 'text': 'Original'}]
    def render(data, page, output):
        output.write_bytes(b'simulated-image')
    result = ocr.recognize_pending(b'%PDF-fixture', pages, engine=Engine(), renderer=render, temp_root=tmp_path)
    assert pages[0]['text'] == 'Original'
    assert result[0]['original_text'] == 'Original'
    assert result[0]['status'] == 'candidate'
    assert result[0]['review_status'] == 'pendiente_revision_ocr'
    assert result[0]['low_confidence_lines'] == [1]
    assert list(tmp_path.iterdir()) == []


def test_failure_keeps_source(tmp_path):
    class Engine:
        def predict(self, input):
            raise RuntimeError('simulated')
    result = ocr.recognize_pending(b'%PDF-fixture', [{'page': 1, 'method': 'pypdf', 'text': ''}],
                                   engine=Engine(), renderer=lambda *a: None, temp_root=tmp_path)
    assert result[0]['status'] == 'failed'
    assert result[0]['original_text'] == ''
    assert result[0]['error'] == 'RuntimeError'


def test_no_candidate_does_not_initialize_engine(monkeypatch):
    monkeypatch.setattr(ocr, 'create_engine', lambda: pytest.fail('must not load Paddle'))
    assert ocr.recognize_pending(b'%PDF-fixture', [{'page': 1, 'method': 'pypdf', 'text': 'x' * 40}]) == []

