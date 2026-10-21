"""Prepare strict empty-window gates for the refreshed upstream test contract."""
import ast
from pathlib import Path
from run_empty_native_after_nested import read, save, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/native-empty-window-20261021-lab'


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def helpers(tree):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(tree).body
            if isinstance(n, ast.FunctionDef) and n.name in ('sha', 'save', 'git')}


def main():
    assert read(REL / 'audit-r2.json')['runtime_resources_unchanged']
    records = {}
    source = ROOT / 'scripts/run_empty_native_after_nested.py'
    target = ROOT / 'scripts/run_empty_native_after_nested_r2.py'
    assert not target.exists()
    original = source.read_text('utf8')
    text = original.replace('run_empty_native_after_nested.py', target.name)
    text = text.replace("'audit-r1.json'", "'audit-r2.json'").replace("'foundation-r1.json'", "'foundation-r2.json'")
    text = text.replace("UPSTREAM_REL / 'full-r1.json'", "UPSTREAM_REL / 'full-r2.json'")
    text = once(text, "'verify_native_empty_install.py', 'finalize_native_empty_lab.py')",
        "'verify_native_empty_install.py', 'finalize_native_empty_lab.py',\n           'refresh_empty_parent_contract.py', 'run_empty_parent_contract_controls.py',\n           'audit_empty_parent_contract_refresh.py', 'prepare_empty_verification_r2.py')")
    text = once(text, "assert audit['source_wheel_installed_resources'] == 161",
        "assert audit['source_wheel_installed_resources'] == 161\n    refresh = read(base / 'parent-contract-refresh-r1.json')\n    original = refresh['frozen_before']\n    assert refresh['frozen_after'] == current and not refresh['runtime_inputs_changed']\n    assert audit['original_runtime_frozen_inputs'] == original and audit['runtime_resources_unchanged']\n    controls = read(base / 'parent-contract-controls-r1.json')\n    assert controls['terminal_ok'] and controls['methods'] == 4 and controls['skipped'] == 0\n    assert controls['frozen_before'] == controls['frozen_after'] == current\n    assert sha(base / 'parent-contract-controls-r1.json') == audit['current_existing_cli_controls_sha256']")
    for name in ('installation', 'related', 'item', 'native'):
        text = once(text, f"assert {name}['frozen_before'] == {name}['frozen_after'] == current",
                    f"assert {name}['frozen_before'] == {name}['frozen_after'] == original")
    assert helpers(text) == helpers(original)
    compile(text, target.name, 'exec')
    target.write_text(text, encoding='utf8', newline='\n')
    records[target.name] = {'source_sha256': sha(source), 'prepared_sha256': sha(target), 'unchanged_helpers': list(helpers(text))}
    source = ROOT / 'scripts/publish_native_empty_window.py'
    target = ROOT / 'scripts/publish_native_empty_window_r2.py'
    assert not target.exists()
    original = source.read_text('utf8')
    text = original.replace("'audit-r1.json'", "'audit-r2.json'")
    text = once(text, "'verify_native_empty_install','finalize_native_empty_lab','native_index_release_tools','publish_native_empty_window')",
        "'verify_native_empty_install','finalize_native_empty_lab','native_index_release_tools','publish_native_empty_window',\n    'run_empty_native_after_nested_r2','refresh_empty_parent_contract','run_empty_parent_contract_controls',\n    'audit_empty_parent_contract_refresh','prepare_empty_verification_r2','publish_native_empty_window_r2')")
    text = once(text, "assert audit['targeted_methods']==293 and audit['source_wheel_installed_resources']==161",
        "assert audit['targeted_methods']==293 and audit['source_wheel_installed_resources']==161\n    refresh=read(ROOT/REL/'parent-contract-refresh-r1.json');original=refresh['frozen_before']\n    assert refresh['frozen_after']==current and not refresh['runtime_inputs_changed']\n    assert audit['original_runtime_frozen_inputs']==original and audit['runtime_resources_unchanged']\n    controls=read(ROOT/REL/'parent-contract-controls-r1.json')\n    assert controls['terminal_ok'] and controls['methods']==4 and controls['skipped']==0\n    assert controls['frozen_before']==controls['frozen_after']==current\n    assert sha(ROOT/REL/'parent-contract-controls-r1.json')==audit['current_existing_cli_controls_sha256']")
    for name in ('installation', 'related', 'item', 'native'):
        text = once(text, f"assert {name}['frozen_before']=={name}['frozen_after']==current",
                    f"assert {name}['frozen_before']=={name}['frozen_after']==original")
    lines = text.splitlines(True)
    index = next(i for i, line in enumerate(lines) if line.startswith('    message=f"'))
    lines.insert(index+1, "    message+='。293 项专项、媒体与隔离安装保留运行时完全相同的原执行；仅继承父版测试断言后新跑 4 项旧 CLI 控制，未将历史记录标为重跑'\n")
    text = ''.join(lines)
    text = once(text, '37＋50＋63＋22＋105＋16＝293 个不同方法、0 跳过；16 项包含于 293，再包含于完整回归，不累加历史结果',
        '原执行 37＋50＋63＋22＋105＋16＝293 个不同方法、0 跳过；继承父版测试断言后另新跑 4 项既有 CLI 控制，运行时资源不变，16 项包含于 293 与完整回归，不累加历史结果')
    assert helpers(text) == helpers(original)
    compile(text, target.name, 'exec')
    target.write_text(text, encoding='utf8', newline='\n')
    records[target.name] = {'source_sha256': sha(source), 'prepared_sha256': sha(target), 'unchanged_helpers': list(helpers(text))}
    save(REL / 'verification-r2-preparation.json', {'status': 'prepared-not-executed', 'scripts': records,
        'upstream_full_receipt': 'nested-native-clock-20261021-lab/full-r2.json',
        'candidate_first_full_receipt': 'native-empty-window-20261021-lab/full-r1.json',
        'historical_execution_scopes_preserved': True, 'generator_sha256': sha(__file__)})
    print('prepared refreshed full and publication gates; no full run, main changes or publication')


if __name__ == '__main__':
    main()
