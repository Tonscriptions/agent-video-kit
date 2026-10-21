"""Bind the refreshed parent, eighty native methods and unchanged media runtime."""
from datetime import datetime, timezone
import json
from pathlib import Path
from run_frozen_regression import frozen
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/multicam-source-range-20261021-lab'


def main():
    read = lambda path: json.loads(Path(path).read_bytes())
    output = REL / 'audit-r2.json'
    assert not output.exists()
    old = read(REL / 'audit-r1.json')
    refresh = read(REL / 'parent-contract-refresh-r1.json')
    current = frozen()
    original = refresh['frozen_before']
    assert old['status'] == 'passed-bounded-lab-audit' and original == old['frozen_inputs']
    assert current == refresh['frozen_after'] and len(current) == 257
    assert set(current) == set(original) and {n for n in original if original[n] != current[n]} == {'product/tests/test_cli.py'}
    assert not refresh['runtime_inputs_changed']
    for key, digest in (('before_test_snapshot', original['product/tests/test_cli.py']), ('after_test_snapshot', current['product/tests/test_cli.py'])):
        assert sha(ROOT / refresh[key]) == digest
    parent = read(REL / 'foundation-r2.json')['source_inputs']
    assert len(parent) == 256 and set(current)-set(parent) == {'product/tests/test_multicam_source_range.py'}
    assert {n for n in parent if parent[n] != current[n]} == {'product/src/ai_ad_editor/'+n+'.py' for n in ('multicam','cli','capabilities')}
    related = read(REL / 'related-r1.json')
    assert related['status'] == 'passed-related-regressions' and related['terminal_ok']
    assert related['methods'] == related['distinct_methods'] == 80 and related['skipped'] == 0
    assert len(related['method_ids']) == len(set(related['method_ids'])) == 80
    assert related['frozen_before'] == related['frozen_after'] == current and related['frozen_equal']
    assert related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert sha(REL / 'related-r1.log') == related['log_sha256']
    assert sha(REL / 'external-fixtures-r1.json') == related['fixture_manifest_sha256']
    for name, digest in related['fixture_inputs'].items(): assert sha(ROOT / name) == digest
    for name, digest in related['script_hashes'].items(): assert sha(ROOT / 'scripts' / name) == digest
    for name in ('native-r1/verification.json', 'installed-r1/verification.json', 'installed-r1/media/verification.json'):
        row = read(REL / name)
        assert row['status'] == 'passed' and row['frozen_before'] == row['frozen_after'] == original
        assert all(check['ok'] for check in row['checks'])
    installation = read(REL / 'installed-r1/verification.json')
    assert len(installation['resource_hashes']) == 161 and installation['isolated_cli_calls'] == 18
    for name, digest in installation['resource_hashes'].items(): assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
    assert len(installation['optional_numpy_addon']['files']) == 933
    for name, row in old['media'].items(): assert sha(ROOT / name) == row['sha256']
    drafts = read(REL / 'skills-draft-r1.json')
    assert drafts['status'] == 'passed-four-unregistered-drafts' and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT / row['path']) == row['sha256'] and row['validator_exit_code'] == 0
        assert sha(ROOT / row['parent_snapshot']) == row['parent_sha256'] and not row['registered']
    snapshots = REL / 'before-parent-contract-documents-r1'
    snapshots.mkdir()
    preserved = {}
    for name, digest in old['documents'].items():
        path = ROOT / name
        assert sha(path) == digest
        target = snapshots / path.name
        target.write_bytes(path.read_bytes())
        preserved[name] = {'snapshot': target.relative_to(ROOT).as_posix(), 'sha256': digest}
    message = f'''<!-- MULTICAM-RELATED-R1 -->
父版测试断言已原样变基。当前关联回归 **80 方法、{related['suite_seconds']:.3f} 秒、0 跳过**：22 多机位＋16 空视频选区＋32 嵌套原生时钟＋10 个既有媒体/时钟 CLI 控制，方法身份无重复。
257 输入和 8 个已提交外部夹具前后相同，四份验证脚本保持不变。当前完整回归仍未启动。
原 23 方法、15 次原生 CLI/11 条其他命令与 18 次隔离 CLI 保留其原实际执行；之后只改变未打包的 test_cli.py，161 运行时资源完全相同，没有将旧媒体和安装标为重跑。
下表 MC-01..12 是首次实验的历史记录，其中“待父测试变基”已由本次完成。尚未合入 main、推送或注册 Skill，剪映全功能与自然质量仍未验收。
<!-- /MULTICAM-RELATED-R1 -->'''
    documents = {}
    for name in old['documents']:
        path = ROOT / name
        text = path.read_text('utf8')
        assert 'MULTICAM-RELATED-R1' not in text
        at = text.index('\n')
        path.write_text(text[:at]+'\n\n'+message+'\n'+text[at:], encoding='utf8', newline='\n')
        documents[name] = sha(path)
    record = dict(old)
    record.update(status='passed-standalone-audit', frozen_inputs=current, source_parent_inputs=parent,
        original_runtime_frozen_inputs=original, targeted_methods=80, current_targeted_methods=80, distinct_methods=80,
        original_runtime_audit_sha256=sha(REL / 'audit-r1.json'), related_sha256=sha(REL / 'related-r1.json'),
        parent_contract_refresh_sha256=sha(REL / 'parent-contract-refresh-r1.json'), documents=documents,
        historical_document_snapshots=preserved, runtime_resources_unchanged=True,
        media_or_installation_reexecuted=False, parent_contract_refresh_rebase_pending=False,
        generator_sha256=sha(__file__), audited_at_utc=datetime.now(timezone.utc).isoformat())
    write(output, record)
    print(json.dumps({'status': record['status'], 'distinct_methods': 80, 'frozen_inputs': 257, 'runtime_changed_after_original_media': False}))


if __name__ == '__main__':
    main()
