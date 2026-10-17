"""Audit V41 documents and retained evidence without running renderers or models."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / 'docs/validation/evidence'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def check_files(folder, items):
    for name, item in items.items():
        path = folder / name
        assert path.is_file() and sha(path) == item['sha256'], str(path)
        if 'bytes' in item:
            assert path.stat().st_size == item['bytes'], str(path)
        if path.suffix.lower() in {'.zip', '.whl'}:
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None, str(path)


def run(output):
    assert not output.exists(), output
    # The progress table links this record. Preserve the check attempt on failure.
    output.write_text('{"status":"checking"}\n', encoding='utf-8', newline='\n')
    documents = [ROOT / 'README.md', ROOT / 'AGENTS.md', *sorted((ROOT / 'docs').rglob('*.md'))]
    local = external = anchors = 0
    broken = []
    for path in documents:
        text = path.read_text(encoding='utf-8-sig')
        assert text.strip(), str(path)
        clean = re.sub(r'^\s*```.*?^\s*```[^\n]*', '', text, flags=re.M | re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', clean):
            target = raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) and not re.match(r'^[A-Za-z]:[/\\]', target):
                external += 1
                continue
            target = target.split('#', 1)[0]
            if not target:
                anchors += 1
                continue
            local += 1
            if not (path.parent / urllib.parse.unquote(target)).resolve().exists():
                broken.append({'document': path.relative_to(ROOT).as_posix(), 'target': raw})
    assert not broken, broken
    record = load(EV / 'html-motion-20261018.json')
    assert record['status'] == 'passed' and record['goal_still_active']
    assert record['complete_capcut_parity_accepted'] is False
    full = record['full']
    assert full['methods'] == 975 and full['terminal_ok'] and full['skipped'] == 0 and full['frozen_equal']
    assert len(full['frozen_after']) == 137 and full['frozen_before'] == full['frozen_after']
    assert record['specific']['methods'] == 37 and record['specific']['terminal_ok']
    assert record['specific']['frozen_after'] == full['frozen_after']
    python = 0
    for name, digest in full['frozen_after'].items():
        path = ROOT / name
        assert sha(path) == digest, name
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
            python += 1
    assert python == 130
    assert sha(EV / 'html-motion-final-full-20261018.log') == full['log_sha256']
    assert sha(EV / 'html-motion-final-specific-20261018.log') == record['specific']['log_sha256']
    public = ROOT / 'docs/assets/html-motion-20261018'
    media = record['public_media_audit']
    check_files(public, media['public_files'])
    assert sha(ROOT / 'scripts/audit_html_motion_media.py') == media['generator_sha256']
    assert media['file_count'] == 78 and len(media['public_files']) == 78
    assert sum(item['bytes'] for item in media['public_files'].values()) == 6332822
    cases = record['public_cases']
    assert cases['status'] == 'passed' and cases['calls'] == 30 and cases['source_frozen_equal']
    assert cases['source_after'] == full['frozen_after']
    review_artifacts = load(public / 'native-review-artifacts.json')
    assert sha(ROOT / review_artifacts['generator']) == review_artifacts['generator_sha256']
    assert sha(public / 'S03-timeline.mkv') == review_artifacts['source_video_sha256']
    check_files(EV / 'html-motion-wheel-20261018', record['wheel_files'])
    wheel = record['wheel']
    assert wheel['package_file_count'] == 94 and wheel['actual_fresh_process_clis'] == 11
    assert wheel['source_after'] == full['frozen_after'] and wheel['source_frozen_equal']
    check_files(ROOT / 'product/src', wheel['package_files'])
    development = record['development']
    check_files(EV, development['logs'])
    for name, files in development['original_media_directories'].items():
        check_files(ROOT / 'docs/assets' / name, files)
    check_files(EV / 'html-motion-development-20261018', development['support_files'])
    assert development['historical_source_files'] == 137
    with zipfile.ZipFile(EV / 'html-motion-development-20261018/matroska-source-frozen.zip') as archive:
        assert len(archive.namelist()) == 137
        for name, digest in development['historical_frozen'].items():
            assert 'sha256:' + hashlib.sha256(archive.read(name)).hexdigest() == digest, name
    skills = record['skills']
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 133
    for item in skills['results']:
        assert item['validator_exit_code'] == 0 and item['installed_directory_resolves_to_repo']
        assert sha(ROOT / 'skills' / item['skill'] / 'SKILL.md') == item['sha256']
    static = record['static_review']
    assert len(static['images']) == 6 and not static['listening'] and not static['continuous_playback']
    for item in static['images']:
        assert sha(public / item['path']) == item['sha256']
    upstream = record['openfilm']
    for name, item in upstream['api_raw'].items():
        assert sha(EV / 'openfilm-html-adoption-20261018' / (name + '.raw.json')) == item['sha256']
    original = ROOT / 'sources/upstream/openfilm-0.2.0/repo.zip'
    assert sha(original) == upstream['fixed_source_archive_sha256']
    with zipfile.ZipFile(original) as archive:
        assert archive.testzip() is None
        host_name = next(n for n in archive.namelist() if n.endswith('/packages/openfilm/src/host.mjs'))
        host = archive.read(host_name)
        license_name = host_name[:-len('packages/openfilm/src/host.mjs')] + 'LICENSE'
        assert archive.read(license_name) == (ROOT / 'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()
    original_line = re.search(rb'^export const FILM_CLOCK = .*;$', host, re.M).group(0).rstrip(b'\r')
    module = (ROOT / 'product/src/ai_ad_editor/openfilm_frame_clock.mjs').read_bytes()
    adopted_line = re.search(rb'^export const FILM_CLOCK = .*;$', module, re.M).group(0).rstrip(b'\r')
    assert len(original_line) == 1066 and original_line == adopted_line
    assert 'sha256:' + hashlib.sha256(original_line).hexdigest() == upstream['export_line_sha256']
    readme = (ROOT / 'README.md').read_text(encoding='utf-8-sig')
    ids = [int(n) for n in re.findall(r'^\| V(\d+) \|', readme, re.M)]
    assert ids == list(range(1, 42)), ids
    assert '![原始输入与实际原生时间线成片]' in readme and '本轮 V41：' in readme
    core = ['docs/README.md', 'docs/构建进度总表_2026-10-16.md', 'docs/产品需求与开发路线基线_2026-10-12.md',
            'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md', 'docs/validation/回归验证记录_2026-10-13.md']
    for name in core:
        text = (ROOT / name).read_text(encoding='utf-8-sig')
        assert '本轮 V41：' in text and '本轮 V40：' not in text, name
    progress = (ROOT / core[1]).read_text(encoding='utf-8-sig')
    for prefix in ('| 本次状态快照 |', '| 核对范围 |', '| 最近完整产品回归 |'):
        line = next(line for line in progress.splitlines() if line.startswith(prefix))
        assert '975' in line, line
    report = ROOT / 'docs/validation/离线HTML动效源码与透明合成实测_2026-10-18.md'
    assert '进行中' not in report.read_text(encoding='utf-8-sig')
    generators = ['scripts/smoke_html_motion.py', 'scripts/audit_html_motion_media.py',
                  'scripts/audit_html_motion_wheel.py', 'scripts/audit_openfilm_html_adoption.py',
                  'scripts/create_html_motion_review_artifacts.py', 'scripts/finalize_html_motion.py',
                  'scripts/update_html_motion_documents.py', 'scripts/run_frozen_regression.py',
                  'scripts/audit_html_motion_documents.py']
    for name in generators:
        ast.parse((ROOT / name).read_text(encoding='utf-8-sig'), filename=name)
    assert sha(ROOT / 'scripts/finalize_html_motion.py') == record['generator_sha256']
    assert sha(ROOT / 'scripts/audit_html_motion_wheel.py') == wheel['generator_sha256']
    assert sha(ROOT / 'scripts/audit_openfilm_html_adoption.py') == upstream['generator_sha256']
    value = {'status': 'passed', 'at_utc': datetime.now(timezone.utc).isoformat(),
             'markdown_files': len(documents), 'local_file_links': local, 'broken_links': broken,
             'external_links_not_fetched': external, 'anchors_not_checked': anchors,
             'numbered_rows': len(ids), 'frozen_files': 137, 'python_ast_files': python,
             'public_files': 78, 'wheel_package_files': 94, 'retained_historical_source_files': 137,
             'scope': 'Document links/current metadata and byte-frozen product, evidence, media, wheel, Skills, original clock/MIT; no additional render, model, browser, install or external API.',
             'generator_sha256': sha(Path(__file__)),
             'support_generators': {name: sha(ROOT / name) for name in generators},
             'document_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in documents}}
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value[key] for key in ('status', 'markdown_files', 'local_file_links', 'numbered_rows', 'frozen_files', 'public_files')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
