"""Resume retained prefixes with short bounded requests, then verify pinned LFS."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(4 * 1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def main(args):
    target, evidence = args.target.resolve(), args.evidence.resolve()
    assert target.is_relative_to(ROOT / 'product/.runtime')
    assert evidence.is_relative_to(ROOT / 'docs/validation/evidence')
    evidence.mkdir(exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    prior = json.loads(args.prior.read_bytes())
    weight, repo, revision = prior['weight'], prior['repository'], prior['revision']
    total = weight['size']
    chunks = target / 'short-ranges'
    chunks.mkdir(exist_ok=args.resume)
    def save(name, data):
        (evidence / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
    pieces, jobs = [], []
    for part in prior['parts']:
        start, end = part['start'], part['end']
        prefix = target / 'download-parts' / (str(start) + '.part')
        n = prefix.stat().st_size if prefix.exists() else 0
        assert 0 <= n <= end - start + 1
        if n:
            pieces.append({'start': start, 'end': start + n - 1, 'path': str(prefix), 'sha256': sha(prefix), 'retained': True})
        for offset in range(start + n, end + 1, 4 * 1024 * 1024):
            row = {'start': offset, 'end': min(end, offset + 4 * 1024 * 1024 - 1),
                   'path': str(chunks / (str(offset) + '.part')), 'retained': False}
            pieces.append(row)
            jobs.append(row)
    pieces.sort(key=lambda p: p['start'])
    assert pieces[0]['start'] == 0 and pieces[-1]['end'] == total - 1
    assert all(a['end'] + 1 == b['start'] for a, b in zip(pieces, pieces[1:]))
    save('plan.json', {'repository': repo, 'revision': revision, 'expected': weight,
                       'pieces': pieces, 'workers': args.workers, 'transport_ref_is_not_trusted': True})
    started = time.monotonic()
    def download(row):
        output = Path(row['path'])
        row = dict(row)
        row['preexisting_bytes'] = output.stat().st_size if output.exists() else 0
        assert row['preexisting_bytes'] <= row['end'] - row['start'] + 1
        if row['preexisting_bytes']:
            row['preexisting_sha256'] = sha(output)
        attempts = []
        for attempt in range(4):
            received = output.stat().st_size if output.exists() else 0
            if received == row['end'] - row['start'] + 1:
                break
            a, b = row['start'] + received, row['end']
            base = ('https://modelscope.cn/models/' + repo + '/resolve/master' if attempt % 2 == 0
                    else 'https://hf-mirror.com/' + repo + '/resolve/' + revision)
            url = base + '/' + weight['rfilename'] + f'?download=true&avk_short={a}-{b}'
            at = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Range': f'bytes={a}-{b}'})
                with urllib.request.urlopen(request, timeout=15) as response:
                    assert response.status == 206 and response.headers.get('Content-Range') == f'bytes {a}-{b}/{total}'
                    with output.open('ab' if received else 'xb') as stream:
                        while data := response.read(64 * 1024):
                            assert stream.tell() + len(data) <= row['end'] - row['start'] + 1
                            stream.write(data)
                            if time.monotonic() - at > 90:
                                raise TimeoutError('Per-request 90 second development deadline')
                assert output.stat().st_size == row['end'] - row['start'] + 1
                break
            except Exception as exc:
                attempts.append({'url': url, 'offset': received, 'error': repr(exc), 'seconds': time.monotonic() - at})
                save(str(row['start']) + '.failure.json', {'attempts': attempts})
        else:
            raise RuntimeError('Retained failed short range ' + str(row['start']))
        result = {**row, 'bytes': output.stat().st_size, 'sha256': sha(output), 'attempts': attempts}
        save(str(row['start']) + '.json', result)
        return result
    try:
        assert 1 <= args.workers <= 32
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = [pool.submit(download, row) for row in jobs]
            received = []
            for future in as_completed(pending):
                row = future.result()
                received.append(row)
                print(json.dumps({'ranges_completed': len(received), 'ranges_total': len(jobs),
                                  'received_new_bytes': sum(x['bytes'] - x['preexisting_bytes'] for x in received)}), flush=True)
        assembled = target / (weight['rfilename'] + '.assembled')
        with assembled.open('xb') as stream:
            for piece in pieces:
                path = Path(piece['path'])
                if piece['retained']:
                    assert sha(path) == piece['sha256']
                with path.open('rb') as source:
                    while data := source.read(4 * 1024 * 1024):
                        stream.write(data)
        assert assembled.stat().st_size == total and sha(assembled) == weight['lfs']['sha256']
        assembled.rename(target / weight['rfilename'])
        configs = json.loads((args.prior.parent / 'configs.json').read_bytes())['files']
        save('verification.json', {'status': 'downloaded_and_hashed', 'repository': repo, 'revision': revision,
            'weight_bytes': total, 'weight_sha256': 'sha256:' + weight['lfs']['sha256'], 'configs': configs,
            'source_proof': str(args.prior.parent / 'source.json'), 'ranges': received,
            'retained_prefixes': [p for p in pieces if p['retained']], 'seconds': time.monotonic() - started,
            'development_network': True, 'runtime_downloads': False, 'code_or_weights_executed': False,
            'generator_sha256': 'sha256:' + sha(Path(__file__))})
    except BaseException as exc:
        save('failure.json', {'status': 'failed', 'error': repr(exc), 'partials_preserved': True})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['target', 'evidence', 'prior']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--resume', action='store_true')
    main(parser.parse_args())
