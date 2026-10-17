"""Acquire a fixed OpenFilm source archive and compare all files without installing it.

Explicit source-research network access only. This never runs upstream scripts,
providers, a browser, Docker or WSL. Use a fresh evidence/work directory.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import time
import urllib.request
import zipfile


def digest(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def contents(raw):
    result = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            if len(parts) < 2 or any(p in ('..', '.', '') for p in parts) or ':' in info.filename or '\\' in info.filename:
                raise ValueError('Unsafe archive entry: '+info.filename)
            relative = '/'.join(parts[1:])
            if relative in result or info.file_size > 32*1024*1024:
                raise ValueError('Duplicate or oversized archive entry: '+relative)
            result[relative] = archive.read(info)
    if sum(map(len, result.values())) > 128*1024*1024:
        raise ValueError('Oversized source tree')
    return result


def run(args):
    if args.archive.exists():
        raise ValueError('Use a fresh archive path')
    for directory in (args.output, args.work):
        directory.mkdir(parents=True, exist_ok=False)
    requests = []

    def fetch(url, name):
        for attempt in range(1, 4):
            begin = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={
                    'User-Agent':'agent-video-kit-fixed-source-audit', 'Accept':'application/vnd.github+json'})
                with urllib.request.urlopen(request, timeout=40) as response:
                    raw = response.read(32*1024*1024+1)
                    if len(raw) > 32*1024*1024:
                        raise ValueError('Response size limit')
                    requests.append({'url':url, 'attempt':attempt, 'status':response.status,
                                     'bytes':len(raw), 'sha256':digest(raw), 'seconds':time.monotonic()-begin})
                (args.output/name).write_bytes(raw)
                save(args.output/'requests.json', requests)
                return raw
            except Exception as exc:
                requests.append({'url':url, 'attempt':attempt, 'error':str(exc), 'seconds':time.monotonic()-begin})
                save(args.output/'requests.json', requests)
                if attempt == 3:
                    raise

    api = 'https://api.github.com/repos/openfilm/openfilm'
    metadata = json.loads(fetch(api, 'repository.json'))
    commit = json.loads(fetch(api+'/commits/'+metadata['default_branch'], 'commit.json'))
    head = commit['sha']
    raw = fetch(api+'/zipball/'+head, 'source.zip')
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    (args.output/'source.zip').rename(args.archive)
    old, new = contents(args.fixed.read_bytes()), contents(raw)
    old_hashes = {p:digest(b) for p,b in sorted(old.items())}
    new_hashes = {p:digest(b) for p,b in sorted(new.items())}
    added, removed = sorted(new.keys()-old.keys()), sorted(old.keys()-new.keys())
    changed = sorted(p for p in old.keys() & new.keys() if old[p] != new[p])
    changes = []
    for relative in changed:
        try:
            a, b = old[relative].decode('utf-8'), new[relative].decode('utf-8')
            patch = ''.join(difflib.unified_diff(a.splitlines(True), b.splitlines(True),
                                               fromfile='fixed/'+relative, tofile='head/'+relative))
            patch_path = args.output/f'change-{len(changes):02d}.patch'
            patch_path.write_text(patch, encoding='utf-8', newline='\n')
            changes.append({'path':relative, 'patch':patch_path.name, 'patch_lines':len(patch.splitlines())})
        except UnicodeError:
            changes.append({'path':relative, 'binary':True})
    source = args.work/'source'
    for relative, data in new.items():
        target = source.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    package = json.loads(new['packages/openfilm/package.json'])
    record = {
        'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'repository':'https://github.com/openfilm/openfilm',
        'head':head, 'commit_at_utc':commit['commit']['committer']['date'],
        'stars':metadata['stargazers_count'], 'forks':metadata['forks_count'], 'license':metadata['license']['spdx_id'],
        'version':package['version'], 'node_engine':package.get('engines'),
        'fixed_archive':str(args.fixed), 'fixed_archive_sha256':digest(args.fixed.read_bytes()),
        'source_archive':str(args.archive), 'source_archive_sha256':digest(raw), 'source_archive_bytes':len(raw),
        'old_file_count':len(old), 'new_file_count':len(new),
        'unchanged_file_count':sum(old_hashes[p] == new_hashes.get(p) for p in old_hashes),
        'added':added, 'removed':removed, 'changed':changes,
        'fixed_hashes':old_hashes, 'head_hashes':new_hashes,
        'unpacked_source':str(source), 'tests_run':False, 'runtime_updated':False,
        'browser_started':False, 'upstream_cli_started':False, 'dependencies_installed':False,
        'scope':'Full archive bytes compared; no product or upstream functionality acceptance implied.'}
    save(args.output/'verification.json', record)
    print(json.dumps({k:v for k,v in record.items() if k in (
        'checked_at_utc','head','stars','forks','version','old_file_count','new_file_count','unchanged_file_count')},
        ensure_ascii=False))
    print(json.dumps({'added':len(added),'removed':len(removed),'changed':len(changed)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('fixed','output','work','archive'):
        parser.add_argument('--'+key, type=Path, required=True)
    run(parser.parse_args())
