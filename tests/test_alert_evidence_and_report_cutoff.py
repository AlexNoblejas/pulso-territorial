"""Alert-source resolution and report cutoffs, independent of live feeds and wall-clock date."""
from copy import deepcopy
from datetime import date
import json

import pytest

from pulso import alerts, portfolio, service

TODAY=date(2026,11,11)

def case(**fields):
    return {'id':'C1','name':'Comunidad de prueba','events':[], 'commitments':[],**fields}

def source(sid='DP',**fields):
    return {'id':sid,'title':'Reporte mensual oficial','institution':'Defensoría del Pueblo',
            'url':'https://official.example/report.html','period':'2026-09',**fields}

def test_phase_source_id_resolves_url_institution_period_without_mutation():
    event={'source_id':'DP','kind':'reporte oficial','period':'2026-09','title':'Hechos del período'}
    cases=[case(phase='Crisis',events=[event])]
    sources=[source()]
    original=deepcopy((cases,sources))
    found=alerts.compute(cases,[],[],[],today=TODAY,sources=sources)
    evidence=next(a for a in found if a['rule']=='fase')['evidence'][0]
    assert evidence['url']=='https://official.example/report.html'
    assert evidence['institution']=='Defensoría del Pueblo'
    assert evidence['date']=='2026-09' and evidence['source_id']=='DP'
    assert (cases,sources)==original

def test_commitment_uses_its_own_reference_instead_of_an_unrelated_first_report():
    cases=[case(events=[{'source_id':'DP','kind':'reporte oficial','period':'2026-09'}],
                commitments=[{'text':'Reunión programada','due_date':'2026-11-20','source_id':'PCM'}])]
    sources=[source(),source('PCM',url='https://official.example/pcm/reunion',institution='PCM')]
    found=alerts.compute(cases,[],[],[],today=TODAY,sources=sources)
    deadline=next(a for a in found if a['rule']=='plazo')
    assert deadline['evidence'][0]['url']=='https://official.example/pcm/reunion'
    assert deadline['evidence'][0]['institution']=='PCM'
    assert deadline['date']=='2026-11-20'

def test_press_gap_resolves_news_reference():
    cases=[case(events=[{'source_id':'NEWS-A','kind':'prensa','date':'2026-11-09','title':'Nota reciente'},
                        {'source_id':'DP','kind':'reporte oficial','period':'2026-09'}])]
    sources=[source(),source('NEWS-A',url='https://press.example/nota',institution='Medio público',date='2026-11-09')]
    found=alerts.compute(cases,[],[],[],today=TODAY,sources=sources)
    gap=next(a for a in found if a['rule']=='brecha')
    assert gap['evidence'][0]['url']=='https://press.example/nota'
    assert gap['evidence'][0]['institution']=='Medio público'

def test_discrepancy_expands_refs_preserves_verified_pdf_page_and_deduplicates():
    pdf='corpus/MINAM_OGASA_Mar2025.pdf'
    cases=[case(events=[{'source_id':'DP','kind':'reporte oficial','period':'2026-09'},
                        {'source_id':'MINAM','pdf_url':pdf+'#page=20','page':20,'period':'2025-03'}])]
    sources=[source(),source('MINAM',url=None,pdf_url=pdf,pages=30,institution='MINAM / OGASA',period='2025-03')]
    insights=[{'type':'discrepancia','title':'Fechas distintas','text':'Verificar ambas fechas','case_id':'C1',
               'source_ids':['DP','MINAM','DP','UNKNOWN']}]
    found=alerts.compute(cases,[],[],insights,today=TODAY,sources=sources)
    discrepancy=next(a for a in found if a['rule']=='discrepancia')
    assert len(discrepancy['evidence'])==2
    assert discrepancy['source_ids']==['DP','MINAM']
    pdf_evidence=next(e for e in discrepancy['evidence'] if e['source_id']=='MINAM')
    assert pdf_evidence['url']==pdf+'#page=20' and pdf_evidence['page']==20
    assert discrepancy['unresolved_source_ids']==['UNKNOWN']
    assert discrepancy['evidence_status']=='parcial'
    assert discrepancy['date']=='2026-09'  # a historical discrepancy is not newly dated today.

def test_unknown_reference_does_not_construct_url_or_fall_back_to_unrelated_report():
    cases=[case(events=[{'source_id':'DP','kind':'reporte oficial','period':'2026-09'}],
                commitments=[{'text':'Reunión','due_date':'2026-11-20','source_id':'UNKNOWN'}])]
    found=alerts.compute(cases,[],[],[],today=TODAY,sources=[source()])
    deadline=next(a for a in found if a['rule']=='plazo')
    assert deadline['evidence']==[]
    assert deadline['unresolved_source_ids']==['UNKNOWN']
    assert deadline['evidence_status']=='sin_enlace_incorporado'

def test_unregistered_or_out_of_bounds_relative_pdf_is_not_returned():
    registered=source('MINAM',url=None,pdf_url='corpus/registered.pdf',pages=30)
    assert alerts._evidence({'source_id':'MINAM','pdf_url':'corpus/other.pdf#page=1'}, {'MINAM':registered})['url']=='corpus/registered.pdf'
    evidence=alerts._evidence({'source_id':'MINAM','pdf_url':'corpus/registered.pdf#page=99','page':99},{'MINAM':registered})
    assert evidence['url']=='corpus/registered.pdf' and evidence['page'] is None
    assert alerts._evidence({'pdf_url':'corpus/other.pdf#page=1'}, {}) is None

