"""Verify the delivered V59 loading scope, historical baselines, docs and Skill registration."""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path
import re
import shutil
import sys
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save
from run_rose_research import scores
from smoke_fragments import frozen


def audit(output):
    import numpy as np
    assert not output.exists()
    folder = ROOT/'docs/validation/evidence/rose-preflight-collection-20261019-v59'
    receipt = json.loads((folder/'verification.json').read_bytes())
    assert receipt['status'] == 'strict_local_loading_verified_inference_pending'
    assert receipt['model_forward_calls'] == 0 and not receipt['quality_scores_available']
    assert not receipt['product_integrated'] and not receipt['full_product_regression_rerun']
    assert receipt['production_files_frozen'] == 186 and receipt['production_sha256'] == frozen()
    for row in receipt['files']:
        path = ROOT/row['path']
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes'], row['path']
    assert sha(ROOT/'scripts/collect_rose_preflight.py') == sha(folder/'executed-collector.py') == receipt['generator_sha256']
    native = json.loads((folder/'native-verification.json').read_bytes())
    assert native['status'] == 'preflight_passed_no_inference' and native['model_forwards'] == 0
    assert not native['blocked_network_events'] and len(native['all_checkpoint_loading']) == 2
    assert native['parameter_counts'] == {'T5': 5680910336, 'ROSE': 1564428608, 'VAE': 126892531}
    assert native['vae_loading']['tensors'] == 194
    assert [r['tensor_count'] for r in native['all_checkpoint_loading']] == [242, 983]
    acquired = json.loads((folder/'acquisition-verification.json').read_bytes())
    assert acquired['bytes'] == 15019977880 and acquired['file_count'] == 13
    assert not acquired['clip_checkpoint_acquired'] and not acquired['base_transformer_acquired']
    assert acquired['model_inference_calls'] == 0
    for row in acquired['files']:
        # Strict inspection already re-read the entire checkpoint SHA; this
        # document audit binds that evidence and checks current file lengths.
        assert Path(row['path']).stat().st_size == row['bytes']
    prep = json.loads((folder/'source-preparation.json').read_bytes())
    assert len(prep['original_files']) == len(prep['prepared_files']) == 12
    for row in prep['prepared_files']:
        assert sha(Path(row['path'])) == row['sha256']
    from hashlib import sha256
    with zipfile.ZipFile(folder/'pinned-original-core.zip') as archive:
        assert set(archive.namelist()) == {r['path'] for r in prep['original_files']}
        for row in prep['original_files']:
            assert 'sha256:'+sha256(archive.read(row['path'])).hexdigest() == row['sha256']
    # Recompute the historical same-case baselines with the new independent
    # integer row scorer. These are zero new FGT/LaMa/ROSE model forwards.
    work = ROOT/'product/.runtime/rose-public-r2-20261019-v59'
    truth = np.load(work/'independent-truth.npy', allow_pickle=False)
    selection = np.load(work/'effective-selection.npy', allow_pickle=False)
    case = json.loads((work/'case.json').read_bytes())
    baselines = {}
    for label in ('fgt', 'lama'):
        rows = scores(np.load(work/(label+'.npy'), allow_pickle=False), truth, selection)
        for actual, expected in zip(rows, case[label+'_reference_scores']):
            for key in ('masked_psnr_db', 'known_motion_residual_mae_rgb'):
                assert abs(actual[key]-expected[key]) < 1e-10
        baselines[label] = rows
    save(folder/'independent-historical-baselines.json', baselines)
    source_failure = ROOT/'product/.runtime/rose-source-r1-20261019-v59/executed-preparer.py'
    shutil.copyfile(source_failure, folder/'initial-source-preparer.py')
    errors = {'source_preparation': {'exception': 'ValueError: ROSE_SOURCE_INCOMPLETE',
        'reason': 'initial whitelist requested README.md absent from prior selected-source receipt',
        'record_kind': 'tool stderr transcribed into structured development record, not a saved raw stderr file',
        'executed_source_sha256': sha(source_failure), 'model_forward_calls': 0},
        'wrong_interpreter_preflight': json.loads((ROOT/'docs/validation/evidence/rose-preflight-r1-20261019-v59/verification.json').read_bytes())}
    assert errors['wrong_interpreter_preflight']['status'] == 'failed'
    assert 'accelerate' in errors['wrong_interpreter_preflight']['error']
    save(folder/'development-errors.json', errors)
    skills_path = folder/'skills.json'
    skills = json.loads(skills_path.read_bytes())
    mapping = json.loads((ROOT/'video-cut-install-manifest.json').read_bytes())
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 207
    assert mapping['current_audit']['record_sha256'] == sha(skills_path)
    for row in skills['results']:
        name = row['skill']
        assert row['validator_exit_code'] == 0 and row['installed_directory_resolves_to_repo']
        assert sha(ROOT/'skills'/name/'SKILL.md') == row['sha256']
        assert (Path('C:/Users/carzy/.codex/skills')/name).resolve() == (ROOT/'skills'/name).resolve()
        assert next(x for x in mapping['skills'] if x['name'] == name)['skill_md_sha256'] == row['sha256'][7:]
    report = 'docs/validation/ROSE本地模型获取与离线预检_2026-10-19.md'
    names = ['README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md', report,
        'docs/specs/ROSE离线对象移除与副作用核验契约_v0.1_2026-10-19.md',
        'docs/third-party/ROSE原生研究依赖与来源说明_2026-10-19.md',
        'docs/third-party/时序修复候选源码与许可说明_2026-10-18.md',
        'docs/OpenFilm复用复核与开发成本更新_2026-10-19.md']
    links = []
    for name in names:
        path = ROOT/name
        text = path.read_text(encoding='utf-8')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            assert (path.parent/urllib.parse.unquote(target)).resolve().exists(), (name, raw)
            links.append({'document': name, 'target': raw})
        if '<!-- V59-RESEARCH -->' in text:
            current = text.split('<!-- V59-RESEARCH -->', 1)[1].split('<!-- /V59-RESEARCH -->', 1)[0]
            assert '0 次模型前向' in current and 'V58 1357/1357' in current
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    assert [int(x) for x in re.findall(r'^\| V(\d{2}) \|', readme, re.M)] == list(range(1, 60))
    assert '| V59 | ROSE 获取与严格加载（研究） |' in readme
    research = ROOT/'docs/validation/evidence/openfilm-reuse-final-20261019-r05'
    upstream = json.loads((research/'verification.json').read_bytes())
    assert upstream['totals'] == {'tests': 64, 'pass': 63, 'fail': 0, 'skipped': 1}
    assert sha(research/'upstream-selected.stdout.log') == upstream['stdout_sha256']
    assert not (ROOT/'docs/assets/rose-native-20261019-v59').exists()
    sources = [*sorted((ROOT/'scripts').glob('*rose*.py')), ROOT/'research/temporal-neural/rose_worker.py']
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    result = {'status': 'passed_scoped_preflight_document_audit_inference_pending', 'model_forward_calls': 0,
        'research_components_strict_loaded': 3, 'production_files_frozen': 186, 'current_product_regression': 'V58 1357/1357',
        'full_product_regression_rerun': False, 'skill_count': 14, 'skill_local_links_checked': 207,
        'document_local_links_checked': len(links), 'documents': {name: sha(ROOT/name) for name in names},
        'collector_receipt_sha256': sha(folder/'verification.json'), 'skills_receipt_sha256': sha(skills_path),
        'historical_baseline_receipt_sha256': sha(folder/'independent-historical-baselines.json'),
        'development_errors_sha256': sha(folder/'development-errors.json'), 'no_new_rose_media': True,
        'unexecuted_research_pipeline': True, 'quality_accepted': False, 'full_capcut_parity_accepted': False,
        'openfilm_selected_pass': 63, 'openfilm_selected_skip': 1, 'code_ast_files': len(sources),
        'research_sources': {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
        'generator_sha256': sha(Path(__file__))}
    save(output, result)
    print(json.dumps({k: result[k] for k in ('status', 'document_local_links_checked', 'code_ast_files', 'model_forward_calls')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output.resolve())
