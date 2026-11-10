import io
import json
from contextlib import closing

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from pulso import service as s
from pulso.cli import update_bulletins


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'DATA', tmp_path)
    s.init_db()


def pdf_bytes(text='Las Bambas registra una mesa de dialogo en Apurimac.'):
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject()
    stream.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode('ascii'))
    page[NameObject('/Contents')] = stream
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def fixture(url=''):
    return s.ingest_upload(pdf_bytes(), 'reporte.pdf', '2026-04', url=url)


def test_real_pdf_extraction_search_and_bulletin():
    fixture()
    hits = s.search('Las Bambas Apurímac')
    assert len(hits) == 1
    assert hits[0]['page'] == 1
    assert 'mesa de dialogo' in hits[0]['text']
    assert s.search('Las Bambas Cajamarca') == []
    assert 'página PDF 1' in s.bulletin(hits)


def test_content_deduplication_and_source_enrichment():
    first = fixture()
    second = fixture('https://www.defensoria.gob.pe/report.pdf')
    assert first['id'] == second['id']
    assert second['existing'] and second['url'].startswith('https://')
    assert s.stats()['documents'] == 1


def test_rejects_fake_pdf_and_tracks_scanned_pages():
    with pytest.raises(ValueError):
        s.ingest_upload(b'not a PDF', 'fake.pdf')
    row = s.ingest_upload(pdf_bytes(''), 'scan.pdf')
    assert row['ocr_pending'] == 1


@pytest.mark.parametrize('url', ['http://www.defensoria.gob.pe/a', 'https://evil.example/a', 'https://www.defensoria.gob.pe.evil.example/a', 'https://user@www.defensoria.gob.pe/a'])
def test_source_allowlist(url):
    with pytest.raises(ValueError):
        s._allowed(url)


def test_html_is_section_not_pdf_page():
    text = 'Reporte de Conflictos Sociales septiembre de 2026. ' + 'Las Bambas participa en una mesa de diálogo. ' * 100
    row = s.ingest_html(f'<html><body><main>{text}</main></body></html>'.encode(), 'RCS.html', 'https://www.defensoria.gob.pe/rcs.html')
    assert row['period'] == '2026-09'
    assert s.search('Bambas')[0]['method'] == 'html_section'
    assert 'sección de extracción HTML' in s.bulletin(s.search('Bambas'))
    with pytest.raises(ValueError):
        s.ingest_html(b'<html>Mantenimiento</html>', 'bad', '')


@pytest.mark.parametrize('period_text,expected', [('RCS_271_setiembre_2026.html','2026-09'), ('Reporte ABRIL DE 2026','2026-04'), ('sin fecha','')])
def test_report_period(period_text, expected):
    assert s.report_period(period_text.replace('_', ' ')) == expected


def test_invalid_model_outputs_fail_closed():
    context = [{'source_id':'E1','document_id':'D','page':1,'method':'pypdf','text':'Existe una reunión documentada para discutir demandas.'}]
    for parsed in [{'other':True}, {'records':'wrong'}, {'records':[{'source_id':[], 'quote':'x', 'claim':'x'}]}, {'records':[{'source_id':'E1','quote':'Cita inventada inexistente', 'claim':'hecho'}]}]:
        records, errors = s.validate_records(parsed, context)
        assert not records and errors
    records, errors = s.validate_records({'records':[{'source_id':'E1','quote':context[0]['text'], 'claim':'La fuente reporta reunión.', 'type':'hecho'}]}, context)
    assert not errors and records[0]['review_status'] == 'pendiente_revision_semantica'


def test_missing_key_and_budget_do_not_call_api(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    with pytest.raises(ValueError, match='GROQ_API_KEY'):
        s.ask('Qué', [{'text':'a'}], 'groq')
    monkeypatch.setenv('GROQ_API_KEY', 'test-fixture')
    monkeypatch.setenv('PULSO_DAILY_TOKEN_CAP', '1')
    calls = []
    monkeypatch.setattr(s.requests, 'post', lambda *a, **k: calls.append(True))
    with pytest.raises(ValueError, match='límite'):
        s.ask('Qué se reporta', [{'document_id':'D','page':1,'text':'Una reunión documentada.', 'method':'pypdf'}], 'groq')
    assert calls == []


def test_mock_provider_json_and_usage(monkeypatch):
    fixture()
    hits = s.search('Bambas')
    monkeypatch.setenv('GROQ_API_KEY','test-fixture')
    monkeypatch.setenv('PULSO_DAILY_TOKEN_CAP','60000')
    class Response:
        status_code = 200
        def json(self):
            return {'choices':[{'message':{'content':json.dumps({'records':[{'source_id':'E1','quote':hits[0]['text'], 'claim':'La fuente reporta una mesa.', 'type':'hecho'}]})}}], 'usage':{'total_tokens':100}}
    def request(*a, **k):
        assert k['json']['response_format']['json_schema']['strict'] is True
        return Response()
    monkeypatch.setattr(s.requests, 'post', request)
    assert s.ask('Qué reporta',hits,'groq')['records']
    with closing(s.connect()) as db:
        assert db.execute('SELECT actual,status FROM ai_usage').fetchone()['actual'] == 100


def test_same_url_new_content_keeps_both_versions(monkeypatch):
    url = 'https://www.defensoria.gob.pe/report.pdf'
    fixture(url)
    monkeypatch.setattr(s, 'discover', lambda:[url])
    monkeypatch.setattr(s, 'fetch', lambda u:(pdf_bytes('Segunda version documental con acuerdos nuevos.'),u))
    result = s.sync_sources(1)
    assert result['downloaded'] == 1
    assert s.stats()['documents'] == 2
    # Next immediate run respects the daily recheck interval.
    assert s.sync_sources(1)['downloaded'] == 0


def test_bad_seed_does_not_block_next_run(monkeypatch):
    bad = 'https://www.defensoria.gob.pe/bad.pdf'
    good = 'https://www.defensoria.gob.pe/good.pdf'
    monkeypatch.setattr(s,'discover',lambda:[bad,good])
    monkeypatch.setattr(s,'fetch',lambda u:(b'not a PDF' if u==bad else pdf_bytes(),u))
    assert s.sync_sources(1)['errors']
    assert s.sync_sources(1)['downloaded'] == 1


def test_automatic_bulletin_changes_only_when_evidence_changes():
    fixture()
    assert update_bulletins()
    assert update_bulletins() == []
    assert (s.DATA/'bulletins'/'las-bambas.md').exists()
