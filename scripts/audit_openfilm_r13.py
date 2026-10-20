"""Verify R13 research bytes, original test receipts, product freeze, and links."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
import zipfile

from run_frozen_regression import frozen
from review_openfilm_r13 import archive, NEW, OLD, SELECTED, TESTS

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/openfilm-024-20261021-r13'
DOCUMENTS = (
    'README.md', 'docs/OpenFilm_0.2.4复用复核与成本更新_2026-10-21.md',
    'docs/OpenFilm当前复用决策_2026-10-18.md',
    'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',
    'docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md',
)
SCRIPTS = ('capture_openfilm_r13.py', 'review_openfilm_r13.py',
           'sync_openfilm_r13_documents.py', 'audit_openfilm_r13.py')


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(BASE) and not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'script_sha256': sha(Path(__file__).read_bytes()), 'checks': []}
    try:
        acquisition = read(BASE / 'acquisition-r1/verification.json')
        review = read(BASE / 'run-r1/verification.json')
        full = read(ROOT / 'docs/validation/evidence/timeline-preview-20261020-v78/full-r2.json')
        current = frozen()
        assert len(current) == 235
        assert current == acquisition['frozen_before'] == acquisition['frozen_after']
        assert current == review['frozen_before'] == review['frozen_after']
        assert current == full['frozen_before'] == full['frozen_after']
        assert full['methods'] == 1768 and full['skipped'] == 0 and full['terminal_ok'] and full['frozen_equal']
        record['frozen_product_inputs'] = current
        record['checks'].append('235 product inputs byte-equal to both R13 phases and V78 historical full run')
        assert acquisition['status'] == 'passed_acquisition_only' and review['status'] == 'passed_research_only'
        assert acquisition['head_commit'] == NEW and acquisition['base_commit'] == OLD
        assert acquisition['ahead_by'] == 3 and acquisition['latest_release_tag'] == 'v0.2.2'
        assert len(acquisition['requests']) == 5
        for request in acquisition['requests']:
            data = (ROOT / request['path']).read_bytes()
            assert request['sha256'] == sha(data) and request['bytes'] == len(data)
            assert request['status'] == 200 and request['http_date'] and request['received_at_utc']
        captured = datetime.fromisoformat(acquisition['requests'][0]['received_at_utc']).astimezone(timezone(timedelta(hours=8)))
        report = (ROOT / DOCUMENTS[1]).read_text(encoding='utf8')
        assert captured.strftime('%Y-%m-%d %H:%M:%S') in report
        assert acquisition['stars'] == 1546 and acquisition['forks'] == 154
        record['checks'].append('5 acquired responses/archive hashes, source version, release distinction and dated community snapshot')
        old, old_meta = archive(OLD)
        new, new_meta = archive(NEW)
        assert review['archives'] == {'old': old_meta, 'new': new_meta}
        assert len(old) == len(new) == 781
        expected = {'added': sorted(new.keys() - old.keys()), 'removed': sorted(old.keys() - new.keys()),
                    'modified': sorted(n for n in old.keys() & new.keys() if old[n] != new[n]),
                    'unchanged': sorted(n for n in old.keys() & new.keys() if old[n] == new[n])}
        assert len(expected['modified']) == 25 and len(expected['unchanged']) == 756
        assert not expected['added'] and not expected['removed']
        for key, value in expected.items():
            assert review['tree'][key] == value
        manifest = read(BASE / 'run-r1/new-tree.json')
        assert manifest == {n: {'bytes': len(data), 'sha256': sha(data)} for n, data in new.items()}
        record['checks'].append('both pinned ZIPs and full 781-file inventory / 25-file delta')
        assert len(SELECTED) == 16 and set(review['selected_modules']) == set(SELECTED)
        assert sum(value['unchanged'] for value in review['selected_modules'].values()) == 13
        for name in SELECTED:
            assert review['selected_modules'][name] == {'old_sha256': sha(old[name]), 'new_sha256': sha(new[name]), 'unchanged': old[name] == new[name]}
            for label, files in (('old', old), ('new', new)):
                assert (BASE / 'run-r1/selected' / label / name).read_bytes() == files[name]
        for name, info in review['legal'].items():
            assert info['unchanged'] and info['sha256'] == sha(new[name]) and new[name] == old[name]
            assert (BASE / 'run-r1/legal' / (name + '.txt')).read_bytes() == new[name]
        assert len(review['legal']) == 7
        record['checks'].append('16 candidate old/new originals and 7 unchanged legal texts')
        assert review['workflow_count'] == 10
        for prefix, count in (('packages/openfilm/skills/', 31), ('packages/openfilm/studio/server/providers/', 29)):
            group = review['groups'][prefix]
            assert group['old_files'] == group['new_files'] == group['unchanged'] == count and not group['changed']
            assert {n: v for n, v in old.items() if n.startswith(prefix)} == {n: v for n, v in new.items() if n.startswith(prefix)}
        record['checks'].append('10 Skills / 31 files and 29 provider files unchanged; no new installations')
        assert len(review['calls']) == len(TESTS) == 7
        counts = []
        for index, call in enumerate(review['calls'], 1):
            assert call['test'] == TESTS[index - 1] and call['test_source_sha256'] == sha(new[call['test']])
            assert call['exit_code'] == 0
            stdout = (BASE / f'run-r1/test-{index}.stdout.log').read_bytes()
            stderr = (BASE / f'run-r1/test-{index}.stderr.log').read_bytes()
            assert sha(stdout) == call['stdout_sha256'] and sha(stderr) == call['stderr_sha256']
            actual = {k: int(v) for k, v in re.findall(r'^# (tests|pass|fail|skipped|cancelled) (\d+)\s*$', stdout.decode(), re.M)}
            assert actual == call['counts'] and actual['tests'] == actual['pass']
            assert actual['fail'] == actual['skipped'] == actual['cancelled'] == 0
            counts.append(actual['pass'])
        assert counts == [30, 1, 3, 9, 3, 6, 13] and sum(counts) == review['original_upstream_test_methods'] == 65
        record['checks'].append('7 unmodified original test inputs and raw TAP outputs: 65/65, no skips')
        modules = review['existing_local_upstream_modules']
        assert len(modules) == 6
        assert sum(bool(info['exact_matches']) for info in modules.values()) == 2
        for name, info in modules.items():
            data = (ROOT / name).read_bytes()
            assert sha(data) == info['sha256'] and len(data) == info['bytes']
            assert info['exact_matches'] == [n for n, value in new.items() if value == data]
        assert review['network_calls'] == 0 and review['new_product_methods_executed'] == 0 and review['new_model_inference'] == 0
        assert not review['dependencies_installed'] and not review['browser_or_player_instance_executed'] and not review['provider_or_agent_sdk_executed']
        record['checks'].append('existing 6 local upstream modules; 2 exact whole-file matches; research-only execution boundary')
        assert (BASE / 'acquisition-r1/executed-capture.py.txt').read_bytes() == (ROOT / 'scripts/capture_openfilm_r13.py').read_bytes()
        assert (BASE / 'run-r1/executed-review.py.txt').read_bytes() == (ROOT / 'scripts/review_openfilm_r13.py').read_bytes()
        record['scripts'] = {name: sha((ROOT / 'scripts' / name).read_bytes()) for name in SCRIPTS}
        references = []
        for name in DOCUMENTS:
            path = ROOT / name
            text = path.read_text(encoding='utf8')
            if name != DOCUMENTS[1]:
                assert text.count('<!-- R13-CURRENT -->') == text.count('<!-- /R13-CURRENT -->') == 1
                text = text.split('<!-- R13-CURRENT -->', 1)[1].split('<!-- /R13-CURRENT -->', 1)[0]
            for target in re.findall(r'\]\(([^)]+)\)', text):
                target = target.strip('<>')
                if urlparse(target).scheme or target.startswith('#'):
                    continue
                resolved = (path.parent / unquote(target.split('#', 1)[0])).resolve()
                assert resolved.is_relative_to(ROOT) and resolved.exists(), (name, target)
                references.append({'document': name, 'target': resolved.relative_to(ROOT).as_posix()})
        record['local_references'] = references
        record['checks'].append('executed script copies, 7 document entries and all new local references')
        record.update(status='passed_research_release_audit', original_test_methods=65,
                      product_tests_run_this_round=0, frozen_equal=True)
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'status': record['status'], 'checks': len(record['checks']),
                      'product_inputs': len(record['frozen_product_inputs']), 'original_methods': 65,
                      'local_references': len(record['local_references'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
