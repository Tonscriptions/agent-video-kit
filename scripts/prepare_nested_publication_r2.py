"""Prepare a release gate for the refreshed assertion and fresh full-r2 receipt."""
from pathlib import Path
from run_nested_native_after_index import save, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/nested-native-clock-20261021-lab'


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    source = ROOT / 'scripts/publish_nested_native_clock.py'
    target = ROOT / 'scripts/publish_nested_native_clock_r2.py'
    assert not target.exists()
    text = source.read_text('utf8')
    text = replace_once(text, "TESTS=('test_nested_native_clock',)", "TESTS=('test_nested_native_clock','test_cli')")
    text = replace_once(text, "'native_index_release_tools','publish_nested_native_clock')",
        "'native_index_release_tools','publish_nested_native_clock',\n    'run_nested_native_after_index_r2','run_nested_native_regressions_r2','run_nested_contract_controls',\n    'prepare_nested_contract_refresh','prepare_nested_verification_r2','audit_nested_contract_refresh',\n    'prepare_nested_publication_r2','publish_nested_native_clock_r2')")
    text = text.replace("'audit-r1.json'", "'audit-r2.json'").replace("'related-r1.json'", "'related-r2.json'")
    text = text.replace("label+'-final-r1.json'", "label+'-final-r2.json'")
    text = text.replace('full-after-index-r1/run.json', 'full-after-index-r2/run.json')
    text = text.replace("ROOT/REL/'full-r1.json'", "ROOT/REL/'full-r2.json'")
    text = text.replace("MAIN/REL/'full-r1.json'", "MAIN/REL/'full-r2.json'")
    text = text.replace('published-index-alignment-r1.json', 'published-index-alignment-r2.json')
    text = text.replace('before-full-documents-r1.json', 'before-full-documents-r2.json')
    text = text.replace('{REL}/related-r1.json', '{REL}/related-r2.json').replace('{REL}/full-r1.json', '{REL}/full-r2.json')
    text = replace_once(text, "assert audit['targeted_methods']==277 and audit['source_wheel_installed_resources']==161",
        "assert audit['targeted_methods']==277 and audit['source_wheel_installed_resources']==161\n    refresh=read(ROOT/REL/'contract-refresh-r1.json');original=refresh['frozen_before']\n    assert refresh['frozen_after']==current and not refresh['runtime_inputs_changed']\n    assert audit['original_runtime_frozen_inputs']==original and audit['runtime_resources_unchanged']")
    text = replace_once(text, "assert installation['frozen_before']==installation['frozen_after']==current",
        "assert installation['frozen_before']==installation['frozen_after']==original")
    text = replace_once(text, "assert native['frozen_before']==native['frozen_after']==current",
        "assert native['frozen_before']==native['frozen_after']==original")
    text = replace_once(text, '37＋50＋63＋22＋105＝277 个不同方法、0 跳过；新增 32 包含在嵌套 105 中',
        'r2 为 37＋50＋63＋22＋105＝277 个不同方法、0 跳过；另有 4 项既有 CLI 时钟控制，新 32 包含在嵌套 105 中')
    text = replace_once(text, '19 隔离 CLI＋1 来源进程/11 模块，同样逐帧参考通过',
        '19 隔离 CLI＋1 来源进程/11 模块，同样逐帧参考通过；执行绑定原始冻结版本，之后仅测试断言改变，161 运行时资源完全相同，未重复安装')
    text = replace_once(text, '中间重构缺少原点变量、早期导出路径与描述别名脚本断言失败均保留，未放松逐帧参考',
        '中间重构、早期脚本及完整 r1 的 1957 项/3263.817 秒/1 失败均保留；退休旧 CFR 警告断言后增加双叶原生协议检查，4 控制通过，再执行完整 r2，未放松逐帧参考')
    text = replace_once(text, '公开复现入口为 `scripts/smoke_nested_native_clock.py`',
        '完整 r1 的 1 项失败是既有测试要求退休的 CFR 归一化警告；原始失败、九份执行脚本和修改前后测试已保全。仅更新该断言并新增两个子叶的原生时钟协议检查，运行时代码未改变。r2 专项与完整回归使用新收据；native-r4 和 installed-r1 仍引用实际原执行，161 运行时资源与当前逐字节相同，未将旧媒体或安装写为重跑。\n\n公开复现入口为 `scripts/smoke_nested_native_clock.py`')
    target.write_text(text, encoding='utf8', newline='\n')
    save(REL / 'publication-r2-preparation.json', {'status': 'prepared-awaiting-r2-audit-and-full',
        'source': source.relative_to(ROOT).as_posix(), 'source_sha256': sha(source),
        'prepared': target.relative_to(ROOT).as_posix(), 'prepared_sha256': sha(target),
        'test_only_refresh_explicit': True, 'historical_runtime_scope_preserved': True,
        'generator_sha256': sha(__file__)})
    print('prepared r2 publisher; no main changes or publication')


if __name__ == '__main__':
    main()
