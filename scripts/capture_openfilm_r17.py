"""Capture one pinned OpenFilm revision for a native, read-only reuse audit."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'af5756a88d362bdcd71dc870a0e02590420e6944'
HEAD = 'cf6cd6fa9b3d4ee50dd963853ee6ca4f8354ecf4'
OUT = ROOT / 'docs/validation/evidence/openfilm-reuse-20261022-r17/capture-r1'
SOURCE = ROOT / 'product/.runtime/openfilm-r17-source'
ARCHIVE = ROOT / 'sources/upstream/openfilm-025-20261022-r17/repo.zip'
PRIOR = ROOT / 'sources/upstream/openfilm-025-20261022-r16/repo.zip'
CANDIDATES = (
    'packages/openfilm/src/browser-pool.mjs',
    'packages/openfilm/src/seekable.mjs',
    'packages/openfilm/src/host.mjs',
    'packages/openfilm/src/render.mjs',
    'packages/openfilm/studio/server/render-worker.mjs',
    'packages/openfilm/studio/server/exports.mjs',
    'packages/openfilm/src/film-doc.mjs',
    'packages/openfilm/src/look.mjs',
    'packages/openfilm/studio/server/subtitle-segments.mjs',
    'packages/openfilm/studio/ui/src/lib/component-props.ts',
    'packages/openfilm/studio/ui/src/lib/template-controls.ts',
    'packages/openfilm/studio/server/nle.mjs',
    'packages/openfilm/studio/server/fcpxml.mjs',
    'packages/openfilm/src/encoders.mjs',
    'packages/openfilm/src/shared.mjs',
    'apps/desktop/src/agents.mjs',
    'apps/desktop/src/as-node.mjs',
)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def freeze():
    spec = importlib.util.spec_from_file_location('main_freeze_r17', ROOT / 'scripts/run_frozen_regression.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.frozen()


def archive_files(path, revision):
    files = {}
    with zipfile.ZipFile(path) as z:
        assert len(z.infolist()) < 6000
        assert sum(x.file_size for x in z.infolist()) < (96 << 20)
        for entry in z.infolist():
            if entry.is_dir():
                continue
            p = PurePosixPath(entry.filename)
            assert not p.is_absolute() and '..' not in p.parts
            assert p.parts[0] == 'openfilm-' + revision
            assert not any('\\' in part or ':' in part for part in p.parts)
            assert (entry.external_attr >> 16) & 0o170000 != 0o120000
            name = PurePosixPath(*p.parts[1:]).as_posix()
            assert name and name not in files
            files[name] = z.read(entry)
    return files


def main():
    assert not SOURCE.exists() and not ARCHIVE.exists()
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'executed-capture.py.txt').write_bytes(Path(__file__).read_bytes())
    record = dict(status='running', started_at_utc=now(), fixed_head=HEAD, compare_base=BASE,
                  requests=[], frozen_before=freeze(), upstream_cli_executed=False,
                  browser_tabs_opened=0, virtualization=False, product_code_adopted=False,
                  new_product_tests=0, new_media=0)
    save(OUT / 'verification.json', record)
    try:
        urls = {
            'repository': 'https://api.github.com/repos/openfilm/openfilm',
            'head': 'https://api.github.com/repos/openfilm/openfilm/commits/main',
            'release': 'https://api.github.com/repos/openfilm/openfilm/releases/latest',
            'compare': f'https://api.github.com/repos/openfilm/openfilm/compare/{BASE}...{HEAD}',
            'archive': f'https://codeload.github.com/openfilm/openfilm/zip/{HEAD}',
        }
        replies = {}
        for key, url in urls.items():
            started = now()
            request = urllib.request.Request(url, headers={
                'User-Agent': 'agent-video-kit-pinned-reuse-audit',
                'Accept': 'application/vnd.github+json'})
            with urllib.request.urlopen(request, timeout=60) as response:
                limit = (24 if key == 'archive' else 8) << 20
                raw = response.read(limit + 1)
                assert len(raw) <= limit, ('response-size-limit', key)
                meta = dict(key=key, url=url, status=response.status,
                            requested_at_utc=started, received_at_utc=now(),
                            bytes=len(raw), sha256=sha(raw), etag=response.headers.get('ETag'),
                            server_date=response.headers.get('Date'))
            record['requests'].append(meta)
            if key == 'archive':
                ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
                with ARCHIVE.open('xb') as stream:
                    stream.write(raw)
            else:
                (OUT / (key + '.json')).write_bytes(raw)
                replies[key] = json.loads(raw)
            save(OUT / 'verification.json', record)
        assert replies['head']['sha'] == HEAD, 'New upstream revision: preserve this capture and review explicitly'
        compare = replies['compare']
        assert compare['status'] == 'ahead' and compare['total_commits'] == 1
        assert compare['commits'][-1]['sha'] == HEAD and len(compare['files']) < 300
        old_receipt = json.loads((ROOT / 'docs/validation/evidence/openfilm-reuse-20261022-r16/capture-r2/verification.json').read_bytes())
        assert sha(PRIOR.read_bytes()) == old_receipt['archive_sha256']
        files = archive_files(ARCHIVE, HEAD)
        old = archive_files(PRIOR, BASE)
        changed = [name for name in sorted(set(files) | set(old)) if files.get(name) != old.get(name)]
        assert set(changed) == {x['filename'] for x in compare['files']}, 'Compare and pinned ZIP disagree'
        SOURCE.mkdir(parents=True, exist_ok=False)
        for name, data in files.items():
            target = SOURCE / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
        save(OUT / 'source-tree.json', {n: {'sha256': sha(d), 'bytes': len(d)} for n, d in sorted(files.items())})
        save(OUT / 'changes-from-r16.json', changed)
        for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'TRADEMARK.md'):
            (OUT / (name + '.txt')).write_bytes(files[name])
        (OUT / 'changed-files-and-patches.txt').write_text('\n\n'.join(
            row['filename'] + '\n' + row.get('patch', '[Read pinned source]')
            for row in compare['files']), encoding='utf8')
        record.update(status='passed-pinned-source-capture', finished_at_utc=now(),
                      stars=replies['repository']['stargazers_count'], forks=replies['repository']['forks_count'],
                      release=replies['release']['tag_name'], release_published_at=replies['release']['published_at'],
                      commits_since_r16=compare['total_commits'], files_since_r16=len(changed),
                      source_files=len(files), archive_sha256=sha(ARCHIVE.read_bytes()),
                      archive_bytes=ARCHIVE.stat().st_size, license_unchanged_from_r16=files['LICENSE'] == old['LICENSE'],
                      candidates={n: {'changed_since_r16': files.get(n) != old.get(n),
                                      'lines': len(files[n].splitlines()), 'sha256': sha(files[n])}
                                  for n in CANDIDATES}, frozen_after=freeze())
        assert record['frozen_before'] == record['frozen_after'], 'Concurrent product publication: retain evidence and recheck'
        save(OUT / 'verification.json', record)
        print(json.dumps({k: record[k] for k in (
            'status', 'fixed_head', 'stars', 'forks', 'release', 'source_files', 'files_since_r16')}, ensure_ascii=False))
    except BaseException as exc:
        record.update(status='failed', finished_at_utc=now(), error=repr(exc), frozen_after=freeze())
        save(OUT / 'verification.json', record)
        raise


if __name__ == '__main__':
    main()
