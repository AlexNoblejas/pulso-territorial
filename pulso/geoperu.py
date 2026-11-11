"""Capas territoriales de GEOPERÚ (geoservidor del MINAM) por ArcGIS REST (sesión 06).

Mismo protocolo que el MCP de GEOPERÚ de la tarea 4: consultas /query con f=geojson, recortadas al
área de cada cartera y simplificadas. Sin clave. Resultado en data/geoperu_<cartera>.json.
También calcula el contexto territorial de cada caso (comunidad, cuenca, ANP, pasivos, derechos).
Ejecutar: python -m pulso.geoperu
"""
import json
import math
import re
import sys
import time

import requests
from shapely.geometry import Point, shape

from . import news, service

ROOT_URL='https://geoservidorperu.minam.gob.pe/arcgis/rest/services'
EXTENTS={'mineria':(-73.2,-14.8,-71.8,-13.5),'hidrocarburos':(-78.2,-5.3,-75.7,-2.7)}
INVERSION='Servicio_Oportunidades_Inversion'
# key, etiqueta, servicio, capa, filtro, campos, color
LAYERS={
    'mineria':[
        ('concesiones_empresa','Concesiones de Minera Las Bambas',INVERSION,25,"TIT_CONCES LIKE '%LAS BAMBAS%'",['CONCESION','TIT_CONCES','D_ESTADO','SUSTANCIA','DISTRI'],'#2563b9'),
        ('comunidades_oficiales','Comunidades campesinas (MIDAGRI)',INVERSION,26,'1=1',['nom_comuni','nom_dist','nom_prov'],'#bd9b6e'),
        ('cuencas','Unidades hidrográficas',INVERSION,4,'1=1',['NOMBRE','NIVEL','CODIGO'],'#4f8fb8'),
        ('anp','Áreas naturales protegidas (SERNANP)',INVERSION,31,'1=1',['anp_nomb','anp_cate'],'#3f8f5a'),
        ('pasivos','Pasivos ambientales mineros 2022',"ServicioActivacionQuebrada",14,'1=1',['TIPO','SUBTIPO','DISTRITO','RESPONSAB','N_DE_MINER'],'#a5483c')],
    'hidrocarburos':[
        ('lotes','Lotes petroleros (Petroperú)',INVERSION,28,'1=1',['nom_lotes','cia','estado','contrato'],'#2563b9'),
        ('oleoducto','Oleoducto Norperuano (MINAM)','hiroambienplanificacion/elementos_expuestos',9,'1=1',['nombre','tipo_ih','ubi_dist'],'#1f2937'),
        ('comunidades_oficiales','Comunidades nativas (MIDAGRI)',INVERSION,27,'1=1',['nom_comuni','federacion','etnia','nom_dist'],'#bd9b6e'),
        ('cuencas','Unidades hidrográficas',INVERSION,4,'1=1',['NOMBRE','NIVEL','CODIGO'],'#4f8fb8'),
        ('anp','Áreas naturales protegidas (SERNANP)',INVERSION,31,'1=1',['anp_nomb','anp_cate'],'#3f8f5a'),
        ('pasivos','Pasivos ambientales de hidrocarburos 2022',"ServicioActivacionQuebrada",15,'1=1',['Lote','Descri_Pas','Distrito','Nom_Cuenca'],'#a5483c')]}


def _round(value):
    if isinstance(value,float):
        return round(value,4)
    if isinstance(value,list):
        return [_round(v) for v in value]
    return value


def query(service_name,layer,where,fields,extent,offset=0.003):
    url=f'{ROOT_URL}/{service_name}/MapServer/{layer}/query'
    features,start=[],0
    while True:
        params={'where':where,'geometry':','.join(map(str,extent)),'geometryType':'esriGeometryEnvelope','inSR':4326,
                'spatialRel':'esriSpatialRelIntersects','outFields':','.join(fields),'returnGeometry':'true','outSR':4326,
                'maxAllowableOffset':offset,'resultOffset':start,'resultRecordCount':1000,'f':'geojson'}
        response=requests.get(url,params=params,headers={'User-Agent':news.USER_AGENT},timeout=(10,120))
        response.raise_for_status()
        data=response.json()
        if 'error' in data:
            raise ValueError(data['error'].get('message','ArcGIS error'))
        batch=data.get('features',[])
        for feature in batch:
            if feature.get('geometry'):
                feature['geometry']['coordinates']=_round(feature['geometry']['coordinates'])
                features.append({'type':'Feature','geometry':feature['geometry'],'properties':{k:feature['properties'].get(k) for k in fields}})
        if not data.get('exceededTransferLimit') and len(batch)<1000:
            return features
        start+=len(batch)
        time.sleep(0.5)


