"""Adapt the tested complete-suite gate to the exact multicam candidate lineage."""
import ast
from pathlib import Path
import re
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/multicam-source-range-20261021-lab'

SOURCE_GATE = '''def source_gate():
    current = frozen()
    base = ROOT / REL
    audit = read(base / 'audit-r2.json')
    assert audit['status'] == 'passed-standalone-audit' and audit['targeted_methods'] == 80
    assert current == audit['frozen_inputs'] and len(current) == 257
    refresh = read(base / 'parent-contract-refresh-r1.json')
    original = refresh['frozen_before']
    assert current == refresh['frozen_after'] and not refresh['runtime_inputs_changed']
    assert original == audit['original_runtime_frozen_inputs'] and audit['runtime_resources_unchanged']
    for name, digest in audit['documents'].items(): assert sha(ROOT / name) == digest
    for name, row in audit['media'].items(): assert sha(ROOT / name) == row['sha256']
    related = read(base / 'related-r1.json')
    assert related['status'] == 'passed-related-regressions' and related['terminal_ok']
    assert related['methods'] == related['distinct_methods'] == 80 and related['skipped'] == 0
    assert len(related['method_ids']) == len(set(related['method_ids'])) == 80
    assert related['frozen_before'] == related['frozen_after'] == current
    assert related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert sha(base / 'related-r1.json') == audit['related_sha256']
    assert sha(base / 'related-r1.log') == related['log_sha256']
    for name, digest in related['script_hashes'].items(): assert sha(ROOT / 'scripts' / name) == digest
    installation = read(base / 'installed-r1/verification.json')
    assert installation['status'] == 'passed' and installation['isolated_cli_calls'] == 18 and installation['module_origin_probes'] == 1
    assert installation['frozen_before'] == installation['frozen_after'] == original
    assert len(installation['resource_hashes']) == 161 and len(installation['optional_numpy_addon']['files']) == 933
    for name, digest in installation['resource_hashes'].items(): assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
    for name in ('native-r1/verification.json', 'installed-r1/media/verification.json'):
        item = read(base / name)
        assert item['status'] == 'passed' and item['cli_calls'] == 15 and item['native_commands'] == 11
        assert len(item['checks']) == 23 and all(row['ok'] for row in item['checks'])
        assert item['frozen_before'] == item['frozen_after'] == original
    drafts = read(base / 'skills-draft-r1.json')
    assert drafts['status'] == 'passed-four-unregistered-drafts' and drafts['skill_count'] == 4 and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT / row['path']) == row['sha256'] and row['validator_exit_code'] == 0
        assert sha(ROOT / row['parent_snapshot']) == row['parent_sha256'] and not row['registered']
    previous = read(base / 'foundation-r2.json')['source_inputs']
    assert len(previous) == 256 and set(current) - set(previous) == ADDED
    assert {name for name in previous if previous[name] != current[name]} == MODIFIED
    fixture = read(base / 'external-fixtures-r1.json')
    assert fixture['status'] == 'passed' and fixture['fixture_count'] == 8
    for row in fixture['fixtures']: assert sha(ROOT / row['path']) == row['sha256']
    return current, previous, {name: sha(ROOT / 'scripts' / name) for name in SCRIPTS}
'''


def replace_assignment(text, name, code):
    node = next(node for node in ast.parse(text).body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))
    lines = text.splitlines(True)
    return ''.join(lines[:node.lineno-1]) + name + ' = ' + code + '\n' + ''.join(lines[node.end_lineno:])


def helpers(text):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(text).body
            if isinstance(node, ast.FunctionDef) and node.name in ('sha', 'save', 'git')}


def main():
    source = ROOT.parent / 'native-empty-window-lab-20261021/scripts/run_empty_native_after_nested_r2.py'
    target = ROOT / 'scripts/run_multicam_after_empty.py'
    assert not target.exists()
    original = source.read_text('utf8')
    text = original.replace('native-empty-window-lab-20261021', 'multicam-source-range-lab-20261021')
    text = text.replace('nested-native-clock-lab-20261021', 'native-empty-window-lab-20261021')
    text = text.replace('native-empty-window-20261021-lab', 'multicam-source-range-20261021-lab')
    text = text.replace('nested-native-clock-20261021-lab', 'native-empty-window-20261021-lab')
    text = text.replace('空视频选区与显式音频保留独立实验', '多机位源覆盖与原速同步独立实验')
    text = text.replace('原生视频空区间契约_实验', '多机位源覆盖与显式缺口策略_实验')
    text = text.replace('external-fixtures-r2.json', 'external-fixtures-r1.json')
    text = text.replace("UPSTREAM_REL / 'full-r2.json'", "UPSTREAM_REL / 'full-r1.json'")
    text = text.replace('published-nested-alignment', 'published-empty-alignment').replace('published_nested_commit', 'published_empty_commit')
    text = text.replace('published-nested', 'published-empty').replace('NATIVE-EMPTY-FULL-R1', 'MULTICAM-FULL-R1')
    mapping = {'1957': '1973', '1973': '1995', '255': '256', '256': '257'}
    text = re.sub(r'\b(?:1957|1973|255|256)\b', lambda match: mapping[match[0]], text)
    text = replace_assignment(text, 'MODIFIED', "{'product/src/ai_ad_editor/' + name + '.py' for name in ('multicam','cli','capabilities')}")
    text = replace_assignment(text, 'ADDED', "{'product/tests/test_multicam_source_range.py'}")
    scripts = ('run_multicam_after_empty.py', 'run_frozen_regression.py', 'run_with_regression_fixtures.py',
        'materialize_regression_fixtures.py', 'run_multicam_related_regressions.py', 'smoke_multicam_source_range.py',
        'verify_multicam_source_range_install.py', 'audit_multicam_related_lab.py',
        'refresh_multicam_parent_contract.py', 'prepare_multicam_full_gate.py')
    text = replace_assignment(text, 'SCRIPTS', repr(scripts))
    node = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name == 'source_gate')
    lines = text.splitlines(True)
    text = ''.join(lines[:node.lineno-1]) + SOURCE_GATE + ''.join(lines[node.end_lineno:])
    assert helpers(text) == helpers(original)
    assert "UPSTREAM_REL / 'full-r1.json'" in text and "upstream['full_methods'] == 1973" in text
    assert "item['methods'] == 1995" in text and "'expected_methods': 1995" in text
    compile(text, target.name, 'exec')
    target.write_text(text, encoding='utf8', newline='\n')
    write(REL / 'full-launcher-reuse-r1.json', {'status': 'prepared-awaiting-preflight', 'source': str(source),
        'source_sha256': sha(source), 'prepared_sha256': sha(target), 'unchanged_helper_AST': list(helpers(text)),
        'expected_complete_methods': 1995, 'expected_parent_complete_methods': 1973,
        'frozen_inputs': 257, 'parent_inputs': 256, 'pinned_scripts': len(scripts),
        'suite_launched': False, 'generator_sha256': sha(__file__)})
    print('prepared complete 1995-method gate; no suite launched')


if __name__ == '__main__':
    main()