def test_external_pdf_page_and_standalone_rss_url_are_retained():
    event={'url':'https://official.example/informe.pdf#page=4','page':4,'institution':'Entidad','published':'2026-11-09'}
    assert alerts._evidence(event,{})['url']==event['url']
    assert alerts._evidence(event,{})['page']==4
    assert alerts._evidence({'url':'javascript:alert(1)'},{}) is None

def test_historical_alert_without_document_url_admits_no_incorporated_link():
    history=[{'name':'Caso histórico','last_status':'Activo','last_period':'2024-01'}]
    found=alerts.compute([],[],[],[],today=TODAY,history=history)
    assert found[0]['rule']=='sin_cierre' and found[0]['evidence']==[]
    assert found[0]['evidence_status']=='sin_enlace_incorporado'

@pytest.fixture
def isolated_portfolio(monkeypatch):
    old=source('DP-2026-09',period='2026-09',kind='reporte oficial',title='RCS de septiembre',sha256='old-report-fixture')
    latest=source('DP-2026-10',period='2026-10',kind='reporte oficial',title='RCS 272 de octubre de 2026',sha256='next-report-fixture')
    observation={'period':'2026-09','name':'Llata - Antamina (Huánuco)','status':'Activo',
                 'phase':'Diálogo','phase_basis':'Clasificación reportada','dialogue':True,
                 'region':'Huánuco','province':'Huamalíes','district':'Llata','location':'Distrito de Llata',
                 'coordinates':None,'coordinate_precision':'sin georreferencia',
                 'description':'Reclamos recogidos por la ficha','narrative':'Hechos del mes',
                 'source_id':'DP-2026-09','demands':[],'actors':{}}
    snap={'observations':{'1333-0923':[observation]},'case_companies':{'1333-0923':'antamina'},
          'sources':[old,latest],'supplementary':{'records':[],'newscases':[]},
          'author':'Prueba','built_at':'2026-11-11T10:00:00+00:00'}
    monkeypatch.setattr(portfolio,'_snapshot',lambda:deepcopy(snap))
    monkeypatch.setattr(portfolio,'_read',lambda name,default=None:default or {})
    monkeypatch.setattr(portfolio.news,'load',lambda:{'items':[],'feeds':[]})
    monkeypatch.setattr(portfolio.connectors,'all_items',lambda:[])
    monkeypatch.setattr(portfolio.corpus,'load',lambda:{'documents':{},'passages':[],'signals':[],'problems':[]})
    history=[{'historical_research_id':1,'name':'Antecedente conservado','last_status':'Activo',
              'observations':[{'period':'2025-01','status':'Activo'}]}]
    monkeypatch.setattr(portfolio,'historical',lambda company:(deepcopy(history),[{'period':'2025-01','active':1,'latent':0}]))
    monkeypatch.setattr(portfolio,'stakeholders',lambda company:[])
    monkeypatch.setattr(portfolio,'map_reading',lambda *args:[])
    monkeypatch.setattr(portfolio,'system_status',lambda:{})
    monkeypatch.setattr(portfolio.geoperu,'context',lambda *args:[])
    monkeypatch.setattr(service,'stats',lambda:{'documents':1})
    monkeypatch.setattr(service,'provider_status',lambda:{'groq':False})
    return snap

def test_newest_global_report_can_show_zero_company_cases_without_erasing_history(isolated_portfolio):
    p=portfolio.portfolio('antamina')
    assert p['period']=='2026-10' and p['periods'][0]=='2026-10'
    assert p['cases']==[] and p['summary']['active']==0
    assert len(p['historical_cases'])==1 and len(p['linked_history'])==1
    assert any(s['id']=='DP-2026-10' for s in p['sources'])
    assert p['coverage']['current_source']=='RCS 272 de octubre de 2026'

def test_explicit_older_period_retains_its_company_cases(isolated_portfolio):
    p=portfolio.portfolio('antamina','2026-09')
    assert len(p['cases'])==1 and p['cases'][0]['id']=='1333-0923'
    assert p['period']=='2026-09' and len(p['linked_history'])==1

def test_unknown_global_period_remains_rejected(isolated_portfolio):
    with pytest.raises(ValueError,match='No hay una observación'):
        portfolio.portfolio('antamina','2099-01')

def test_portfolio_resolves_deadline_evidence_without_live_news_or_current_date(isolated_portfolio,tmp_path,monkeypatch):
    # A fixed annotation exercises the actual portfolio -> compute(sources=...) connection.
    config=tmp_path/'config'
    config.mkdir()
    annotations={'period':'2026-09','source_sha256':'old-report-fixture','method':'Fixture documental',
                 'cases':{'1333-0923':{'summary':'Resumen de prueba','demands':[],
                 'commitments':[{'text':'Reunión programada','due_date':'2026-11-20','source_id':'DP-2026-09'}]}}}
    (config/'case_annotations.json').write_text(json.dumps(annotations),encoding='utf-8')
    monkeypatch.setattr(service,'ROOT',tmp_path)
    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY
    monkeypatch.setattr(alerts,'date',FixedDate)
    p=portfolio.portfolio('antamina','2026-09')
    deadline=next(a for a in p['alerts'] if a['rule']=='plazo')
    evidence=deadline['evidence'][0]
    assert evidence['source_id']=='DP-2026-09'
    assert evidence['url']=='https://official.example/report.html'
    assert evidence['institution']=='Defensoría del Pueblo'
    assert deadline['date']=='2026-11-20'
