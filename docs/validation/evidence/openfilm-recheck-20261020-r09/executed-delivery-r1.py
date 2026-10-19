"""Validate source-review identities and documentation without accepting product WIP."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

from audit_openfilm_refresh import contents
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence/openfilm-recheck-20261020-r09'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = EVIDENCE / 'delivery-r1.json'
    assert not output.exists()
    record = json.loads((EVIDENCE / 'verification.json').read_bytes())
    before = frozen()
    assert before == record['product_before'] == record['product_after']
    assert record['product_unchanged_during_review'] and not record['guard_denied_calls']
    assert record['extracted_fixture_cases'] == 16 and record['fixture_exit'] == 0
    assert not record['upstream_full_modules_run'] and not record['product_regression_rerun']
    for name, expected in record['files'].items():
        assert sha(EVIDENCE / name) == expected['sha256'], name
    assert sha(ROOT / 'scripts/review_openfilm_r09.py') == sha(EVIDENCE / 'executed-review.py')
    repository = json.loads((EVIDENCE / 'repository.json').read_bytes())
    commit = json.loads((EVIDENCE / 'commit.json').read_bytes())
    assert repository['stargazers_count'] == record['stars'] == 1269
    assert repository['forks_count'] == record['forks'] == 128
    assert commit['sha'] == record['head'] == '71922644da5d6b67db2cc796d4e057f98999944f'
    for request in json.loads((EVIDENCE / 'requests.json').read_bytes()):
        path = EVIDENCE / ('commit.json' if '/commits/' in request['url'] else 'repository.json')
        assert sha(path) == request['sha256']
    archive = ROOT / record['archive']
    assert sha(archive) == record['archive_sha256']
    tree = contents(archive.read_bytes())
    assert len(tree) == 757
    assert {name: 'sha256:' + hashlib.sha256(raw).hexdigest()
            for name, raw in tree.items()} == record['tree_hashes']
    assert tree['LICENSE'] == (ROOT / 'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()
    observations = json.loads((EVIDENCE / 'fixture-observations.json').read_bytes())
    assert len(observations['checks']) == 16 and all(row['passed'] for row in observations['checks'])
    cache = observations['cache']
    assert cache['contentBefore'] != cache['contentAfter']
    assert cache['printBefore'] == cache['printAfter'] and cache['keyBefore'] == cache['keyAfter']
    documents = ['README.md', 'docs/README.md', 'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',
                 'docs/OpenFilm诊断模块复用与原生模型故障后续项_2026-10-20.md',
                 EVIDENCE.relative_to(ROOT).as_posix() + '/NOTICE.md']
    links = 0
    for name in documents:
        path = ROOT / name
        text = path.read_text(encoding='utf8')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = unquote(raw.strip('<>').split('#', 1)[0])
            if not target or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', target):
                continue
            assert (path.parent / target).resolve().exists(), name + ' -> ' + target
            links += 1
    readme = (ROOT / 'README.md').read_text(encoding='utf8')
    assert '| R09 |' in readme and '<!-- R09-RESEARCH -->' in readme
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip()
    assert branch == 'main'
    assert frozen() == before
    files = {path.relative_to(ROOT).as_posix(): {'sha256': sha(path), 'bytes': path.stat().st_size}
             for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    for name in [*documents, '.gitattributes', 'scripts/review_openfilm_r09.py',
                 'scripts/audit_openfilm_r09_delivery.py']:
        path = ROOT / name
        files[name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'passed_scoped_research_delivery', 'source_files': 757,
              'extracted_declaration_cases': 16, 'local_document_links': links,
              'product_wip_unchanged': True, 'product_functionality_accepted': False,
              'historical_v67_regression_not_reassigned_to_wip': True,
              'source_reuse_limits_retained': ['minimum_one_worker_is_not_admission',
                                              'custom_name_prevents_batch_reuse',
                                              'size_mtime_cache_can_be_stale'],
              'files': files}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
