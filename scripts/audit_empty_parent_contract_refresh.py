"""Audit the exact parent test refresh while retaining original execution scopes."""
from datetime import datetime, timezone
from pathlib import Path
from run_frozen_regression import frozen
from run_empty_native_after_nested import read, save, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/native-empty-window-20261021-lab'


def main():
    output = REL / 'audit-r2.json'
    assert not output.exists()
    old = read(REL / 'audit-r1.json')
    refresh = read(REL / 'parent-contract-refresh-r1.json')
    current = frozen()
    original = refresh['frozen_before']
    assert old['status'] == 'passed-standalone-audit' and old['frozen_inputs'] == original
    assert current == refresh['frozen_after'] and len(current) == 256
    assert set(current) == set(original) and {n for n in original if original[n] != current[n]} == {'product/tests/test_cli.py'}
    assert refresh['runtime_inputs_changed'] is False
    for key, expected in (('before_test_snapshot', original['product/tests/test_cli.py']), ('after_test_snapshot', current['product/tests/test_cli.py'])):
        assert sha(ROOT / refresh[key]) == expected
    for name, row in refresh['preserved_preflight_scripts'].items():
        assert sha(ROOT / name) == sha(ROOT / row['snapshot']) == row['sha256']
    controls = read(REL / 'parent-contract-controls-r1.json')
    assert controls['terminal_ok'] and controls['methods'] == 4 and controls['skipped'] == 0 and controls['frozen_equal']
    assert controls['frozen_before'] == controls['frozen_after'] == current
    assert sha(REL / 'parent-contract-controls-r1.log') == controls['log_sha256']
    assert sha(ROOT / 'scripts/run_empty_parent_contract_controls.py') == controls['generator_sha256']
    related = read(REL / 'related-r2.json')
    assert related['status'] == 'passed-related-regressions' and related['distinct_methods'] == 293 and related['skipped'] == 0
    assert related['frozen_before'] == related['frozen_after'] == original
    assert len(related['method_ids']) == len(set(related['method_ids'])) == 293
    assert not set(controls['method_ids']) & set(related['method_ids'])
    for name, digest in related['script_hashes'].items():
        assert sha(ROOT / 'scripts' / name) == digest
    for label, count in (('index',37), ('reverse',50), ('sequence',63), ('preview',22), ('nested',105), ('empty',16)):
        path = REL / (label + '-final-r2.json')
        item = read(path)
        assert sha(path) == related['families'][label]['evidence_sha256']
        assert item['terminal_ok'] and item['methods'] == count and item['skipped'] == 0
        assert item['frozen_before'] == item['frozen_after'] == original
        assert item['external_fixture_count'] == 8 and item['external_fixtures_equal']
        assert item['verification_scripts_equal'] and item['external_fixture_manifest_unchanged']
    for name in ('native-r2/verification.json', 'installed-r1/verification.json', 'installed-r1/media/verification.json'):
        item = read(REL / name)
        assert item['status'] == 'passed' and item['frozen_before'] == item['frozen_after'] == original
        assert all(row['ok'] for row in item['checks'])
    installation = read(REL / 'installed-r1/verification.json')
    assert len(installation['resource_hashes']) == 161
    for name, digest in installation['resource_hashes'].items():
        assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
    for name, row in old['media'].items():
        assert sha(ROOT / name) == row['sha256']
    foundation = read(REL / 'foundation-r2.json')
    parent = foundation['source_inputs']
    assert len(parent) == 255 and set(current)-set(parent) == {'product/tests/test_native_empty_window.py'}
    assert {name for name in parent if parent[name] != current[name]} == {'product/src/ai_ad_editor/reverse_video_clock.py'}
    assert sha(REL / 'skills-draft-r1.json') == old['skill_draft_sha256']
    for row in read(REL / 'skills-draft-r1.json')['skills'].values():
        assert sha(ROOT / row['path']) == row['sha256']
        assert sha(ROOT / row['parent_snapshot']) == row['parent_sha256'] and not row['registered']
    message = '''<!-- NATIVE-EMPTY-PARENT-CONTRACT-REFRESH -->
已原样继承父候选对 `test_cli.py` 的旧 CFR 警告断言更新；256 输入中只此测试文件改变，161 个运行时资源未改变。
当前新跑 4 项既有 CLI 时钟控制通过（2.608 秒、0 跳过）。先前 293 项、native-r2 与 installed-r1 保留原实际冻结版本，不写成重新执行；它们的全部运行时代码与当前相同。
父基线改用 foundation-r2，后续入口为 run_empty_native_after_nested_r2.py / publish_native_empty_window_r2.py，并要求 V84 已发布的 full-r2 收据。
此候选的完整 1973 方法回归仍未启动，尚未合入 main、推送或注册 Skill。
<!-- /NATIVE-EMPTY-PARENT-CONTRACT-REFRESH -->'''
    documents = {}
    for name in old['documents']:
        path = ROOT / name
        text = path.read_text('utf8')
        assert 'NATIVE-EMPTY-PARENT-CONTRACT-REFRESH' not in text
        position = text.index('\n')
        path.write_text(text[:position]+'\n\n'+message+'\n'+text[position:], encoding='utf8', newline='\n')
        documents[name] = sha(path)
    record = dict(old)
    record.update(frozen_inputs=current, original_runtime_frozen_inputs=original,
        original_runtime_audit_sha256=sha(REL / 'audit-r1.json'), documents=documents,
        parent_contract_refresh_sha256=sha(REL / 'parent-contract-refresh-r1.json'),
        foundation_r2_sha256=sha(REL / 'foundation-r2.json'), related_runtime_reexecuted=False,
        media_or_installation_reexecuted=False, current_existing_cli_controls=4,
        current_existing_cli_controls_sha256=sha(REL / 'parent-contract-controls-r1.json'),
        runtime_resources_unchanged=True, generator_sha256=sha(__file__),
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    save(output, record)
    print('audit passed: historical 293/runtime/media scope preserved, four fresh CLI controls, 256 inputs')


if __name__ == '__main__':
    main()
