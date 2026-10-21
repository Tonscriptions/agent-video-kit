"""Bind current controls, native media, isolated install and four unregistered deltas."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/audio-source-origin-20261021-lab'
REPORT = 'docs/validation/原生音频起点与同步独立实验_2026-10-21.md'
CONTRACT = 'docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md'


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def main():
    output = REL / 'audit-r1.json'
    assert not output.exists()
    current = frozen()
    media = read(REL / 'media-audit-r1.json')
    assert media['status'] == 'passed-native-and-isolated-media-awaiting-skills-and-complete-suite'
    assert current == media['frozen_inputs'] and len(current) == 259
    parent = read(REL / 'foundation-r1.json')['source_inputs']
    modified = {'product/src/ai_ad_editor/' + name + '.py' for name in ('multicam', 'render', 'audio_stretch', 'capabilities')}
    added = {'product/tests/test_audio_source_origin.py'}
    assert len(parent) == 258 and set(current) - set(parent) == added
    assert {name for name in parent if parent[name] != current[name]} == modified
    related = read(REL / 'related-r1.json')
    assert sha(REL / 'related-r1.json') == media['related_sha256']
    assert related['status'] == 'passed-related-regressions' and related['terminal_ok'] and related['exit_code'] == 0
    assert related['methods'] == related['distinct_methods'] == 226 and related['skipped'] == 0
    assert len(related['method_ids']) == len(set(related['method_ids'])) == 226
    assert related['frozen_before'] == related['frozen_after'] == current
    assert related['frozen_equal'] and related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert sha(REL / 'related-r1.log') == related['log_sha256']
    assert sha(REL / 'foundation-r1.json') == related['fixture_manifest_sha256']
    for name, digest in related['script_hashes'].items():
        assert sha(ROOT / 'scripts' / name) == digest
    for name, digest in related['fixture_inputs'].items():
        assert sha(ROOT / name) == digest
    assert len(related['fixture_inputs']) == 8
    for name, row in media['media'].items():
        path = ROOT / name
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    assert len(media['media']) == 42 and sum(name.endswith('.gif') for name in media['media']) == 14
    native = read(REL / 'native-r1/verification.json')
    installed = read(REL / 'installed-r1/verification.json')
    assert sha(REL / 'native-r1/verification.json') == media['native_sha256']
    assert sha(REL / 'installed-r1/verification.json') == media['installed_sha256']
    for item in (native, read(REL / 'installed-r1/media/verification.json')):
        assert item['status'] == 'passed' and item['frozen_before'] == item['frozen_after'] == current
        assert item['cli_calls'] == 23 and item['native_commands'] == 32 and len(item['checks']) == 39
        assert all(row['ok'] for row in item['checks']) and set(item['cases']) == {'native', 'offset'}
        assert item['script_sha256'] == sha(ROOT / 'scripts/smoke_audio_source_origin.py')
    assert installed['status'] == 'passed' and installed['frozen_before'] == installed['frozen_after'] == current
    assert installed['isolated_cli_calls'] == 26 and installed['module_origin_probes'] == 1
    assert len(installed['checks']) == 15 and all(row['ok'] for row in installed['checks'])
    assert len(installed['resource_hashes']) == 161 and len(installed['optional_numpy_addon']['files']) == 933
    for name, digest in installed['resource_hashes'].items():
        assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
    drafts = read(REL / 'skills-draft-r1.json')
    assert drafts['status'] == 'passed-four-unregistered-drafts' and drafts['skill_count'] == 4 and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT / row['path']) == row['sha256'] and row['validator_exit_code'] == 0 and not row['registered']
        assert sha(ROOT / row['parent_snapshot']) == row['parent_sha256']
    snapshot_dir = REL / 'before-skill-audit-documents-r1'
    snapshot_dir.mkdir()
    documents, preserved = {}, {}
    for name, digest in media['documents'].items():
        path = ROOT / name
        assert sha(path) == digest
        snapshot = snapshot_dir / path.name
        snapshot.write_bytes(path.read_bytes())
        preserved[name] = {'snapshot': snapshot.relative_to(ROOT).as_posix(), 'sha256': digest}
        prefix = 'docs/validation/evidence/audio-source-origin-20261021-lab' if name == 'README.md' else (
            'evidence/audio-source-origin-20261021-lab' if name.startswith('docs/validation/') else '../validation/evidence/audio-source-origin-20261021-lab')
        block = f'''<!-- AUDIO-STANDALONE-AUDIT-R1 -->
当前独立审计：259 产品输入，226 个不同相关方法、{related['suite_seconds']:.3f} 秒、0 跳过；原生 23 CLI/39 检查、新隔离 26 CLI/15 安装＋39 媒体检查均已完成，42 资产/14 GIF。四份 Skill 增量已基于真实发布 V86 父版验证，**未注册**；发布时只合入新块及记录的精确父版文字更新，不能用旧父版全文覆盖后续 V87 指导。
完整 **2031** 方法是预计数量，尚未启动，须绑定实际发布的 V87（2019 方法）后再运行；当前 226 是子集，不能累计成新全量结果。尚未合入 main 或推送；剪映完整功能/自然效果等价未验收。
[独立审计]({prefix}/audit-r1.json) · [四份未注册增量]({prefix}/skills-draft-r1.json)。文中早期阶段的“待完成”按各自日期保留，当前状态以本段为准。
<!-- /AUDIO-STANDALONE-AUDIT-R1 -->'''
        text = path.read_text('utf8')
        assert '<!-- AUDIO-STANDALONE-AUDIT-R1 -->' not in text
        at = text.index('\n')
        text = text[:at] + '\n\n' + block + '\n' + text[at:]
        path.write_text(text, encoding='utf8', newline='\n')
        documents[name] = sha(path)
    assert frozen() == current
    result = {
        'status': 'passed-standalone-audit', 'at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_inputs': current, 'source_parent_inputs': parent,
        'modified_runtime_inputs': sorted(modified), 'added_inputs': sorted(added),
        'targeted_methods': 226, 'distinct_methods': 226, 'related_seconds': related['suite_seconds'],
        'related_sha256': sha(REL / 'related-r1.json'), 'media_audit_sha256': sha(REL / 'media-audit-r1.json'),
        'documents': documents, 'historical_document_snapshots': preserved,
        'media': media['media'], 'asset_count': 42, 'GIF_count': 14,
        'media_manifest_sha256': sha(REL / 'media-manifest-r1.json'), 'static_review_sha256': sha(REL / 'static-review-r1.json'),
        'native_verification_sha256': sha(REL / 'native-r1/verification.json'),
        'isolated_verification_sha256': sha(REL / 'installed-r1/verification.json'),
        'skill_draft_sha256': sha(REL / 'skills-draft-r1.json'),
        'native_cli_calls': 23, 'native_other_commands': 32, 'native_checks': 39,
        'isolated_cli_calls': 26, 'isolated_origin_processes': 1, 'isolated_origin_modules': 14,
        'isolated_installer_checks': 15, 'isolated_media_checks': 39,
        'runtime_resource_count': 161, 'numpy_addon_files': 933, 'base_installer_numpy_included': False,
        'unregistered_skill_deltas': 4, 'parent_media_reused': False, 'native_windows': True,
        'virtualization': False, 'network': False, 'full_suite_started': False,
        'expected_future_full_methods': 2031, 'expected_future_parent_full_methods': 2019,
        'main_integrated': False, 'skills_registered': False, 'continuous_playback_reviewed': False,
        'audio_reviewed': False, 'full_capcut_parity': False, 'generator_sha256': sha(__file__)}
    write(output, result)
    links = []
    for name in documents:
        path = ROOT / name
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)', path.read_text('utf8')):
            target = unquote(token.strip('<>').split('#', 1)[0])
            if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            resolved = (path.parent / target).resolve()
            assert resolved.is_relative_to(ROOT) and resolved.exists(), (name, token)
            links.append({'document': name, 'target': resolved.relative_to(ROOT).as_posix()})
    result['local_links'] = links
    write(output, result)
    (REL / 'finalize-standalone-r1.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status': result['status'], 'frozen_inputs': 259, 'related_methods': 226,
                      'assets': 42, 'GIFs': 14, 'unregistered_deltas': 4, 'document_links': len(links)}))


if __name__ == '__main__':
    main()
