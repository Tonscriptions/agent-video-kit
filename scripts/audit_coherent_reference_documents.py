"""Check V42 research documentation against frozen unsuccessful evidence."""
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


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run(output):
    assert output.is_relative_to(EV) and not output.exists(), output
    output.write_text('{"status":"checking"}\n', encoding='utf-8', newline='\n')
    documents = [ROOT / 'README.md', ROOT / 'AGENTS.md', *sorted((ROOT / 'docs').rglob('*.md'))]
    local = external = anchors = 0
    broken = []
    for path in documents:
        text = path.read_text(encoding='utf-8-sig')
        assert text.strip(), path
        text = re.sub(r'^\s*```.*?^\s*```[^\n]*', '', text, flags=re.M | re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
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
    readme = (ROOT / 'README.md').read_text('utf-8-sig')
    rows = re.findall(r'^\| V(\d{2}) \|', readme, flags=re.M)
    assert [int(n) for n in rows] == list(range(1, 43))
    assert readme.index('V42（研究）') < readme.index('最近产品 V41：')
    row42 = next(line for line in readme.splitlines() if line.startswith('| V42 |'))
    for text in ('研究', '41', '124', '4/12', '未产品化', '未重跑'):
        assert text in row42, text
    core = [ROOT / n for n in ('docs/README.md', 'docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md')]
    for path in core:
        text = path.read_text('utf-8-sig')
        for word in ('V42（研究）', '12 区域中 4 失败', '未重跑', '137 产品文件'):
            assert word in text, (path, word)
    progress = (ROOT / 'docs/构建进度总表_2026-10-16.md').read_text('utf-8-sig')
    assert '| Skill 审计 | 14 Skills、137 引用' in progress
    assert '既有 22 项（10＋12）包含在本轮 41 项中，已重跑' in progress
    assert '[当前审计](./validation/evidence/docs-audit-coherent-reference-20261018.json)' in progress
    contract = ROOT / 'docs/specs/空间与时序一致参考选择研究契约_v0.1_2026-10-18.md'
    report = ROOT / 'docs/validation/空间与时序一致参考选择实测_2026-10-18.md'
    assert '研究已完成' in contract.read_text('utf-8-sig') and '256N' in contract.read_text('utf-8-sig')
    report_text = report.read_text('utf-8-sig')
    assert all(f'| Q{i:02} |' in report_text for i in range(1, 13))
    assert '不是第三方盲测' in report_text and '测量完成后追加的诊断' in report_text

    evidence = EV / 'coherent-reference-20261018'
    record = load(evidence / 'verification.json')
    assert record['status'] == 'research_completed_quality_gate_failed'
    assert record['goal_still_active'] and not record['candidate_promoted']
    assert not record['natural_quality_accepted'] and not record['complete_capcut_parity_accepted']
    assert record['scored_regions'] == 12 and record['failed_scored_regions'] == 4
    assert record['fresh_holdout_strict_mse_gain_regions'] == 0
    assert not record['numerical_improvement_supported_on_fresh_holdout']
    assert record['research_tests']['methods'] == 41 and record['research_tests']['skipped'] == 0
    assert record['development_tests_not_additive']['methods'] == 35
    assert record['research_candidate_frames'] == 124 and record['network_guard_events'] == []
    assert record['research_cli']['successful_invocations'] == 2
    assert record['research_cli']['preexecution_cancelled_invocations'] == 1
    assert not record['research_cli']['production_cli']
    prior = load(EV / 'html-motion-20261018.json')
    assert prior['full']['methods'] == 975 and prior['full']['terminal_ok'] and prior['full']['skipped'] == 0
    assert sha(EV / 'html-motion-final-full-20261018.log') == prior['full']['log_sha256']
    assert record['product_baseline']['full_regression_rerun_this_research_round'] is False
    assert record['frozen_product'] == prior['full']['frozen_after']
    assert len(record['frozen_product']) == 137
    for name, expected in record['frozen_product'].items():
        assert sha(ROOT / name) == expected, name
    for name, expected in record['frozen_sources'].items():
        assert sha(ROOT / name) == expected, name
        ast.parse((ROOT / name).read_text('utf-8-sig'), filename=name)
    for name, item in record['support_files'].items():
        path = evidence / name
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], name
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None, name
    with zipfile.ZipFile(evidence / 'final-source.zip') as archive:
        assert set(archive.namelist()) == set(record['frozen_sources'])
        for name, expected in record['frozen_sources'].items():
            assert digest(archive.read(name)) == expected
    development = load(evidence / 'development.json')
    with zipfile.ZipFile(evidence / 'development-source.zip') as archive:
        for name, expected in development['research_before'].items():
            assert digest(archive.read(name)) == expected
    final = load(evidence / 'final.json')
    assert final['research_before'] == final['research_after']
    assert record['frozen_product'] == final['production_before'] == final['production_after']
    assert final['runtime']['model_runs'] == 0 and not final['runtime']['browser_or_virtualization']
    gallery = ROOT / record['public_media']['directory']
    assert sha(gallery / 'verification.json') == record['public_media']['record_sha256']
    media = load(gallery / 'verification.json')
    assert media['natural_media_published'] is False and media['continuous_playback_reviewed'] is False
    assert len(media['files']) + 1 == 36 and len(media['lossless_streams']) == 10
    for name, item in media['files'].items():
        assert (gallery / name).stat().st_size == item['bytes'] and sha(gallery / name) == item['sha256']
    assert set(media['cases']) == {'two_surfaces', 'two_motion_cut', 'elastic_exposure'}
    for case in media['cases'].values():
        assert case['source_fps'] == 12 and case['frames'] == 12 and case['gif_duration_ms'] == 1000
    skills_path = EV / 'coherent-reference-skills-20261018.json'
    skills = load(skills_path)
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 137
    assert skills['generator_sha256'] == sha(ROOT / 'scripts/audit_source_edit_skills.py')
    for item in skills['results']:
        assert item['validator_exit_code'] == 0 and item['installed_directory_resolves_to_repo']
        assert sha(ROOT / 'skills' / item['skill'] / 'SKILL.md') == item['sha256']
    result = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator': 'scripts/audit_coherent_reference_documents.py', 'generator_sha256': sha(Path(__file__)),
        'documents_checked': len(documents), 'local_file_references_checked': local,
        'external_references_not_fetched': external, 'anchor_only_references_not_validated': anchors,
        'broken_local_references': broken, 'readme_numbered_rows': len(rows),
        'research_quality_gate_failed_preserved': True, 'candidate_promoted': False,
        'product_frozen_file_count': len(record['frozen_product']), 'product_baseline': 'V41/975, not rerun',
        'frozen_research_and_generator_files_checked': len(record['frozen_sources']),
        'support_files_checked': len(record['support_files']), 'public_media_files_checked': 36,
        'skills': {'count': 14, 'local_links': 137, 'record_sha256': sha(skills_path)},
        'document_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in [ROOT / 'README.md', *core, contract, report]},
        'primary_evidence_sha256': sha(evidence / 'verification.json'), 'goal_still_active': True,
        'complete_capcut_parity_accepted': False}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ('status', 'documents_checked', 'local_file_references_checked',
        'readme_numbered_rows', 'research_quality_gate_failed_preserved')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
