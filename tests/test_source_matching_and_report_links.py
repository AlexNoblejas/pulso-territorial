"""Real homonym counterexamples, original-document attribution and report PDF links."""
import json
import re
import unicodedata
from urllib.parse import urljoin

from pypdf import PdfReader

from pulso import corpus, news, reports

def classify(title,snippet=''):
    return news.classify({'title':title,'snippet':snippet})

def test_pijuayal_in_iparia_ucayali_is_not_manseriche_conflict():
    title='OFIS llevó la Clasificación Socioeconómica a 14 comunidades nativas durante primera campaña aérea en Ucayali'
    snippet='En el distrito de Iparía se atendió a la comunidad de Pijuayal, de lengua asháninka.'
    assert classify(title,snippet)[:2]==([],[])

def test_generic_loreto_in_multi_region_pias_notice_is_not_an_anchor():
    assert classify('PIAS Aérea atiende Loreto y Ucayali','Puntos de atención de Ucayali: Pijuayal, Sawawo y Paititi.')[:2]==([],[])

def test_petroperu_elsewhere_in_ucayali_text_does_not_link_its_pijuayal_to_onp():
    companies,cases,_=classify('Petroperú y servicios en Ucayali','Pijuayal del distrito de Iparía fue atendido.')
    assert companies==['hidrocarburos']  # company mention is genuine; the case identity is not.
    assert cases==[]

def test_pijuayal_with_specific_manseriche_anchor_links_correct_case():
    assert classify('Derrame en Pijuayal, distrito de Manseriche')[:2]==(['hidrocarburos'],['1403-0325'])

def test_fuerabamba_sports_story_does_not_link_company_or_conflict():
    companies,cases,tags=classify('Defensor Patibamba pide a la LINFA revisar el estadio de Fuerabamba antes de la vuelta')
    assert companies==[] and cases==[]

def test_legitimate_fuerabamba_blockade_keeps_existing_link():
    companies,cases,tags=classify('Comuneros de Fuerabamba bloquean el corredor minero')
    assert companies==['mineria'] and cases==['1132-1218']
    assert 'Medida de fuerza' in tags

def test_news_cache_is_reclassified_without_network_or_rewriting_it(tmp_path,monkeypatch):
    path=tmp_path/'news.json'
    raw={'items':[{'title':'Defensor Patibamba pide a la LINFA revisar el estadio de Fuerabamba antes de la vuelta',
                   'snippet':'','companies':['mineria'],'case_codes':['1132-1218'],'tags':['Contexto']}], 'feeds':[]}
    path.write_text(json.dumps(raw),encoding='utf-8')
    before=path.read_bytes()
    monkeypatch.setattr(news,'PATH',path)
    assert news.load()['items']==[]
    assert path.read_bytes()==before

def registry(monkeypatch):
    monkeypatch.setattr(corpus,'load',lambda:{'documents':{'PCM':{'file':'PCM_Willaqniki_5_SetOct_2024.pdf','pages':52}}})

def test_registered_corpus_page_resolves_under_pages_and_local_api(monkeypatch):
    registry(monkeypatch)
    target=reports.href('corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=38')
    assert target=='../corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=38'
    assert urljoin('https://alexnoblejas.github.io/pulso-territorial/static/report_mineria.html',target)=='https://alexnoblejas.github.io/pulso-territorial/corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=38'
    assert urljoin('http://127.0.0.1:8765/api/report?company=mineria',target)=='http://127.0.0.1:8765/corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=38'

def test_pdf_without_page_still_opens_registered_original(monkeypatch):
    registry(monkeypatch)
    assert reports.href('corpus/PCM_Willaqniki_5_SetOct_2024.pdf')=='../corpus/PCM_Willaqniki_5_SetOct_2024.pdf'

def test_unregistered_unsafe_or_invalid_local_targets_are_rejected(monkeypatch):
    registry(monkeypatch)
    for target in ['javascript:alert(1)','data:text/html,x','//evil.example/x','/corpus/PCM_Willaqniki_5_SetOct_2024.pdf',
                   'corpus/../x.pdf','corpus/%2e%2e/x.pdf','corpus/..\\x.pdf','corpus/unregistered.pdf#page=1',
                   'corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=0','corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=53',
                   'corpus/PCM_Willaqniki_5_SetOct_2024.pdf?x=1','corpus/PCM_Willaqniki_5_SetOct_2024.pdf#page=1&evil=x',None,42]:
        assert reports.href(target)=='#',target
    assert reports.href('https://www.gob.pe/example')=='https://www.gob.pe/example'

def test_minam_annex_attribution_matches_original_oefa_table_not_conflict_phase():
    config=json.loads(corpus.CONFIG.read_text(encoding='utf-8'))
    passage=next(p for p in config['passages'] if p['document_id']=='MINAM-OGASA-09-2025' and p['page']==35)
    document=next(d for d in config['documents'] if d['id']==passage['document_id'])
    original=PdfReader(str(corpus.DIRECTORY/document['file'])).pages[passage['page']-1].extract_text()
    normalized=lambda text:re.sub(r'\s+','',unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower())
    page=normalized(original)
    assert 'casospriorizadosoefa' in page
    assert 'lineadeaccion' in page
    assert 'informaciondeloefaajuliode2025' in page
    assert normalized(passage['quote']) in page
    assert passage['upstream_institution']=='OEFA' and passage['source_period']=='2025-07'
    assert 'línea de acción' in passage['title'] and 'fase de prevención' not in passage['title']
    assert 'no es una fase oficial' in passage['relation']
