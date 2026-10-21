"""Prepare fresh regression runners without changing any failed-run script."""
from pathlib import Path
from run_nested_native_after_index import read, save, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/nested-native-clock-20261021-lab'


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    receipts = {}
    old = ROOT / 'scripts/run_nested_native_regressions.py'
    new = ROOT / 'scripts/run_nested_native_regressions_r2.py'
    assert not new.exists()
    text = old.read_text('utf8')
    text = text.replace('run_nested_native_regressions.py', new.name)
    text = text.replace("'related-r1.json'", "'related-r2.json'").replace("'-final-r1.json'", "'-final-r2.json'")
    text = replace_once(text, "assert native['frozen_before'] == native['frozen_after'] == before",
        "refresh = json.loads((ROOT / REL / 'contract-refresh-r1.json').read_bytes())\n    assert native['frozen_before'] == native['frozen_after'] == refresh['frozen_before']\n    assert before == refresh['frozen_after'] and refresh['runtime_inputs_changed'] is False")
    new.write_text(text, encoding='utf8', newline='\n')
    receipts[new.name] = {'source': old.name, 'source_sha256': sha(old), 'prepared_sha256': sha(new)}
    old = ROOT / 'scripts/run_nested_native_after_index.py'
    new = ROOT / 'scripts/run_nested_native_after_index_r2.py'
    assert not new.exists()
    text = old.read_text('utf8')
    text = text.replace('run_nested_native_after_index.py', new.name)
    text = text.replace("'audit-r1.json'", "'audit-r2.json'").replace("'related-r1.json'", "'related-r2.json'")
    text = text.replace('before-full-documents-r1', 'before-full-documents-r2').replace('NATIVE-NESTED-FULL-R1', 'NATIVE-NESTED-FULL-R2')
    text = text.replace("base / 'full-r1.json'", "base / 'full-r2.json'").replace("base / 'full-r1.launcher.log'", "base / 'full-r2.launcher.log'")
    text = text.replace('published-index-alignment-r1.json', 'published-index-alignment-r2.json')
    text = replace_once(text, "ADDED = {'product/tests/test_nested_native_clock.py'}", "MODIFIED.add('product/tests/test_cli.py')\nADDED = {'product/tests/test_nested_native_clock.py'}")
    text = replace_once(text, "'prepare_nested_native_skills.py')", "'prepare_nested_native_skills.py', 'run_nested_native_regressions_r2.py',\n           'audit_nested_contract_refresh.py', 'run_nested_contract_controls.py')")
    new.write_text(text, encoding='utf8', newline='\n')
    receipts[new.name] = {'source': old.name, 'source_sha256': sha(old), 'prepared_sha256': sha(new),
                          'upstream_index_full_receipt_remains_r1': "INDEX_REL / 'full-r1.json'" in text}
    message = '''<!-- NATIVE-NESTED-CONTRACT-REFRESH -->
完整回归首轮实际执行 **1957 方法、3263.817 秒、0 跳过，1 项失败**，冻结输入与外部夹具均未改变。
唯一失败为既有 CLI 测试仍要求 `NESTED_SOURCE_CFR_NORMALIZED`；本轮保留原始失败日志和九份执行脚本。
仅更新 `test_cli.py` 的该项协议断言：确认无旧警告，并检查两个子片段均为 `covering-native-source-half-open-v1`。
4 项既有原生 CLI 控制通过；运行时 161 资源未改变，先前媒体和隔离安装记录仍绑定原始冻结版本，不能写成重新执行。
新一轮相关与完整回归使用独立 r2 收据；尚未合入或发布。
<!-- /NATIVE-NESTED-CONTRACT-REFRESH -->'''
    for name in ('README.md', 'docs/validation/嵌套原生VFR时钟独立实验_2026-10-21.md', 'docs/specs/嵌套原生VFR时钟契约_实验_v0.1_2026-10-21.md'):
        path = ROOT / name
        text = path.read_text('utf8')
        assert 'NATIVE-NESTED-CONTRACT-REFRESH' not in text
        position = text.index('\n')
        path.write_text(text[:position] + '\n\n' + message + '\n' + text[position:], encoding='utf8', newline='\n')
    save(REL / 'verification-r2-preparation.json', {'status': 'prepared-new-runners', 'runners': receipts,
         'runtime_inputs_changed': False, 'generator_sha256': sha(__file__)})
    print('prepared two fresh r2 runners; failed-r1 scripts untouched')


if __name__ == '__main__':
    main()
