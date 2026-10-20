"""Bind R12 research receipts, unchanged V77 bytes and current document links."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

from review_openfilm_r12 import ROOT, OLD, NEW, TESTS, archive, sha, write
from run_frozen_regression import frozen

BASE = ROOT / 'docs/validation/evidence/openfilm-023-20261020-r12'
REPORT = ROOT / 'docs/OpenFilm_0.2.3增量复用与开发成本评估_2026-10-20.md'
CONTRACT = ROOT / 'docs/specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md'


def read(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(BASE) and not output.exists()
    full_path = ROOT / 'docs/validation/evidence/native-hsl-20261020-v77/full-r3.json'
    full, run, probe = read(full_path), read(BASE / 'run-r1/verification.json'), read(BASE / 'probe-r1/verification.json')
    current = frozen()
    assert full['terminal_ok'] and full['exit_code'] == 0 and full['methods'] == 1746 and full['skipped'] == 0
    assert full['frozen_before'] == full['frozen_after'] == current
    assert len(current) == 233
    for receipt in (run, probe):
        assert receipt['frozen_equal'] and receipt['frozen_before'] == receipt['frozen_after'] == current
        assert receipt['network_calls'] == receipt['product_test_methods_executed'] == 0
        assert not receipt['virtualization']
    assert run['status'] == 'passed_research_only' and run['original_upstream_test_methods'] == 46
    assert run['original_test_files'] == len(TESTS) == 5 and run['installed_new_skills'] == 0
    assert not any(run[k] for k in ('dependencies_installed', 'upstream_cli_executed', 'upstream_browser_executed', 'upstream_provider_executed', 'new_model_inference', 'full_capcut_parity'))
    assert probe['status'] == 'passed_research_observations' and not probe['renderer_executed']
    assert not probe['upstream_whole_module_test'] and probe['browser_processes'] == 0
    assert run['script_sha256'] == sha((ROOT / 'scripts/review_openfilm_r12.py').read_bytes()) == sha((BASE / 'run-r1/executed-review.py.txt').read_bytes())
    assert probe['script_sha256'] == sha((ROOT / 'scripts/probe_openfilm_r12_boundaries.py').read_bytes()) == sha((BASE / 'probe-r1/executed-probe.py.txt').read_bytes())
    old, old_meta = archive(OLD)
    new, new_meta = archive(NEW)
    assert run['archives'] == {'old': old_meta, 'new': new_meta}
    assert read(BASE / 'run-r1/new-tree.json') == {n: {'bytes': len(data), 'sha256': sha(data)} for n, data in sorted(new.items())}
    assert run['tree']['old_files'] == 757 and run['tree']['new_files'] == 781
    assert run['tree']['unchanged_count'] == 616
    assert [len(run['tree'][k]) for k in ('added', 'modified', 'removed')] == [27, 138, 3]
    assert old['LICENSE'] == new['LICENSE'] == (BASE / 'run-r1/LICENSE.txt').read_bytes()
    assert sum(v['unchanged'] for v in run['selected_modules'].values()) == 8
    assert len(run['groups']['packages/openfilm/skills/']['unchanged']) == 31
    assert not run['groups']['packages/openfilm/skills/']['changed']
    assert run['workflow_count'] == 10
    provider = run['groups']['packages/openfilm/studio/server/providers/']
    assert provider['old_files'] == provider['new_files'] == 29 and len(provider['changed']) == 6
    for i, call in enumerate(run['calls'], 1):
        assert call['test'] == TESTS[i - 1] and call['exit_code'] == 0
        assert call['test_source_sha256'] == sha(new['packages/openfilm/' + call['test']])
        for stream in ('stdout', 'stderr'):
            assert call[stream + '_sha256'] == sha((BASE / f'run-r1/test-{i}.{stream}.log').read_bytes())
        assert call['counts']['pass'] == call['counts']['tests']
        assert call['counts']['fail'] == call['counts']['cancelled'] == call['counts']['skipped'] == 0
    observed = probe['observations']
    assert observed == json.loads((BASE / 'probe-r1/stdout.log').read_bytes())
    before, after = observed['cache']['before'], observed['cache']['after']
    assert before['sha256'] != after['sha256'] and before['key'] == after['key']
    assert before['bytes'] == after['bytes'] and before['mtimeMs'] == after['mtimeMs']
    assert observed['assertions'] == 8 and observed['rendered_frames'] == observed['network_calls'] == 0
    for stream in ('stdout', 'stderr'):
        assert probe['execution'][stream + '_sha256'] == sha((BASE / ('probe-r1/' + stream + '.log')).read_bytes())
    assert probe['cache_fragment']['executed_module_sha256'] == sha((BASE / 'probe-r1/cache-key-fragment.mjs.txt').read_bytes())
    acquisition = read(BASE / 'acquisition.json')
    assert acquisition['archive']['sha256'] == new_meta['sha256']
    for name, meta in acquisition['raw_files'].items():
        data = (BASE / name).read_bytes()
        assert len(data) == meta['bytes'] and sha(data) == meta['sha256']
    snap = read(BASE / 'snapshot.json')
    assert snap == acquisition['snapshot'] and snap['head'] == NEW and snap['prior_pin'] == OLD
    assert snap['stars'] == 1524 and snap['forks'] == 153 and snap['compare_commits_ahead'] == 29
    assert read(BASE / 'acquisition-r1/failure.json')['status'] == 'failed_metadata_recording_only'
    compact = [ROOT / 'README.md', ROOT / 'docs/README.md', ROOT / 'docs/构建进度总表_2026-10-16.md',
               ROOT / 'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md', ROOT / 'docs/OpenFilm_0.2.2差异复核与复用取舍_2026-10-20.md']
    paths = [REPORT, CONTRACT, *compact]
    links = []
    for path in paths:
        text = path.read_text(encoding='utf8')
        if path in compact:
            text = text.split('<!-- R12-CURRENT -->', 1)[1].split('<!-- /R12-CURRENT -->', 1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)', text):
            name = unquote(raw.split('#', 1)[0])
            if name and not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', name):
                target = (path.parent / name).resolve(strict=True)
                assert target.is_relative_to(ROOT)
                links.append({'document': path.relative_to(ROOT).as_posix(), 'target': target.relative_to(ROOT).as_posix()})
    changed = subprocess.run(['git', 'diff', '--name-only', '-z'], cwd=ROOT, check=True, capture_output=True).stdout
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only', '-z'], cwd=ROOT, check=True, capture_output=True).stdout
    untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT, check=True, capture_output=True).stdout
    names = {n.decode('utf8') for n in (changed + staged + untracked).split(b'\0') if n}
    assert all(n not in current for n in names)
    bound_paths = {ROOT / name for name in names} | set(paths) | {full_path}
    bound = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(bound_paths) if p != output}
    record = {'status': 'passed_static_research_audit', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'script_sha256': sha(Path(__file__).read_bytes()), 'base_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip(),
              'new_commit': NEW, 'research_original_test_methods': 46, 'research_observations': 4,
              'research_observation_assertions': 8, 'product_test_methods_executed_this_round': 0,
              'prior_full_methods': 1746, 'frozen_product_files': len(current),
              'all_product_bytes_equal_prior_full': True, 'local_document_links_checked': len(links),
              'new_product_features': 0, 'new_encoded_visual_acceptance': 0, 'bound_files': bound, 'links': links}
    assert frozen() == current
    write(output, record)
    print(json.dumps({k: record[k] for k in ('status', 'research_original_test_methods', 'research_observations', 'frozen_product_files', 'local_document_links_checked')}))


if __name__ == '__main__':
    main()
