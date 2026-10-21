"""Audit a test-only refresh; retain original runtime/install execution scopes."""
from __future__ import annotations
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
from run_frozen_regression import frozen
from run_nested_native_after_index import read, save, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/nested-native-clock-20261021-lab'


def main():
    output = REL / 'audit-r2.json'
    assert not output.exists()
    prior = read(REL / 'audit-r1.json')
    refresh = read(REL / 'contract-refresh-r1.json')
    current = frozen()
    previous = refresh['frozen_before']
    assert prior['status'] == 'passed-standalone-audit'
    assert previous == prior['frozen_inputs'] and current == refresh['frozen_after']
    assert len(current) == 255 and set(current) == set(previous)
    assert {name for name in current if current[name] != previous[name]} == {'product/tests/test_cli.py'}
    assert refresh['runtime_inputs_changed'] is False
    assert sha(ROOT / refresh['before_test_snapshot']) == previous['product/tests/test_cli.py']
    assert sha(ROOT / refresh['after_test_snapshot']) == current['product/tests/test_cli.py']
    for name, row in refresh['preserved_executed_scripts'].items():
        assert sha(ROOT / name) == sha(ROOT / row['snapshot']) == row['sha256']
    failed = read(REL / 'full-r1.json')
    assert failed['status'] == 'failed' and failed['methods'] == 1957 and not failed['terminal_ok']
    assert failed['frozen_before'] == failed['frozen_after'] == previous
    assert sha(REL / 'full-r1.json') == refresh['failed_full_sha256']
    controls = read(REL / 'contract-controls-r1.json')
    assert controls['status'] == 'passed' and controls['terminal_ok'] and controls['methods'] == 4 and controls['skipped'] == 0
    assert controls['frozen_before'] == controls['frozen_after'] == current and controls['frozen_equal']
    assert sha(REL / 'contract-controls-r1.log') == controls['log_sha256']
    related = read(REL / 'related-r2.json')
    assert related['status'] == 'passed-related-regressions' and related['distinct_methods'] == 277 and related['skipped'] == 0
    assert related['frozen_before'] == related['frozen_after'] == current
    assert len(set(related['method_ids'])) == len(related['method_ids']) == 277
    assert not set(controls['method_ids']) & set(related['method_ids'])
    for name, digest in related['script_hashes'].items():
        assert sha(ROOT / 'scripts' / name) == digest
    for name, count in (('index', 37), ('reverse', 50), ('sequence', 63), ('preview', 22), ('nested', 105)):
        path = REL / (name + '-final-r2.json')
        value = read(path)
        assert sha(path) == related['families'][name]['evidence_sha256']
        assert value['terminal_ok'] and value['status'] == 'passed' and value['methods'] == count and value['skipped'] == 0
        assert value['frozen_before'] == value['frozen_after'] == current
        assert value['external_fixture_count'] == 8 and value['external_fixtures_equal']
        assert value['verification_scripts_equal'] and value['external_fixture_manifest_unchanged']
        inner = read(path.with_name(path.stem + '.source.json'))
        assert sha(path.with_name(path.stem + '.source.log')) == inner['log_sha256']
    for name in ('native-r4/verification.json', 'installed-r1/verification.json', 'installed-r1/media/verification.json'):
        value = read(REL / name)
        assert value['status'] == 'passed' and value['frozen_before'] == value['frozen_after'] == previous
        assert all(row['ok'] for row in value['checks'])
    installation = read(REL / 'installed-r1/verification.json')
    assert len(installation['resource_hashes']) == 161 and installation['isolated_cli_calls'] == 19
    for name, digest in installation['resource_hashes'].items():
        assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
    for name, row in prior['media'].items():
        assert sha(ROOT / name) == row['sha256'] and (ROOT / name).stat().st_size == row['bytes']
    drafts = read(REL / 'skills-draft-r1.json')
    assert drafts['skill_count'] == 4
    for row in drafts['results']:
        assert sha(ROOT / 'skills' / row['skill'] / 'SKILL.md') == row['draft_sha256']
        assert sha(ROOT / row['main_parent_snapshot']) == row['main_parent_sha256']
    record = copy.deepcopy(prior)
    record.update(frozen_inputs=current, full_regression_executed=True, full_regression_passed=False,
        modified_inputs=sorted(set(prior['modified_inputs']) | {'product/tests/test_cli.py'}),
        documents={name: sha(ROOT / name) for name in prior['documents']},
        original_runtime_audit_sha256=sha(REL / 'audit-r1.json'),
        contract_refresh_sha256=sha(REL / 'contract-refresh-r1.json'),
        related_regressions='related-r2.json', related_regressions_sha256=sha(REL / 'related-r2.json'),
        extra_existing_cli_controls=4, extra_existing_cli_controls_sha256=sha(REL / 'contract-controls-r1.json'),
        prior_failed_full_sha256=sha(REL / 'full-r1.json'), prior_failed_full_methods=1957,
        prior_failed_full_seconds=failed['suite_seconds'], prior_full_failures=1,
        runtime_resources_unchanged=True, runtime_media_or_installation_reexecuted=False,
        historical_runtime_scope='native-r4 and installed-r1 remain bound to the original frozen map; only unrelated CLI test assertions changed',
        original_runtime_frozen_inputs=previous, generator_sha256=sha(__file__),
        audited_at_utc=datetime.now(timezone.utc).isoformat())
    save(output, record)
    print(json.dumps({'status': record['status'], 'related_methods': 277, 'extra_existing_cli_controls': 4,
                      'runtime_resources_unchanged': True, 'prior_complete_suite_passed': False}))


if __name__ == '__main__':
    main()
