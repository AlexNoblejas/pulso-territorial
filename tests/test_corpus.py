import json

from pulso import corpus, export


def test_every_configured_passage_is_literal_on_its_page():
    corpus.load.cache_clear()
    library = corpus.load()
    config = json.loads(corpus.CONFIG.read_text(encoding='utf-8'))
    assert library['problems'] == []
    assert len(library['passages']) + len(library['signals']) == len(config['passages']) + len(config['signals'])


def test_tampered_quote_is_rejected(tmp_path, monkeypatch):
    config = json.loads(corpus.CONFIG.read_text(encoding='utf-8'))
    config['passages'][0]['quote'] = config['passages'][0]['quote'].replace('80 %', '95 %')
    fake = tmp_path / 'corpus.json'
    fake.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(corpus, 'CONFIG', fake)
    corpus.load.cache_clear()
    try:
        library = corpus.load()
        assert any('no aparece literal' in problem for problem in library['problems'])
        assert len(library['passages']) == len(config['passages']) - 1
    finally:
        corpus.load.cache_clear()


def test_changed_pdf_hash_is_rejected(tmp_path, monkeypatch):
    config = json.loads(corpus.CONFIG.read_text(encoding='utf-8'))
    config['documents'][0]['sha256'] = '0' * 64
    fake = tmp_path / 'corpus.json'
    fake.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(corpus, 'CONFIG', fake)
    corpus.load.cache_clear()
    try:
        library = corpus.load()
        assert config['documents'][0]['id'] not in library['documents']
    finally:
        corpus.load.cache_clear()


def test_static_export_has_pages_reports_and_pdfs(tmp_path):
    corpus.load.cache_clear()
    site = export.export(tmp_path / 'site')
    assert 'data-static="1"' in (site / 'index.html').read_text(encoding='utf-8')
    for company in ['mineria', 'hidrocarburos']:
        payload = json.loads((site / 'static' / f'portfolio_{company}.json').read_text(encoding='utf-8'))
        assert payload['cases']
        assert (site / 'static' / f'report_{company}.html').exists()
        for event in (e for c in payload['cases'] for e in c['events'] if e.get('literal')):
            if not event['pdf_url'].startswith('http'):
                assert (site / event['pdf_url'].split('#')[0]).exists()
