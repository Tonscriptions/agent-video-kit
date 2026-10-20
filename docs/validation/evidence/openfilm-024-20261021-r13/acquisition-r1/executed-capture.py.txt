"""Pin OpenFilm source for R13 research; never installs or executes upstream."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = '284f8bd3d6850ceaa773043e2ecb90e13640f547'
HEAD = '53156ac5818d8bad3f2c356043b376b3eebd95ba'
EVIDENCE = ROOT / 'docs/validation/evidence/openfilm-024-20261021-r13/acquisition-r1'
SOURCE = ROOT / 'sources/upstream/openfilm-024-20261021-r13'


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    assert not EVIDENCE.exists() and not SOURCE.exists(), 'Never overwrite acquisition evidence'
    before = frozen()
    EVIDENCE.mkdir(parents=True)
    SOURCE.mkdir(parents=True)
    (EVIDENCE / 'executed-capture.py.txt').write_bytes(Path(__file__).read_bytes())
    record = {'status': 'running', 'base_commit': BASE, 'head_commit': HEAD,
              'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'script_sha256': sha(Path(__file__).read_bytes()), 'frozen_before': before,
              'requests': [], 'research_acquisition_only': True,
              'upstream_install_or_execution': False, 'browser_tabs_opened': 0,
              'virtualization': False}

    def fetch(url, target, limit):
        request = urllib.request.Request(url, headers={
            'User-Agent': 'agent-video-kit-source-review', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(limit + 1)
            assert len(data) <= limit, 'Response exceeds research acquisition budget'
            assert response.status == 200
            target.write_bytes(data)
            record['requests'].append({
                'url': url, 'resolved_url': response.url, 'status': response.status,
                'http_date': response.headers.get('Date'), 'etag': response.headers.get('ETag'),
                'last_modified': response.headers.get('Last-Modified'),
                'received_at_utc': datetime.now(timezone.utc).isoformat(),
                'path': target.relative_to(ROOT).as_posix(), 'bytes': len(data), 'sha256': sha(data)})
        return data

    try:
        repo = json.loads(fetch('https://api.github.com/repos/openfilm/openfilm', EVIDENCE / 'repository.json', 1 << 20))
        head = json.loads(fetch('https://api.github.com/repos/openfilm/openfilm/commits/' + HEAD, EVIDENCE / 'head.json', 2 << 20))
        comparison = json.loads(fetch('https://api.github.com/repos/openfilm/openfilm/compare/' + BASE + '...' + HEAD, EVIDENCE / 'compare.json', 4 << 20))
        release = json.loads(fetch('https://api.github.com/repos/openfilm/openfilm/releases/latest', EVIDENCE / 'release.json', 2 << 20))
        data = fetch('https://codeload.github.com/openfilm/openfilm/zip/' + HEAD, SOURCE / 'repo.zip', 32 << 20)
        assert head['sha'] == HEAD
        assert comparison['base_commit']['sha'] == BASE and comparison['status'] == 'ahead'
        assert comparison['commits'][-1]['sha'] == HEAD
        with zipfile.ZipFile(SOURCE / 'repo.zip') as archive:
            version = json.loads(archive.read('openfilm-' + HEAD + '/packages/openfilm/package.json'))['version']
            assert version == '0.2.4'
        record.update(status='passed_acquisition_only', version=version,
                      stars=repo['stargazers_count'], forks=repo['forks_count'],
                      repository_pushed_at=repo['pushed_at'], commit_date=head['commit']['committer']['date'],
                      ahead_by=comparison['ahead_by'], latest_release_tag=release['tag_name'],
                      latest_release_published_at=release['published_at'], zip_sha256=sha(data), zip_bytes=len(data))
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        after = frozen()
        record.update(frozen_after=after, frozen_equal=before == after,
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        write(EVIDENCE / 'verification.json', record)
    assert record['frozen_equal']
    print(json.dumps({key: record[key] for key in ('status', 'head_commit', 'version', 'stars', 'forks', 'ahead_by', 'latest_release_tag', 'zip_sha256', 'zip_bytes', 'frozen_equal')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
