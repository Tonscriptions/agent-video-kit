"""Audit current local controls while keeping missing media/install/full delivery explicit."""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
from run_frozen_regression import frozen


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'multicam-source-range-lab-20261021'
REL = ROOT / 'docs/validation/evidence/multicam-stream-coverage-20261021-lab'
REPORT = 'docs/validation/多机位原生视频覆盖独立实验_2026-10-21.md'
CONTRACT = 'docs/specs/多机位原生帧覆盖与只读索引契约_实验_v0.1_2026-10-21.md'


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + '\n', encoding='utf8', newline='\n')


def main():
    output = REL / 'development-audit-r1.json'
    assert not output.exists()
    current = frozen()
    assert len(current) == 258
    foundation = read(REL / 'foundation-r1.json')
    parent = foundation['source_inputs']
    assert len(parent) == 257 and set(current) - set(parent) == {'product/tests/test_multicam_stream_coverage.py'}
    changed = {name for name in parent if parent[name] != current[name]}
    assert changed == {'product/src/ai_ad_editor/' + name + '.py' for name in ('multicam', 'cli', 'capabilities')}
    assert all(sha(PARENT / name) == digest for name, digest in parent.items())
    related = read(REL / 'related-r2.json')
    assert related['status'] == 'passed-related-regressions' and related['terminal_ok']
    assert related['methods'] == related['distinct_methods'] == len(set(related['method_ids'])) == 104
    assert related['frozen_before'] == related['frozen_after'] == current
    for field in ('frozen_equal', 'fixtures_unchanged', 'fixture_manifest_unchanged', 'scripts_unchanged'):
        assert related[field]
    assert related['skipped'] == 0 and related['log_sha256'] == sha(REL / 'related-r2.log')
    for name, digest in related['script_hashes'].items():
        assert sha(ROOT / 'scripts' / name) == digest
    for row in foundation['external_fixtures']:
        assert sha(ROOT / row['path']) == row['sha256']
    audio = read(REL / 'audio-only-after-r1.json')
    assert audio['terminal_ok'] and audio['methods'] == 2 and audio['skipped'] == 0
    assert audio['frozen_before'] == audio['frozen_after'] == current
    assert audio['log_sha256'] == sha(REL / 'audio-only-after-r1.log')
    before_audio = read(REL / 'audio-only-before-r1.json')
    assert not before_audio['terminal_ok'] and before_audio['methods'] == 2 and before_audio['frozen_equal']
    assert {name for name in current if before_audio['frozen_before'][name] != current[name]} == {
        'product/src/ai_ad_editor/multicam.py', 'product/src/ai_ad_editor/capabilities.py'}
    old_related = read(REL / 'related-r1.json')
    assert old_related['terminal_ok'] and old_related['methods'] == old_related['distinct_methods'] == 102
    assert old_related['log_sha256'] == sha(REL / 'related-r1.log')
    modules = dict(Counter(name.split('.')[0] for name in related['method_ids']))
    assert modules == {'test_multicam_stream_coverage': 24, 'test_multicam_source_range': 22,
        'test_native_empty_window': 16, 'test_nested_native_clock': 32, 'test_cli': 10}
    tree = ast.parse((ROOT / 'product/tests/test_multicam_stream_coverage.py').read_text('utf8'))
    assert sum(isinstance(node, ast.FunctionDef) and node.name.startswith('test_') for node in ast.walk(tree)) == 24
    snapshots = REL / 'before-current-development-documents-r1'
    snapshots.mkdir()
    document_before = {}
    for name in (REPORT, CONTRACT):
        target = snapshots / (Path(name).name + '.txt')
        shutil.copyfile(ROOT / name, target)
        document_before[name] = {'path': target.relative_to(ROOT).as_posix(), 'sha256': sha(target)}
    report = (ROOT / REPORT).read_text('utf8')
    report = report.replace('| SV-05 | 相邻功能回归 | 102 方法正在执行：22 本实验＋22 父多机位＋16 空选区＋32 嵌套原生时钟＋10 既有媒体/时钟 CLI。尚无终态，不计作通过 | [运行收据](evidence/multicam-stream-coverage-20261021-lab/related-r1.json) |',
        f'| SV-05 | 当前相邻回归 | **104 个不同方法、{related["suite_seconds"]:.3f} 秒、0 跳过**：24 本实验＋22 父多机位＋16 空选区＋32 嵌套原生时钟＋10 既有 CLI。258 输入、8 夹具、6 份验证脚本前后相同。原 102 为修正仅音频分析之前的历史结果，不累计 | [当前收据](evidence/multicam-stream-coverage-20261021-lab/related-r2.json) |')
    old = '当前实现对未知末帧 duration 直接拒绝，连仅音频同步分析也会受此约束；**后续须保留仅分析工作流的有效音频结果，并将未知视频覆盖只作为生成切换段时的拒绝条件**，不能靠扩大拒绝范围代替产品能力。'
    new = ('已修正仅音频分析的过度拒绝：有效音频偏移保留，视频覆盖以 unknown 状态和明确诊断报告；请求生成该机位切换段时仍拒绝。'
        '原两项控制一失败/一通过（2.355 秒），同一断言修复后两项通过（2.459 秒），再执行当前 104 方法。'
        '这两项使用真实本地音频和模拟的视频 EOF 未知状态，不能写成未知末帧封装文件的真实成片验收。'
        '源 SHA 变化、损坏索引等完整性错误不会转换成仅分析成功。')
    assert report.count(old) == 1
    report = report.replace(old, new)
    report += '\n\n[仅音频修复前](evidence/multicam-stream-coverage-20261021-lab/audio-only-before-r1.json) · [同一控制修复后](evidence/multicam-stream-coverage-20261021-lab/audio-only-after-r1.json) · [当前局部开发审计](evidence/multicam-stream-coverage-20261021-lab/development-audit-r1.json)。\n'
    write(ROOT / REPORT, report)
    contract = (ROOT / CONTRACT).read_text('utf8')
    contract = contract.replace('| SV-C06 | 仅音频同步分析应能返回有效偏移和视频覆盖未知的明确诊断；不以视频 EOF 未知直接丢弃有效音频结果 | 尚待修复；现实现会整体拒绝 |',
        '| SV-C06 | 仅音频同步分析返回有效偏移和视频覆盖未知的明确诊断；生成该机位切换段时再拒绝未知 EOF，完整性错误仍直接拒绝 | 两项相同控制修复后通过，纳入当前 104；未知状态为模拟，音频为真实本地生成 |')
    contract = contract.replace('| SV-C11 | 相邻回归、完整回归、离线发行、17 Skills、编号 README 和真实原片/MP4/GIF 各自验收，不混为一个通过数 | 相邻 102 运行中；其余交付未完成 |',
        '| SV-C11 | 相邻回归、完整回归、离线发行、17 Skills、编号 README 和真实原片/MP4/GIF 各自验收，不混为一个通过数 | 当前相邻 104 通过；完整回归、实际公开媒体、隔离安装及 Skill 接入未完成 |')
    write(ROOT / CONTRACT, contract)
    patch_lines = []
    for name in sorted(changed):
        before = (PARENT / name).read_text('utf8').splitlines(True)
        after = (ROOT / name).read_text('utf8').splitlines(True)
        patch_lines += list(difflib.unified_diff(before, after, fromfile='parent/' + name, tofile='candidate/' + name))
    write(REL / 'runtime-r1.patch', ''.join(patch_lines))
    links = []
    for name in (REPORT, CONTRACT):
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)', (ROOT / name).read_text('utf8')):
            target = token.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][\w+.-]*:', target):
                continue
            path = ((ROOT / name).parent / target).resolve()
            assert path.is_relative_to(ROOT) and (path.exists() or path == output), (name, token)
            links.append({'document': name, 'target': path.relative_to(ROOT).as_posix()})
    record = {'status': 'passed-local-controls-only-awaiting-media-install-and-complete-suite',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'frozen_inputs': current, 'parent_inputs': parent,
        'modified_runtime_modules': sorted(changed), 'new_test_methods': 24, 'current_related_methods': 104,
        'current_related_seconds': related['suite_seconds'], 'current_related_sha256': sha(REL / 'related-r2.json'),
        'module_method_counts': modules, 'current_two_controls': 2, 'current_two_control_sha256': sha(REL / 'audio-only-after-r1.json'),
        'historical_related_102_reexecuted_as_104': True, 'counts_are_not_added': True,
        'source_resource_count': sum(name.startswith('product/src/') for name in current),
        'parent_media_or_installed_results_reused': False, 'new_public_media_present': False,
        'new_isolated_install_completed': False, 'full_suite_started': False, 'skills_registered': False,
        'main_integrated': False, 'expected_future_parent_full_methods': 1995, 'expected_future_full_methods': 2019,
        'documents_before': document_before, 'documents': {name: sha(ROOT / name) for name in (REPORT, CONTRACT)},
        'local_links': links, 'patch_sha256': sha(REL / 'runtime-r1.patch'), 'generator_sha256': sha(__file__),
        'next_steps': ['Create real original/native/MP4/GIF evidence with exact PTS, complete lossless RGBA and explicit PCM.',
            'Fresh isolated161-resource validation; NumPy remains an explicit optional local addition outside the basic seven-wheel bundle.',
            'Prepare only new Skill guidance; wait for the actual published1995 parent before the complete2019 suite and ordinary main release.'],
        'limits': ['offset only; no device drift', 'nonzero audio stream origin unaccepted', 'unknown EOF fallback controls simulate only the video unknown state',
            'no natural/HDR/long/RSS/continuous playback/listening or full CapCut parity acceptance']}
    write(output, json.dumps(record, ensure_ascii=False, indent=2))
    shutil.copyfile(__file__, REL / 'development-audit-r1.script.py.txt')
    print(json.dumps({'status': record['status'], 'methods': 104, 'new_methods': 24, 'frozen_inputs': len(current), 'links': len(links)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