def update(company):
    result={'company':company,'fetched_at':service.now(),'server':ROOT_URL,'extent':EXTENTS[company],'layers':{}}
    for key,label,service_name,layer,where,fields,color in LAYERS[company]:
        source=f'{ROOT_URL}/{service_name}/MapServer/{layer}'
        try:
            features=query(service_name,layer,where,fields,EXTENTS[company])
            result['layers'][key]={'label':label,'source':source,'where':where,'color':color,'count':len(features),'ok':True,
                                   'data':{'type':'FeatureCollection','features':features}}
        except Exception as exc:
            previous=load(company).get('layers',{}).get(key)
            result['layers'][key]={**(previous or {'label':label,'source':source,'color':color,'count':0,'data':{'type':'FeatureCollection','features':[]}}),
                                   'ok':False,'error':f'{type(exc).__name__}: {str(exc)[:120]}'}
    path=service.DATA/f'geoperu_{company}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    return result


def load(company):
    for path in (service.DATA/f'geoperu_{company}.json',service.ROOT/'demo_data'/f'geoperu_{company}.json'):
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return {'layers':{}}


def _km(geometry,point):
    # Degrees to km with the local longitude scale; enough for a 1-50 km context reading.
    distance=geometry.distance(point)
    latitude=point.representative_point().y
    return round(distance*111.32*math.sqrt((1+math.cos(math.radians(latitude))**2)/2),1)


def context(company,coordinates,precision='',name=''):
    """Territorial context of a case. A district reference point is never read as a community location;
    when the community named in the case has an official polygon, distances are measured from it."""
    layers=load(company).get('layers',{})
    shapes={key:[(shape(f['geometry']),f['properties']) for f in layer['data']['features']] for key,layer in layers.items()}
    rows=[]
    words=[w for w in news.CASES if w in service.norm(name)]
    polygon=next(((geom,props) for geom,props in shapes.get('comunidades_oficiales',[])
                  if any(re.search(r''+re.escape(w)+r'',service.norm(props.get('nom_comuni') or '')) for w in words)),None)
    if polygon:
        geometry=polygon[0]
        rows.append({'label':'Polígono oficial de la comunidad','value':f"{polygon[1]['nom_comuni']} · {polygon[1].get('nom_dist') or ''} (MIDAGRI vía GEOPERÚ)",'layer':'comunidades_oficiales'})
    elif coordinates:
        geometry=Point(coordinates)
        if 'comunal' in service.norm(precision):
            found=next((props.get('nom_comuni') for geom,props in shapes.get('comunidades_oficiales',[]) if geom.contains(geometry)),None)
            rows.append({'label':'Comunidad titulada en el punto','value':found or 'Ninguna','layer':'comunidades_oficiales'})
        else:
            rows.append({'label':'Polígono de la comunidad','value':'No encontrado en la capa oficial; se usa el punto distrital','layer':'comunidades_oficiales'})
    else:
        return None
    center=geometry.representative_point()
    def nearest(key,field):
        found=sorted(((_km(geom,geometry),props.get(field)) for geom,props in shapes.get(key,[])),key=lambda x:x[0])
        return {'name':found[0][1],'km':found[0][0]} if found else None
    basin=next((props.get('NOMBRE') for geom,props in shapes.get('cuencas',[]) if geom.contains(center)),None)
    rows.append({'label':'Unidad hidrográfica','value':basin or 'No identificada','layer':'cuencas'})
    anp=nearest('anp','anp_nomb')
    rows.append({'label':'Área natural protegida más cercana','value':f"{anp['name']} · {anp['km']} km" if anp else 'Ninguna en el área de la cartera','layer':'anp'})
    near=[_km(geom,geometry) for geom,props in shapes.get('pasivos',[])]
    rows.append({'label':'Pasivos ambientales a menos de 10 km','value':str(sum(d<=10 for d in near)),'layer':'pasivos'})
    for key,field,label in [('concesiones_empresa','CONCESION','Concesión de la empresa más cercana'),('lotes','nom_lotes','Lote petrolero más cercano'),('oleoducto','nombre','Distancia al oleoducto')]:
        if key in shapes:
            item=nearest(key,field)
            text=('0 km (se superponen)' if item and item['km']==0 else f"{item['km']} km") if item else 'Sin dato'
            rows.append({'label':label,'value':text if key=='oleoducto' else (f"{item['name']} · {text}" if item else text),'layer':key})
    for row in rows:
        row['basis']='Polígono comunal oficial' if polygon else ('Punto comunal' if 'comunal' in service.norm(precision) else 'Punto distrital referencial')
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    for company in EXTENTS:
        data=update(company)
        print(company,{k:(v['count'],'ok' if v['ok'] else v.get('error')) for k,v in data['layers'].items()})


if __name__=='__main__':
    main()
