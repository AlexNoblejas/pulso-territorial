import pytest
from pulso import assistant as a


def sample():
    return {'period':'2026-09','cases':[{'id':'llata','name':'Llata - Antamina','summary':'síntesis editorial',
        'original_description':'La comunidad solicita seguimiento del diálogo documentado.', 'source_ids':['DP'],
        'events':[{'kind':'reporte oficial','summary':'La reunión reportada ocurrió en septiembre.'},
          {'source_id':'PCM','title':'Willaqniki','summary':'Llata: se reportó una mesa de diálogo.', 'literal':True,'page':38,'pdf_url':'corpus/PCM.pdf#page=38','period':'2025-01'},
          {'source_id':'NEWS','title':'titular no es cita','summary':'No usar como cita literal de PDF.','literal':False,'page':3}]}],
        'sources':[{'id':'DP','title':'RCS','institution':'Defensoría del Pueblo','url':'https://www.defensoria.gob.pe/reporte.html'}, {'id':'PCM','title':'Willaqniki','institution':'PCM','url':'corpus/PCM.pdf'}]}


def test_retrieval_contains_real_pdf_locator_and_original_not_editorial():
    items=a.candidates(sample())
    assert len(items)==2
    assert 'síntesis editorial' not in items[0]['text']
    assert items[0]['page'] is None
    assert items[1]['page']==38 and items[1]['locator']=='Página PDF 38'


def test_navigation_only_known_views_and_case_ids():
    assert a.navigation('Abre Llata',sample())==[{'type':'open_case','case_id':'llata'}]
    assert a.navigation('Muéstrame las alertas',sample())==[{'type':'navigate','view':'alertas'}]
    assert a.navigation('Borra los reportes',sample())==[]
    assert a.navigation('Envía correos a todos',sample())==[]
    assert a.navigation('¿Qué dijo Llata?',sample())==[]


@pytest.mark.parametrize('url',['javascript:alert(1)','//evil.example/x','corpus/../secret.pdf','C:\\secret.pdf'])
def test_unsafe_source_urls_rejected(url):
    assert a.safe_source_url(url)==''


def test_unknown_question_does_not_call_model(monkeypatch):
    monkeypatch.setattr(a.portfolio,'portfolio',lambda c,p=None:sample())
    monkeypatch.setattr(a.service,'_call',lambda *args:pytest.fail('no model request expected'))
    assert a.answer('resultado del mundial de fútbol')['mode']=='sin evidencia'


def test_answer_returns_linked_validated_sources(monkeypatch):
    monkeypatch.setattr(a.portfolio,'portfolio',lambda c,p=None:sample())
    monkeypatch.setattr(a.service,'provider_status',lambda:{'groq':True})
    monkeypatch.setattr(a.service,'init_db',lambda:None)
    def call(provider,task,hits):
        quote=hits[0]['text'].split('\n')[0]
        context=[{'source_id':'E1',**hits[0]}]
        return {'records':[{'type':'respuesta','claim':'La fuente reporta seguimiento.','quote':quote,'source_id':'E1'}]},'fixture-model',{'total_tokens':10},context
    monkeypatch.setattr(a.service,'_call',call)
    result=a.answer('¿Qué reporta Llata sobre diálogo?')
    assert result['sources'][0]['locator'].startswith('Ficha del caso')
    assert result['sources'][0]['page'] is None
    assert '[E1]' in result['answer'] and 'sección HTML 1' not in result['answer']


def test_selected_period_and_case_are_enforced(monkeypatch):
    seen=[]
    def data(company,period=None):
        seen.append((company,period))
        return sample()
    monkeypatch.setattr(a.portfolio,'portfolio',data)
    result=a.answer('Abre Llata','antamina',period='2026-09',case_id='llata')
    assert result['actions']==[{'type':'open_case','case_id':'llata'}]
    assert seen==[('antamina','2026-09')]
    with pytest.raises(ValueError,match='no pertenece'):
        a.answer('Abre Llata','antamina',case_id='otro-cliente')
