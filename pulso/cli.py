"""Comandos reproducibles y trabajador periódico de PulsoTerritorial."""
import argparse
import json
import time
from pathlib import Path

from filelock import FileLock, Timeout

from . import service


def update_bulletins():
    config = service.ROOT / 'config' / 'watchlist.json'
    profiles = json.loads(config.read_text(encoding='utf-8')) if config.exists() else []
    output = service.DATA / 'bulletins'
    output.mkdir(parents=True, exist_ok=True)
    generated = []
    for profile in profiles[:20]:
        query = profile['query']
        hits = service.search(query, limit=8)
        safe_id = ''.join(c for c in profile['id'] if c.isalnum() or c in '-_')[:60]
        if not safe_id:
            continue
        text = service.bulletin(hits, company=query)
        path = output / (safe_id + '.md')
        # Preserve a date-stamped history only when the evidence selection changes.
        signature = service.hashlib.sha256(json.dumps(hits, sort_keys=True).encode()).hexdigest()
        sigpath = output / (safe_id + '.sha256')
        if not sigpath.exists() or sigpath.read_text() != signature:
            path.write_text(text, encoding='utf-8')
            stamp = service.datetime.now(service.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            (output / f'{safe_id}_{stamp}.md').write_text(text, encoding='utf-8')
            sigpath.write_text(signature)
            generated.append(str(path))
    return generated


def cycle(limit):
    result = service.sync_sources(limit)
    result['bulletins'] = update_bulletins()
    from .news import update as update_news
    try:
        result['news'] = len(update_news()['items'])
    except Exception as exc:
        result['news_error'] = type(exc).__name__
    from .portfolio import COMPANIES,rebuild,visual_report,portfolio
    try:
        rebuild()
        report_dir=service.DATA/'reports'
        report_dir.mkdir(parents=True,exist_ok=True)
        result['visual_reports']=[]
        for company in COMPANIES:
            period=portfolio(company)['period']
            target=report_dir/f'{company}_{period}.html'
            target.write_text(visual_report(company,period),encoding='utf-8')
            result['visual_reports'].append(str(target))
    except ValueError as exc:
        result['portfolio_status']=str(exc)
    manifest = service.DATA / 'manifest.json'
    manifest.write_text(json.dumps(service.list_documents(), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description='PulsoTerritorial: ingesta y boletines con evidencia')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['sync', 'watch']:
        cmd = sub.add_parser(name)
        cmd.add_argument('--limit', type=int, default=2)
        if name == 'watch':
            cmd.add_argument('--interval', type=int, default=21600)
    sub.add_parser('status')
    sub.add_parser('bulletins')
    query = sub.add_parser('search')
    query.add_argument('query')
    query.add_argument('--limit', type=int, default=8)
    args = parser.parse_args()
    service.init_db()
    if args.command == 'status':
        print(json.dumps(service.stats(), ensure_ascii=False, indent=2))
    elif args.command == 'search':
        print(service.bulletin(service.search(args.query, limit=args.limit), args.query))
    elif args.command == 'bulletins':
        print(json.dumps(update_bulletins(), ensure_ascii=False))
    else:
        lock = FileLock(str(service.DATA / 'worker.lock'), timeout=0)
        try:
            with lock:
                while True:
                    try:
                        cycle(args.limit)
                    except Exception as exc:
                        print(json.dumps({'error': type(exc).__name__, 'time': service.now()}), flush=True)
                        if args.command == 'sync':
                            raise
                    if args.command != 'watch':
                        break
                    time.sleep(max(300, args.interval))
        except Timeout:
            parser.exit(2, 'Ya hay otra actualización de fuentes en ejecución.\n')


if __name__ == '__main__':
    main()
