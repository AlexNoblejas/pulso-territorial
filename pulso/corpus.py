"""Corpus institucional: pasajes literales verificados contra el PDF original.

Ejecutar: python -m pulso.corpus  (comprueba hash, página y texto de cada pasaje).
"""
from functools import lru_cache
import hashlib
import json
import re
import sys

from pypdf import PdfReader

from . import service

DIRECTORY=service.ROOT/'corpus'
CONFIG=service.ROOT/'config'/'corpus.json'


def _squash(text):
    # pypdf splits words ("incident e") and emits private-use bullets; compare without spaces.
    text=re.sub(r'[-]','',text or '')
    return re.sub(r'\s+','',text).lower()


@lru_cache(maxsize=None)
def _page_text(filename,page):
    reader=PdfReader(str(DIRECTORY/filename))
    return _squash(reader.pages[page-1].extract_text())


def pdf_url(document,page=None):
    return f"corpus/{document['file']}"+(f'#page={page}' if page else '')


@lru_cache(maxsize=1)
def load():
    """Return only documents and passages whose hash and literal text check out."""
    if not CONFIG.exists():
        return {'documents':{},'passages':[],'signals':[],'problems':[]}
    config=json.loads(CONFIG.read_text(encoding='utf-8'))
    documents,problems={},[]
    for document in config['documents']:
        path=DIRECTORY/document['file']
        if not path.is_file():
            problems.append(f"{document['id']}: falta {document['file']}")
            continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if document.get('sha256') and digest!=document['sha256']:
            problems.append(f"{document['id']}: el hash no coincide")
            continue
        documents[document['id']]={**document,'sha256':digest,'pdf_url':pdf_url(document)}
    verified={}
    for kind in ['passages','signals']:
        verified[kind]=[]
        for item in config.get(kind,[]):
            document=documents.get(item['document_id'])
            if not document:
                continue
            if _squash(item['quote']) not in _page_text(document['file'],item['page']):
                problems.append(f"{item['document_id']} p.{item['page']}: el pasaje no aparece literal")
                continue
            verified[kind].append({**item,'pdf_url':pdf_url(document,item['page'])})
    return {'documents':documents,**verified,'problems':problems}


def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    corpus=load()
    for document in corpus['documents'].values():
        print(f"OK  {document['id']}  sha256={document['sha256'][:16]}…  {document['institution']}")
    for item in corpus['passages']+corpus['signals']:
        print(f"OK  {item['document_id']} p.{item['page']}  «{item['quote'][:70]}…»")
    for problem in corpus['problems']:
        print('ERROR',problem)
    return 1 if corpus['problems'] else 0


if __name__=='__main__':
    raise SystemExit(main())
