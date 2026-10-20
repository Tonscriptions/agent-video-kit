"""Bind R11 source research and document links without rerunning product tests."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/openfilm-022-20261020-r11'
REPORT = ROOT / 'docs/OpenFilm_0.2.2差异复核与复用取舍_2026-10-20.md'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(BASE) and not output.exists()
    final = read(BASE / 'run-r2/verification.json')
    assert final['status'] == 'passed_research_only' and final['frozen_equal']
    assert final['frozen_before'] == final['frozen_after'] == frozen()
    assert len(final['frozen_after']) == 219
    assert sha(ROOT / 'scripts/review_openfilm_r11.py') == final['script_sha256'] == sha(BASE / 'run-r2/executed-review.py.txt')
    failed = read(BASE / 'verification.json')
    assert failed['status'] == 'failed' and failed['frozen_equal']
    assert 'calls' not in failed and 'node' not in failed
    assert sha(BASE / 'executed-review.py.txt') == failed['script_sha256']
    acquired = read(BASE / 'acquisition.json')
    for name, row in acquired['raw_files'].items():
        path = BASE / name
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    archive = ROOT / 'sources/upstream/openfilm-022-20261020-r11/repo.zip'
    assert sha(archive) == acquired['zip_sha256'] == final['archives']['new']['sha256']
    assert sha(BASE / 'LICENSE.txt') == final['license_unchanged_sha256']
    assert final['tree']['unchanged_count'] == 718 and len(final['tree']['modified']) == 33
    assert len(final['tree']['added']) == len(final['tree']['deleted']) == 6
    assert final['original_upstream_test_methods'] == 1 and len(final['rate_observations']) == 8
    assert len(final['calls']) == 2
    for call in final['calls']:
        assert call['exit_code'] == 0
        for stream in ('stdout', 'stderr'):
            assert sha(BASE / 'run-r2' / (call['entry'] + '.' + stream + '.log')) == call[stream + '_sha256']
    workflow = read(BASE / 'workflow-inventory.json')
    assert workflow['workflow_count'] == len(workflow['workflows']) == 10
    assert workflow['total_files'] == 31 and workflow['installed_new_skills'] == 0
    with zipfile.ZipFile(archive) as source:
        prefix = 'openfilm-' + final['new_commit'] + '/packages/openfilm/skills/'
        for row in workflow['workflows']:
            for name, key in [('SKILL.md', 'skill_sha256'), ('openfilm.json', 'metadata_sha256'), ('cover.jpg', 'cover_sha256')]:
                assert 'sha256:' + hashlib.sha256(source.read(prefix + row['name'] + '/' + name)).hexdigest() == row[key]
    assert not any(final[key] for key in ('network_calls', 'upstream_cli_executed', 'upstream_browser_executed',
                                         'dependencies_installed', 'new_model_inference', 'virtualization', 'full_capcut_parity'))
    paths = [REPORT]
    if not args.candidate:
        paths += [ROOT / name for name in ('README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
                                          'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md')]
    bound = {}
    links = []
    for path in paths:
        text = path.read_text(encoding='utf8')
        if path != REPORT:
            assert '<!-- R11-CURRENT -->' in text
            text = text.split('<!-- R11-CURRENT -->', 1)[1].split('<!-- /R11-CURRENT -->', 1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)', text):
            name = urllib.parse.unquote(raw.split('#', 1)[0])
            if name and not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', name):
                target = (path.parent / name).resolve(strict=True)
                assert target.is_relative_to(ROOT)
                links.append({'document': path.relative_to(ROOT).as_posix(), 'target': target.relative_to(ROOT).as_posix()})
    for path in [*paths, archive, ROOT / 'scripts/review_openfilm_r11.py', Path(__file__),
                 *(p for p in BASE.rglob('*') if p.is_file() and p != output)]:
        bound[path.relative_to(ROOT).as_posix()] = sha(path)
    record = {'status': 'passed_static_research_audit', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'candidate': args.candidate, 'bound_files': bound, 'local_document_links_checked': len(links),
              'links': links, 'original_test_methods': 1, 'observations': 8,
              'creative_workflows_reviewed': 10, 'new_skills_installed': 0,
              'first_failure_preserved': True, 'product_inputs_unchanged': True,
              'product_test_methods_added': 0, 'new_product_video_samples': 0, 'full_capcut_parity': False}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: record[key] for key in ('status', 'candidate', 'local_document_links_checked', 'product_test_methods_added')}))


if __name__ == '__main__':
    main()
