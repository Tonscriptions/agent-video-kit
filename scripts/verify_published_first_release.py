"""Read public GitHub release state and compare all assets to local digests.

No credentials required. Only downloads this repository's own release assets;
does not fetch source media or create browser tabs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'
ARTIFACTS = ROOT / 'docs/releases' / TAG / 'artifacts'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    base = 'https://api.github.com/repos/Tonscriptions/agent-video-kit'
    def get(url):
        req = urllib.request.Request(url, headers={'User-Agent': 'agent-video-kit-release-verifier', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    release = json.loads(get(base + '/releases/tags/' + TAG))
    if release['draft'] or not release['prerelease'] or release['tag_name'] != TAG:
        raise ValueError('Release stage differs')
    local = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in ARTIFACTS.iterdir() if p.is_file()}
    if set(local) != {p['name'] for p in release['assets']}:
        raise ValueError('Remote asset names differ')
    verified = []
    for asset in release['assets']:
        row = local[asset['name']]
        if asset['size'] != row['bytes'] or asset.get('digest') != 'sha256:' + row['sha256']:
            raise ValueError('Remote asset digest differs: ' + asset['name'])
        # Download only the project's generated release ZIPs/metadata, hash in memory.
        data = get(asset['browser_download_url'])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Downloaded asset differs: ' + asset['name'])
        verified.append({'name': asset['name'], 'bytes': len(data), 'sha256': 'sha256:' + row['sha256'],
                         'download_url': asset['browser_download_url'], 'download_verified': True})
    runs = json.loads(get(base + '/actions/runs?per_page=10'))['workflow_runs']
    run = next(r for r in runs if r['name'] == 'Publish first verified Agent Video Kit release' and r['head_sha'] == '56e59051301b6e0535fee5f0ada424d255776fa4')
    if run['conclusion'] != 'success':
        raise ValueError('Release workflow has not completed successfully')
    tag = json.loads(get(base + '/git/ref/tags/' + TAG))
    if tag['object']['type'] == 'tag':
        target = json.loads(get(tag['object']['url']))['object']['sha']
    else:
        target = tag['object']['sha']
    if target != run['head_sha']:
        raise ValueError('Tag commit and workflow differ')
    result = {'status': 'published-and-download-verified', 'release': TAG,
              'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'html_url': release['html_url'], 'published_at': release['published_at'],
              'draft': release['draft'], 'prerelease': release['prerelease'],
              'release_commit': target, 'workflow_url': run['html_url'],
              'workflow_conclusion': run['conclusion'], 'assets': verified,
              'full_capcut_parity': False, 'product_runtime_network': False,
              'publication_verification_network': True}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
