"""Todos los conflictos activos del país, desde las fichas del último reporte HTML de la Defensoría,
y el historial nacional 2012-2025 de la base de tesis (demo_data/historical_national.json).

Cada conflicto conserva su código oficial, ubicación, tipo, fase, diálogo, actores y hechos del mes.
Se marca si nombra a una empresa de las carteras y si ocurre en el territorio de sus operaciones.
"""
import json
import re

from bs4 import BeautifulSoup

from . import service

PATH=service.DATA/'national.json'
SEED=service.ROOT/'demo_data'/'national.json'
HISTORY=service.ROOT/'demo_data'/'historical_national.json'
# Departamentos donde opera cada cartera (territorio para la vista "mi territorio").
TERRITORY={'antamina':['ancash','huanuco'],'mineria':['apurimac','cusco'],'hidrocarburos':['loreto','amazonas','piura']}
COMPANY_TERMS={'antamina':['antamina'],'mineria':['las bambas','mmg'],'hidrocarburos':['petroperu','oleoducto norperuano']}


def parse_location(text,region=''):
    """District, province and department from the many ways the Defensoría writes a location."""
    t=service.norm(text).replace('(*)','')
    stop=r'(?=,| y | e |\.|;| - |$)'
    district=re.search(r'distritos?(?: y provincia)?(?: de)? ([a-z ]+?)'+stop,t)
    province=re.search(r'provincias?(?: y departamento)?(?: de)?(?: del| de la)? ([a-z ]+?)'+stop,t)
    if district and re.search(r'distrito y provincia de',t) and not province:
        province=district
    department=service.norm(region).replace('lima metropolitana','lima').replace('lima provincias','lima')
    clean=lambda m:m[1].strip().upper() if m else ''
    return clean(district),clean(province),department.upper() if department not in ('multirregional','nacional') else ''


def locate(geocodes,district,province,department):
    for key,precision in [(f'{district}|{province}','punto representativo distrital'),(district if not province else None,'punto representativo distrital'),
                          (f'PROV:{province}','punto representativo provincial'),(f'DEP:{department}','punto representativo departamental')]:
        if key and key in geocodes and not key.endswith(':'):
            return {**geocodes[key],'precision':precision}
    return {}


def build():
    """Parse every case card of the newest HTML report; keep the last good copy if parsing fails."""
    from .portfolio import _chips,_fields,_location,_read,_text
    documents=sorted((d for d in service.list_documents() if d['format']=='html'),key=lambda d:(d['period'],d['ingested_at']))
    if not documents:
        return load()
    document=documents[-1]
    raw=service.DATA/'raw'/(document['sha256']+'.html')
    if not raw.exists():
        return load()
    soup=BeautifulSoup(raw.read_bytes(),'html.parser')
    geocodes=_read('geocodes.json',{}) or json.loads((service.ROOT/'demo_data'/'geocodes.json').read_text(encoding='utf-8'))
    cases=[]
    for card in soup.select('.caso-card[data-codigo]'):
        chips,fields=_chips(card),_fields(card)
        name=_text(card.select_one('.caso-nombre'))
        region=re.search(r'\(([^()]*)\)\s*$',name)
        location=chips.get('Ubicación','')
        district,province,department=parse_location(location,region[1] if region else '')
        point=locate(geocodes,district,province,department)
        geo={'district':district.title(),'province':province.title()}
        text=service.norm(' '.join([name,fields.get('Caso',''),fields.get('Actores primarios','')]))
        department_key=department
        phase_dialogue=chips.get('Fase / Diálogo','')
        cases.append({'code':card['data-codigo'],'name':name,'region':region[1] if region else '','location':location,
                      'district':geo['district'],'province':geo['province'],'department':department_key.title(),
                      'type':_text(card.select_one('.caso-tipo')).replace('Tipo:','').strip(),
                      'phase':_text(card.select_one('.badge')) or phase_dialogue.split('·')[0].strip(),
                      'dialogue':'no hay' not in service.norm(phase_dialogue) and 'hay dialogo' in service.norm(phase_dialogue),
                      'registered':chips.get('Ingreso al registro',''),'competence':chips.get('Competencia',''),'actions_dp':chips.get('Actuaciones DP',''),
                      'description':fields.get('Caso',''),'narrative':_text(card.select_one('.hechos-verbatim')),
                      'actors':{'primarios':fields.get('Actores primarios',''),'secundarios':fields.get('Actores secundarios',''),'terciarios':fields.get('Actores terciarios','')},
                      'companies':[c for c,terms in COMPANY_TERMS.items() if any(t in text for t in terms)],
                      'territory':[c for c,deps in TERRITORY.items() if service.norm(region[1] if region else '') in deps],
                      'coordinates':point.get('coordinates'),'coordinate_precision':point.get('precision','sin georreferencia'),
                      'source_url':document['url'],'period':document['period']})
    if not cases:
        return load()
    data={'period':document['period'],'source':document['url'],'title':document['title'],'built_at':service.now(),'cases':cases}
    PATH.parent.mkdir(parents=True,exist_ok=True)
    PATH.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    return data


def load():
    for path in (PATH,SEED):
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return {'cases':[]}


def history():
    return json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else {}


def payload():
    data=load()
    hist=history()
    return {**data,'history':{k:hist.get(k) for k in ['method','source_rows','series','departments','types_by_year','cases']} if hist else None}
