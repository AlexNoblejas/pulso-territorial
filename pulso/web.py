"""Servidor local del producto B2B. Ejecutar: python -m pulso.web."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit,unquote
from pathlib import Path
import argparse
import json
import mimetypes
import threading

from . import corpus,news,portfolio,service

WEB=service.ROOT/'web'
BUSY=threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):
        # Never log request bodies, user questions or credentials.
        pass

    def send(self,data,content_type='application/json; charset=utf-8',status=200,extra=None):
        if isinstance(data,(dict,list)):
            data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        elif isinstance(data,str):
            data=data.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Cache-Control','no-store' if content_type.startswith('application/json') else 'no-cache')
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.local_host():
            return self.send({'error':'Host no permitido.'},status=403)
        try:
            path=urlsplit(self.path)
            args=parse_qs(path.query)
            company=args.get('company',['mineria'])[0]
            period=args.get('period',[None])[0]
            if path.path=='/api/portfolio':
                return self.send(portfolio.portfolio(company,period))
            if path.path=='/api/geography':
                return self.send(portfolio.geography(company))
            if path.path=='/api/report':
                return self.send(portfolio.visual_report(company,period),'text/html; charset=utf-8')
            if path.path=='/api/readings':
                readings=service.ROOT/'demo_data'/'ai_readings.json'
                return self.send(json.loads(readings.read_text(encoding='utf-8')) if readings.exists() else {'readings':{}})
            if path.path=='/api/status':
                return self.send({'library':service.stats(),'providers':service.provider_status(),'mode':'demostración local','author':'Alexander Noblejas'})
            if path.path=='/api/evidence':
                # Only curated public PDFs from the manifest, never an arbitrary filesystem path.
                item=portfolio._read('local_evidence.json',{}).get(args.get('id',[''])[0])
                if not item:
                    return self.send({'error':'Documento no registrado.'},status=404)
                source=Path(item['path'])
                if source.suffix.lower()!='.pdf':
                    return self.send({'error':'Formato no permitido.'},status=400)
                return self.send(source.read_bytes(),'application/pdf')
            relative=unquote(path.path).lstrip('/') or 'index.html'
            if relative.startswith('corpus/'):
                # Only PDFs registered and verified in config/corpus.json, never arbitrary files.
                files={d['file'] for d in corpus.load()['documents'].values()}
                name=relative.split('/',1)[1]
                if name not in files:
                    return self.send({'error':'Documento no registrado.'},status=404)
                return self.send((corpus.DIRECTORY/name).read_bytes(),'application/pdf')
            target=(WEB/relative).resolve()
            if not target.is_relative_to(WEB.resolve()) or not target.is_file():
                return self.send({'error':'Ruta no encontrada.'},status=404)
            return self.send(target.read_bytes(),mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        except ValueError as exc:
            self.send({'error':str(exc)},status=400)
        except Exception as exc:
            self.send({'error':f'No se pudo completar la consulta ({type(exc).__name__}).'},status=500)

    def local_host(self):
        try:
            host=urlsplit('http://'+self.headers.get('Host','')).hostname
            return host in {'127.0.0.1','localhost','::1'}
        except ValueError:
            return False

    def do_POST(self):
        if not self.local_host():
            return self.send({'error':'Host no permitido.'},status=403)
        origin=self.headers.get('Origin','')
        if origin and origin!=f'http://{self.headers.get("Host","")}':
            return self.send({'error':'Origen no permitido.'},status=403)
        if not self.headers.get('Content-Type','').startswith('application/json'):
            return self.send({'error':'Se requiere JSON.'},status=415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=16000:
                return self.send({'error':'Solicitud demasiado grande.'},status=413)
            body=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body,dict):
                return self.send({'error':'El JSON debe ser un objeto.'},status=400)
            if urlsplit(self.path).path=='/api/refresh':
                if not BUSY.acquire(blocking=False):
                    return self.send({'error':'Hay otra revisión de fuentes en curso.'},status=409)
                try:
                    result=service.sync_sources(limit=2)
                    result['news']=len(news.update(pause=0.5)['items'])
                    portfolio.rebuild()
                    return self.send({'result':result,'message':f"Documentos revisados y {result['news']} notas de prensa en la ventana de 120 días. Las fuentes complementarias conservan revisión editorial."})
                finally:
                    BUSY.release()
            if urlsplit(self.path).path=='/api/interpret':
                p=portfolio.portfolio(body.get('company','mineria'),body.get('period'))
                case=next((c for c in p['cases'] if c['id']==body.get('case_id')),None)
                if not case:
                    return self.send({'error':'Selecciona un conflicto de esta cartera.'},status=400)
                provider=body.get('provider','groq')
                if not service.provider_status().get(provider):
                    return self.send({'error':'Este proveedor no está configurado. La lectura documental y las fuentes permanecen disponibles.'},status=409)
                official=[event for event in case['events'] if event['kind']=='reporte oficial']
                original=case.get('original_description',case['summary'])+'\n\n'+'\n'.join(event['summary'] for event in official)
                hits=[{'document_id':case['source_ids'][0],'page':1,'method':'ficha_html_oficial','text':original}]
                # Only the verified passage: the rest of a PDF page usually describes neighbouring cases.
                hits+=[{'document_id':event['source_id'],'page':event['page'],'method':'pdf_pypdf','text':event['summary']}
                       for event in case['events'] if event.get('literal')]
                result=service.extract(hits,provider)
                result['scope']='Citas comprobadas contra el texto de la ficha Defensoría y de las páginas PDF del corpus (PCM, MINAM, MINEM). Las notas de prensa y comunicaciones no se envían al modelo.'
                return self.send(result)
            return self.send({'error':'Acción no encontrada.'},status=404)
        except ValueError as exc:
            self.send({'error':str(exc)},status=400)
        except Exception as exc:
            self.send({'error':f'No se pudo completar la acción ({type(exc).__name__}).'},status=500)


def main():
    parser=argparse.ArgumentParser(description='PulsoTerritorial · plataforma de monitoreo empresarial')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    service.init_db()
    portfolio.rebuild()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'PulsoTerritorial: http://127.0.0.1:{args.port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
