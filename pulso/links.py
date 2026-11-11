"""Verificación automática de todos los enlaces que muestra la plataforma.

Distingue un enlace roto (404, 410, 5xx) de un servidor que bloquea al verificador (401, 403, 429):
lo segundo no significa que el documento no exista. Resultado en data/links.json.
Ejecutar: python -m pulso.links
"""
from concurrent.futures import ThreadPoolExecutor
import json
import sys

import requests

from . import news, service

PATH=service.DATA/'links.json'


def collect():
    from . import portfolio
    urls={}
    for company in portfolio.COMPANIES:
        p=portfolio.portfolio(company)
        found=[s.get('url') for s in p['sources']]+[s.get('pdf_url') for s in p['sources']]
        found+=[e.get('pdf_url') for c in p['cases'] for e in c['events']]
        found+=[i.get('url') for i in p['media']['items']]+[i.get('url') for i in p['state_actions']]+[i.get('url') for i in p['related_news']]
        for url in found:
            if url and url.startswith('http'):
                urls.setdefault(url.split('#')[0],set()).add(company)
    return urls


def check(url):
    headers={'User-Agent':news.USER_AGENT}
    try:
        response=requests.head(url,headers=headers,allow_redirects=True,timeout=(10,20))
        if response.status_code in (400,403,405,501) or response.status_code>=500:
            response=requests.get(url,headers=headers,allow_redirects=True,timeout=(10,30),stream=True)
            response.close()
        code=response.status_code
        state='ok' if code<400 else 'bloqueado' if code in (401,403,429) else 'roto'
        return url,{'state':state,'code':code}
    except requests.RequestException as exc:
        return url,{'state':'sin respuesta','code':None,'error':type(exc).__name__}


def run():
    urls=collect()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=dict(pool.map(check,urls))
    checked_at=service.now()
    for url,result in results.items():
        result.update({'checked_at':checked_at,'companies':sorted(urls[url])})
    totals={state:sum(r['state']==state for r in results.values()) for state in ('ok','bloqueado','roto','sin respuesta')}
    data={'checked_at':checked_at,'total':len(results),'totals':totals,'results':results}
    PATH.parent.mkdir(parents=True,exist_ok=True)
    PATH.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    return data


def load():
    for path in (PATH,service.ROOT/'demo_data'/'links.json'):
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    return {'results':{},'totals':{},'total':0}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    data=run()
    print(data['total'],'enlaces',data['totals'])
    for url,result in data['results'].items():
        if result['state']!='ok':
            print(f"  {result['state']} {result['code']} {url[:110]}")
