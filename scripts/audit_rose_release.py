"""Bind actual ROSE research, bounded docs, Skills and unchanged production inputs."""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path
import re
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save
from run_rose_research import offline
from smoke_fragments import frozen


def audit(output, skills):
    if output.exists():
        raise ValueError('ROSE_FRESH_RELEASE_RECEIPT_REQUIRED')
    events = offline()
    evidence = ROOT/'docs/validation/evidence/rose-native-20261019-v59'
    independent = ROOT/'docs/validation/evidence/rose-independent-20261019-v59'
    receipt = json.loads((evidence/'verification.json').read_bytes())
    checked = json.loads((independent/'verification.json').read_bytes())
    if receipt['status'] != 'actual_inference_published_quality_unaccepted':
        raise ValueError('ROSE_ACTUAL_PUBLICATION_REQUIRED')
    if checked['status'] != 'independent_delivered_checks_passed_quality_separate':
        raise ValueError('ROSE_INDEPENDENT_DELIVERED_CHECK_REQUIRED')
    if checked['source_receipt_sha256'] != sha(evidence/'verification.json'):
        raise ValueError('ROSE_INDEPENDENT_RECEIPT_BINDING_CHANGED')
    if checked['controlled_quality_passed'] != receipt['public']['controlled_quality_passed']:
        raise ValueError('ROSE_CONTROLLED_GATE_DISAGREEMENT')
    for record in (receipt, checked):
        if record['product_integrated'] or record['natural_pixels_published'] or record['full_product_regression_rerun']:
            raise ValueError('ROSE_RESEARCH_SCOPE_CHANGED')
        if record['continuous_playback_reviewed'] or record['audio_listening_reviewed']:
            raise ValueError('ROSE_UNPERFORMED_REVIEW_CLAIM')
    before = frozen()
    historical = json.loads((ROOT/'docs/validation/evidence/effect-automation-20261019-v58/full-final.json').read_bytes())
    if len(before) != 186 or before != receipt['production_sha256'] or before != historical['frozen_after']:
        raise ValueError('ROSE_FROZEN_V58_PRODUCTION_MISMATCH')
    for row in receipt['files']:
        path = ROOT/row['path']
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('ROSE_DELIVERED_FILE_CHANGED: '+row['path'])
    if receipt['natural']['audio']['decoded_pcm_bytes'] != 768000 or not receipt['natural']['audio']['exact']:
        raise ValueError('ROSE_NATURAL_PCM_EVIDENCE_REQUIRED')
    static_path = evidence/'static-review.json'
    static_review = json.loads(static_path.read_bytes())
    if (static_review['status'] != 'agent_static_contacts_reviewed'
            or static_review['continuous_playback_reviewed'] or static_review['audio_listening_reviewed']
            or static_review['natural_pixels_published']):
        raise ValueError('ROSE_STATIC_REVIEW_SCOPE_INVALID')
    if static_review['public'] != json.loads((evidence/'public-static-review.json').read_bytes()):
        raise ValueError('ROSE_PUBLIC_STATIC_REVIEW_RECORD_CHANGED')
    # The private contact path is recorded explicitly; source pixels stay local.
    private_contact = Path(static_review['natural']['local_contact'])
    private_request = json.loads((evidence/'natural-request.json').read_bytes())
    if (static_review['natural']['frame_indices'] != [0, 10, 21, 31]
            or private_contact.resolve() != (Path(private_request['output_path']).parent/'private-contact.png').resolve()
            or static_review['natural']['contact_sha256'] != sha(private_contact)
            or static_review['natural']['contact_sha256'] != receipt['private_contact_sha256']
            or static_review['natural']['quality_accepted']):
        raise ValueError('ROSE_NATURAL_STATIC_REVIEW_BINDING_FAILED')
    guard_dir = ROOT/'docs/validation/evidence/rose-preflight-sync-history-20261019-v59'
    guard = json.loads((guard_dir/'verification.json').read_bytes())
    preflight_release = json.loads((ROOT/'docs/validation/evidence/rose-preflight-collection-20261019-v59/release.json').read_bytes())
    if sha(evidence/'historical-preflight-report.md') != preflight_release['documents']['docs/validation/ROSE本地模型获取与离线预检_2026-10-19.md']:
        raise ValueError('ROSE_HISTORICAL_PREFLIGHT_REPORT_NOT_PRESERVED')
    preflight_skills = json.loads((ROOT/'docs/validation/evidence/rose-preflight-collection-20261019-v59/skills.json').read_bytes())
    original_skill = next(row for row in preflight_skills['results'] if row['skill'] == 'video-cut-local-models')
    if sha(evidence/'historical-preflight-SKILL.md') != original_skill['sha256']:
        raise ValueError('ROSE_HISTORICAL_PREFLIGHT_SKILL_NOT_PRESERVED')
    if (guard['status'] != 'expected_historical_doc_overwrite_rejected' or guard['exit_code'] != 1
            or guard['model_forward_calls'] != 0 or len(guard['documents_unchanged']) != 12):
        raise ValueError('ROSE_HISTORICAL_DOC_OVERWRITE_GUARD_REQUIRED')
    if (sha(guard_dir/'executed-document-sync.py') != guard['historical_generator_sha256']
            or guard['historical_generator_sha256'] != preflight_release['research_sources']['scripts/sync_rose_preflight_documents.py']
            or sha(ROOT/'scripts/sync_rose_preflight_documents.py') != guard['guarded_generator_sha256']
            or sha(guard_dir/'guard.stdout.log') != guard['stdout_sha256']
            or sha(guard_dir/'guard.stderr.log') != guard['stderr_sha256']):
        raise ValueError('ROSE_HISTORICAL_DOC_GUARD_EVIDENCE_CHANGED')
    expected_calls = {'T5': 2, 'T5_blocks': 48, 'transformer': 50, 'transformer_blocks': 1500,
                      'VAE_encode': 1, 'VAE_decode': 1, 'CLIP': 0}
    for name in ('public', 'natural'):
        record = receipt[name]
        if record['worker']['model_calls'] != expected_calls or record['worker']['status'] != 'succeeded':
            raise ValueError('ROSE_REAL_FORWARD_EVIDENCE_REQUIRED: '+name)
        if not record['rgba_roundtrip_exact'] or not record['every_pts_exact'] or not record['original_alpha_exact']:
            raise ValueError('ROSE_ENCODED_DELIVERY_EVIDENCE_REQUIRED: '+name)
        if record['final_outside_selection_changed_pixels'] != 0 or record['natural_quality_accepted']:
            raise ValueError('ROSE_SELECTION_OR_QUALITY_SCOPE_CHANGED: '+name)
    skill_receipt = json.loads(skills.read_bytes())
    mapping = json.loads((ROOT/'video-cut-install-manifest.json').read_bytes())
    if skill_receipt['skill_count'] != 14 or mapping['current_audit']['record_sha256'] != sha(skills):
        raise ValueError('ROSE_CURRENT_SKILL_REGISTRATION_REQUIRED')
    for row in skill_receipt['results']:
        skill = row['skill']
        if row['validator_exit_code'] or not row['installed_directory_resolves_to_repo']:
            raise ValueError('ROSE_SKILL_REGISTRATION_FAILED: '+skill)
        local = ROOT/'skills'/skill/'SKILL.md'
        installed = Path('C:/Users/carzy/.codex/skills')/skill
        if sha(local) != row['sha256'] or installed.resolve() != local.parent.resolve():
            raise ValueError('ROSE_SKILL_CURRENT_BYTES_CHANGED: '+skill)
        if next(value for value in mapping['skills'] if value['name'] == skill)['skill_md_sha256'] != row['sha256'][7:]:
            raise ValueError('ROSE_SKILL_MANIFEST_CHANGED: '+skill)
    report = 'docs/validation/ROSE本地对象移除与原始全画面输出实测_2026-10-19.md'
    names = ['README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md', report,
        'docs/validation/ROSE本地模型获取与离线预检_2026-10-19.md',
        'docs/specs/ROSE离线对象移除与副作用核验契约_v0.1_2026-10-19.md',
        'docs/third-party/ROSE原生研究依赖与来源说明_2026-10-19.md',
        'docs/third-party/时序修复候选源码与许可说明_2026-10-18.md',
        'docs/OpenFilm复用复核与开发成本更新_2026-10-19.md']
    links = []
    gate = '通过' if receipt['public']['controlled_quality_passed'] else '未通过'
    score = f"{receipt['public']['rose_scores'][-1]['masked_psnr_db']:.6f}"
    for name in names:
        path = ROOT/name
        text = path.read_text(encoding='utf-8')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            if not (path.parent/urllib.parse.unquote(target)).resolve().exists():
                raise ValueError('ROSE_DOCUMENT_LINK_MISSING: '+name+' '+raw)
            links.append({'document': name, 'target': raw})
        if '<!-- V59-RESEARCH -->' in text:
            current = text.split('<!-- V59-RESEARCH -->', 1)[1].split('<!-- /V59-RESEARCH -->', 1)[0]
            if '各 32 帧@8 fps、50 步' not in current or score not in current or 'V58 1357/1357' not in current:
                raise ValueError('ROSE_CURRENT_DOCUMENT_SCOPE_STALE: '+name)
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    if [int(x) for x in re.findall(r'^\| V(\d{2}) \|', readme, re.M)] != list(range(1, 60)):
        raise ValueError('ROSE_README_VERIFICATION_SEQUENCE_CHANGED')
    if '| V59 | ROSE 离线对象移除研究 |' not in readme or 'V59-DEMO' not in readme:
        raise ValueError('ROSE_README_REAL_RESULT_MISSING')
    if f'门槛{gate}' not in readme or 'rose-native-20261019-v59/comparison.gif' not in readme:
        raise ValueError('ROSE_README_GATE_OR_ACTUAL_GIF_MISSING')
    matrix = (ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md').read_text(encoding='utf-8')
    if '| ROSE 离线修复候选（V59 研究） |' not in matrix or '| ROSE 候选预检（V59 研究） |' in matrix:
        raise ValueError('ROSE_MATRIX_CURRENT_STATUS_STALE')
    upstream = json.loads((ROOT/'docs/validation/evidence/openfilm-reuse-final-20261019-r05/verification.json').read_bytes())
    if upstream['totals'] != {'tests': 64, 'pass': 63, 'fail': 0, 'skipped': 1}:
        raise ValueError('ROSE_OPENFILM_HISTORICAL_RESEARCH_CHANGED')
    sources = [*sorted((ROOT/'scripts').glob('*rose*.py')), ROOT/'research/temporal-neural/rose_worker.py']
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    if frozen() != before:
        raise ValueError('ROSE_PRODUCTION_CHANGED_DURING_RELEASE_AUDIT')
    result = {'status': 'passed_actual_research_release_audit_quality_separate',
        'research_version': 'V59', 'current_product_regression': 'V58 1357/1357',
        'production_files_frozen': 186, 'full_product_regression_rerun': False,
        'research_actual_cases': 2, 'model_calls_by_case': expected_calls,
        'controlled_quality_passed': receipt['public']['controlled_quality_passed'],
        'natural_quality_accepted': False, 'full_capcut_parity_accepted': False,
        'global_gpu_admission_accepted': False,
        'product_integrated': False, 'natural_pixels_published': False,
        'skill_count': 14, 'skill_local_links_checked': skill_receipt['local_links_checked'],
        'document_local_links_checked': len(links), 'documents': {name: sha(ROOT/name) for name in names},
        'publication_receipt_sha256': sha(evidence/'verification.json'),
        'independent_receipt_sha256': sha(independent/'verification.json'),
        'skills_receipt_sha256': sha(skills), 'install_manifest_sha256': sha(ROOT/'video-cut-install-manifest.json'),
        'openfilm_selected_pass': 63, 'openfilm_selected_skip': 1, 'code_ast_files': len(sources),
        'historical_document_overwrite_guard': True, 'guard_receipt_sha256': sha(guard_dir/'verification.json'),
        'agent_static_contacts_reviewed': 2, 'static_review_receipt_sha256': sha(static_path),
        'research_sources': {path.relative_to(ROOT).as_posix(): sha(path) for path in sources},
        'network': 'disabled', 'blocked_network_events': events, 'model_calls_during_release_audit': 0,
        'generator_sha256': sha(Path(__file__))}
    save(output, result)
    print(json.dumps({key: result[key] for key in ('status', 'document_local_links_checked',
        'code_ast_files', 'controlled_quality_passed', 'production_files_frozen')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--skills', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output.resolve(), args.skills.resolve())
