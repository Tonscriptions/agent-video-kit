"""Validate immutable local release assets; optionally publish using GitHub Actions.

Authentication is supplied only through GITHUB_TOKEN. Tokens are never stored,
printed, embedded in URLs, or forwarded to hosts outside GitHub's API/upload hosts.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--artifacts', type=Path, required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--commit', default=None)
    ap.add_argument('--publish', action='store_true')
    a = ap.parse_args()
    if a.tag != 'v0.1.0-alpha.1':
        raise ValueError('This reviewed first-release publisher accepts its exact tag only')
    rows = []
    for line in (a.artifacts / 'SHA256SUMS.txt').read_text('ascii').splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', digest) or Path(name).name != name:
            raise ValueError('Invalid inventory entry')
        data = (a.artifacts / name).read_bytes()
        if sha(data) != digest:
            raise ValueError('Artifact changed: ' + name)
        rows.append({'name': name, 'sha256': digest, 'bytes': len(data)})
    expected = {'version.json', 'RELEASE-NOTES.md', *(f'agent-video-kit-{a.tag}-{suffix}.zip' for suffix in ('cp313-win_amd64', 'examples', 'skills'))}
    if {r['name'] for r in rows} != expected or {p.name for p in a.artifacts.iterdir()} != expected | {'SHA256SUMS.txt'}:
        raise ValueError('Unexpected or incomplete release asset set')
    version = json.loads((a.artifacts / 'version.json').read_bytes())
    if version['release'] != a.tag or version['target'] != 'cp313-win_amd64' or len(version['wheels']) != 8:
        raise ValueError('Wrong version or wheel profile')
    with zipfile.ZipFile(a.artifacts / f'agent-video-kit-{a.tag}-cp313-win_amd64.zip') as z:
        manifest_bytes = z.read('bundle/manifest.json')
        if 'sha256:' + sha(manifest_bytes) != version['manifest_sha256']:
            raise ValueError('Embedded manifest differs from reviewed version')
        manifest = json.loads(manifest_bytes)
        for row in manifest['files']:
            data = z.read('bundle/' + row['path'])
            if len(data) != row['bytes'] or 'sha256:' + sha(data) != row['sha256']:
                raise ValueError('Embedded bundle input changed: ' + row['path'])
    result = {'status': 'validated', 'tag': a.tag, 'assets': rows}
    if not a.publish:
        print(json.dumps(result))
        return
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', 'Tonscriptions/agent-video-kit')
    if not token or repo != 'Tonscriptions/agent-video-kit':
        raise ValueError('Correct repository-scoped GITHUB_TOKEN required')
    if not a.commit or not re.fullmatch('[0-9a-f]{40}', a.commit):
        raise ValueError('Exact checked-out tag commit required')
    api = 'https://api.github.com/repos/' + repo
    def request(method, url, data=None, binary=False):
        if urllib.parse.urlparse(url).hostname not in {'api.github.com', 'uploads.github.com'}:
            raise ValueError('Refusing credential forwarding')
        headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                   'User-Agent': 'agent-video-kit-first-release', 'X-GitHub-Api-Version': '2022-11-28'}
        if data is not None:
            headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
            if not binary:
                data = json.dumps(data).encode('utf8')
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    releases = request('GET', api + '/releases?per_page=100')
    release = next((r for r in releases if r['tag_name'] == a.tag), None)
    if release is None:
        release = request('POST', api + '/releases', {'tag_name': a.tag, 'target_commitish': a.commit,
            'name': 'Agent Video Kit ' + a.tag + ' — Local Agent CLI preview', 'draft': True,
            'prerelease': True, 'make_latest': 'false', 'body': (a.artifacts / 'RELEASE-NOTES.md').read_text('utf8')})
    existing = {r['name']: r for r in release['assets']}
    all_rows = rows + [{'name': 'SHA256SUMS.txt', 'sha256': sha((a.artifacts / 'SHA256SUMS.txt').read_bytes()),
                        'bytes': (a.artifacts / 'SHA256SUMS.txt').stat().st_size}]
    for row in all_rows:
        if row['name'] in existing:
            asset = existing[row['name']]
            if asset.get('digest') != 'sha256:' + row['sha256'] or asset['size'] != row['bytes']:
                raise ValueError('Existing release asset differs; preserving it: ' + row['name'])
            continue
        if not release['draft']:
            raise ValueError('Published release is incomplete; refusing to mutate it')
        url = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': row['name']})
        asset = request('POST', url, (a.artifacts / row['name']).read_bytes(), binary=True)
        if asset['size'] != row['bytes'] or asset.get('digest') != 'sha256:' + row['sha256']:
            raise ValueError('Uploaded asset verification failed: ' + row['name'])
    release = request('GET', api + '/releases/' + str(release['id']))
    if {r['name'] for r in release['assets']} != {r['name'] for r in all_rows}:
        raise ValueError('Final release asset set differs')
    if release['draft']:
        release = request('PATCH', api + '/releases/' + str(release['id']), {'draft': False, 'prerelease': True, 'make_latest': 'false'})
    result.update(status='published', html_url=release['html_url'], prerelease=release['prerelease'],
                  published_at=release['published_at'], source_commit=a.commit)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as e:
        try:
            message = json.load(e).get('message', 'GitHub API rejected the request')
        except Exception:
            message = 'GitHub API rejected the request'
        print(json.dumps({'status': 'failed-preserved', 'http_status': e.code, 'message': message}))
        sys.exit(1)
