"""Refresh the public upstream revision and bind it to existing local evidence.

Research-only network access: two public GitHub GETs. No package install,
provider request, browser, GUI, render, model or product regression is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone
import urllib.parse
import urllib.request
import zipfile


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def run(output):
    root = Path(__file__).resolve().parents[1]
    output = output.resolve()
    assert output.is_relative_to(root / 'docs/validation/evidence')
    output.mkdir(parents=True, exist_ok=False)
    evidence = root / 'docs/validation/evidence'
    requests, replies = [], {}
    for name, url in {
        'repository': 'https://api.github.com/repos/openfilm/openfilm',
        'head': 'https://api.github.com/repos/openfilm/openfilm/commits/main',
    }.items():
        started = datetime.now(timezone.utc).isoformat()
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Agent-Video-Kit-source-review',
            'Accept': 'application/vnd.github+json', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            status = response.status
        (output / (name + '.json')).write_bytes(raw)
        replies[name] = json.loads(raw)
        requests.append({'url': url, 'method': 'GET', 'started_at_utc': started,
                         'finished_at_utc': datetime.now(timezone.utc).isoformat(),
                         'http_status': status, 'file': name + '.json',
                         'bytes': len(raw), 'sha256': digest(raw)})

    refresh_path = evidence / 'openfilm-refresh-20261018/verification.json'
    refresh = json.loads(refresh_path.read_text(encoding='utf-8'))
    increment_path = evidence / 'openfilm-increment-verified-20261018/verification.json'
    increment = json.loads(increment_path.read_text(encoding='utf-8'))
    expected = 'eefd6a8d379289102141359a4718dbab12170526'
    actual = replies['head']['sha']
    if actual != expected:
        (output / 'verification.json').write_text(json.dumps({
            'status': 'new-upstream-code-needs-review', 'expected': expected,
            'actual': actual, 'requests': requests}, indent=2) + '\n', encoding='utf-8')
        raise RuntimeError('Upstream changed; saved responses require a fresh source review')

    archive_path = root / 'sources/upstream/openfilm-0.2.0/repo.zip'
    assert digest(archive_path.read_bytes()) == refresh['source_archive_sha256']
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        entries = [n for n in archive.namelist() if not n.endswith('/')]
        prefix = entries[0].split('/')[0] + '/'
        files = {n[len(prefix):]: archive.read(n) for n in entries}
    hashes = {name: digest(raw) for name, raw in files.items()}
    assert hashes == refresh['head_hashes'] == increment['source_before'] == increment['source_after']
    assert len(hashes) == 702
    local = root / 'product/.runtime/openfilm-refresh-20261018/source'
    assert {p.relative_to(local).as_posix(): digest(p.read_bytes())
            for p in local.rglob('*') if p.is_file()} == hashes
    subtitle = 'packages/openfilm/studio/server/subtitle-segments.mjs'
    assert files[subtitle] == (root / 'product/src/ai_ad_editor/openfilm_subtitle_segments.mjs').read_bytes()
    assert files['LICENSE'] == (root / 'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()

    product_record = json.loads((evidence / 'range-edits-20261018.json').read_text(encoding='utf-8'))
    full = product_record['verification']['full']
    frozen = full['frozen_after']
    assert len(frozen) == 130 and full['methods'] == 897 and full['skipped'] == 0
    for name, expected_hash in frozen.items():
        assert digest((root / name).read_bytes()) == expected_hash, name
    current_py = {p.relative_to(root).as_posix() for base in ('product/src', 'product/tests')
                  for p in (root / base).rglob('*.py')}
    assert current_py == {name for name in frozen if name.endswith('.py')}
    upstream = next(row for row in increment['runs'] if row['id'] == 'N03-extracted-data')
    assert upstream['passed'] == upstream['test_count'] == 20 and upstream['skipped'] == 0

    # Make the evidence target exist before checking the documentation links.
    (output / 'verification.json').write_text('{}\n', encoding='utf-8')
    documents = [root / 'README.md', root / 'AGENTS.md', *sorted((root / 'docs').rglob('*.md'))]
    checked = 0
    broken = []
    for document in documents:
        text = document.read_text(encoding='utf-8-sig')
        text = re.sub(r'^\s*```.*?^\s*```[^\n]*', '', text, flags=re.M | re.S)
        for target in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = target.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) and not re.match(r'^[A-Za-z]:[/\\]', target):
                continue
            target = target.split('#', 1)[0]
            if not target:
                continue
            checked += 1
            if not (document.parent / urllib.parse.unquote(target)).resolve().exists():
                broken.append({'file': document.relative_to(root).as_posix(), 'target': target})
    assert not broken, broken
    readme = (root / 'README.md').read_text(encoding='utf-8-sig')
    assert '| R03 |' in readme and '| V39 |' in readme and '| V40 |' not in readme

    result = {
        'status': 'passed', 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'requests': requests, 'repository': replies['repository']['full_name'],
        'head': actual, 'stars': replies['repository']['stargazers_count'],
        'forks': replies['repository']['forks_count'], 'upstream_code_changed': False,
        'archive': archive_path.relative_to(root).as_posix(), 'archive_sha256': digest(archive_path.read_bytes()),
        'source_files_verified': len(hashes), 'local_source_unchanged': True,
        'original_subtitle_and_mit_bytes_equal': True, 'product_frozen_files_verified': len(frozen),
        'historical_upstream_test_methods': 20, 'historical_product_test_methods': 897,
        'tests_rerun_this_review': False, 'browser_started': False, 'unused_browser_tabs_created': 0,
        'gui_started': False, 'virtualization_started': False, 'provider_calls': 0,
        'new_model_or_render_calls': 0, 'new_skills_installed': 0,
        'markdown_files_checked': len(documents), 'local_file_links_checked': checked,
        'broken_local_file_links': broken, 'complete_capcut_parity_accepted': False,
        'goal_still_active': True,
        'historical_evidence': {p.relative_to(root).as_posix(): digest(p.read_bytes())
                                for p in (refresh_path, increment_path, evidence / 'range-edits-20261018.json')},
        'document_sha256': {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in documents},
        'script_sha256': digest(Path(__file__).read_bytes()),
        'scope': 'Two current public GitHub GETs; source/archive/product byte and local document link checks. Prior tests remain historical and are not added to this review.',
    }
    (output / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                               encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ('status', 'head', 'stars', 'forks',
          'source_files_verified', 'product_frozen_files_verified', 'local_file_links_checked')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
