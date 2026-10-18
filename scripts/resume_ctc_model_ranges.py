"""Development acquisition only: resume pinned model bytes with bounded ranges."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(4 * 1024 * 1024):
            value.update(data)
    return value.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(args):
    target, evidence = args.target.resolve(), args.evidence.resolve()
    assert target.is_relative_to(ROOT/'product/.runtime')
    assert evidence.is_relative_to(ROOT/'docs/validation/evidence')
    evidence.mkdir(parents=True, exist_ok=False)
    metadata = json.loads((ROOT/'docs/validation/evidence/ctc-model-mirror-source-20261018/inspection.json').read_text(encoding='utf-8'))
    plans, jobs = [], []
    for language, model in metadata['models'].items():
        filename = 'model.safetensors' if language == 'en' else 'pytorch_model.bin'
        record = next(f for f in model['files'] if f['rfilename'] == filename)
        output = target/language/filename
        if output.exists():
            assert output.stat().st_size == record['size'] and sha(output) == record['lfs']['sha256']
            plans.append({'language': language, 'status': 'already_verified', 'output': str(output)})
            continue
        partial = output.with_name(output.name+'.part')
        prefix = partial.with_name(partial.name+'.prefix')
        partial.rename(prefix)
        offset = prefix.stat().st_size
        assert 0 < offset < record['size']
        row = {'language': language, 'filename': filename, 'repository': model['repository'],
               'revision': model['revision'], 'expected_bytes': record['size'],
               'expected_sha256': record['lfs']['sha256'], 'prefix_bytes': offset,
               'prefix_sha256': sha(prefix), 'ranges': [], 'output': str(output)}
        plans.append(row)
        for start in range(offset, record['size'], 16*1024*1024):
            end = min(record['size'], start+16*1024*1024)-1
            piece = output.with_name(filename+f'.range-{start}-{end}')
            item = {'language': language, 'start': start, 'end': end, 'path': str(piece)}
            row['ranges'].append(item)
            jobs.append((item, model, filename))
    save(evidence/'plan.json', {'workers': 8, 'models': plans, 'development_network': True, 'runtime_downloads': False})
    def download(job):
        item, model, filename = job
        path, start, end = Path(item['path']), item['start'], item['end']
        url = f"https://hf-mirror.com/{model['repository']}/resolve/{model['revision']}/{filename}"
        total = next(f['size'] for f in model['files'] if f['rfilename'] == filename)
        attempts = []
        for attempt in range(3):
            offset = path.stat().st_size if path.exists() else 0
            attempts.append({'offset': offset})
            try:
                request = urllib.request.Request(url, headers={'Range': f'bytes={start+offset}-{end}'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    assert response.status == 206
                    assert response.headers.get('Content-Range') == f"bytes {start+offset}-{end}/{total}"
                    with path.open('ab' if path.exists() else 'xb') as stream:
                        while data := response.read(1024*1024):
                            if stream.tell() + len(data) > end-start+1:
                                raise ValueError('Range overflow')
                            stream.write(data)
                assert path.stat().st_size == end-start+1
                row = {**item, 'bytes': path.stat().st_size, 'sha256': sha(path), 'attempts': attempts, 'status': 'received'}
                save(evidence/f"{item['language']}-{start}.json", row)
                print(json.dumps({k: row[k] for k in ('language', 'start', 'bytes', 'status')}), flush=True)
                return row
            except Exception as exc:
                attempts[-1]['error'] = repr(exc)
                save(evidence/f"{item['language']}-{start}.failure.json", {'attempts': attempts})
                if attempt == 2:
                    raise
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(download, job) for job in jobs]
            received = [future.result() for future in as_completed(futures)]
        for plan in plans:
            if plan.get('status') == 'already_verified':
                continue
            output = Path(plan['output'])
            assembled = output.with_name(output.name+'.assembled')
            prefix = output.with_name(output.name+'.part.prefix')
            assert sha(prefix) == plan['prefix_sha256']
            with assembled.open('xb') as stream:
                for part in [prefix, *(Path(item['path']) for item in plan['ranges'])]:
                    with part.open('rb') as source:
                        while data := source.read(4*1024*1024):
                            stream.write(data)
            digest = sha(assembled)
            assert assembled.stat().st_size == plan['expected_bytes'] and digest == plan['expected_sha256']
            assembled.rename(output)
            plan.update(status='verified', sha256=digest)
        save(evidence/'verification.json', {'status': 'verified', 'models': plans, 'ranges': received,
            'weights_executed': False, 'generator_sha256': sha(Path(__file__))})
    except Exception as exc:
        save(evidence/'failure.json', {'status': 'failed', 'error': repr(exc), 'partial_bytes_preserved': True})
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    main(parser.parse_args())
