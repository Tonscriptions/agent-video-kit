"""Offline paired repair experiment; scoring truth never enters the repairers."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/temporal-background'
sys.path[:0] = [str(ROOT / 'product/src'), str(RESEARCH)]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.rvm_worker import install_network_guard
EVENTS = []
install_network_guard(EVENTS)
import cv2
import numpy as np
import coherent_reference as candidate
from reference_core import run as baseline_run
from run_probe import contacts
from run_reference_probe import process_memory


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def frozen():
    files = [*(ROOT / 'product/src').rglob('*.py'), *(ROOT / 'product/tests').rglob('*.py'),
             *(ROOT / 'product/src').rglob('*.mjs'), ROOT / 'product/pyproject.toml',
             ROOT / 'docs/specs/agent-project.schema.json', ROOT / 'product/src/ai_ad_editor/OPENFILM_LICENSE.txt']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


def research_frozen():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in [*sorted(RESEARCH.glob('*.py')), Path(__file__)]}


def stats(output, truth, selected):
    count = int(selected.sum())
    error = output[:, :, :, :3].astype(np.float64) - truth[:, :, :, :3].astype(np.float64)
    mse = float(np.mean(error[selected] ** 2)) if count else None
    changes, values = 0., 0
    for index in range(1, len(error)):
        overlap = selected[index] & selected[index - 1]
        delta = np.abs(error[index][overlap] - error[index - 1][overlap])
        changes += float(delta.sum())
        values += delta.size
    return {'selected_pixels': count, 'mse': mse, 'exact_rgb_match': mse == 0 if count else None,
            'psnr_db': float(10 * np.log10(255 ** 2 / mse)) if mse else None,
            'same_canvas_error_delta_mae': changes / values if values else None,
            'same_canvas_error_delta_values': values,
            'temporal_metric_is_not_motion_compensated_or_perceptual': True}


def tests(work):
    program = ('import sys,unittest,json;'
        f'sys.path[:0]=[{str(ROOT / "product/src")!r},{str(RESEARCH)!r}];'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'from ai_ad_editor.rvm_worker import install_network_guard;events=[];install_network_guard(events);'
        f'suite=unittest.defaultTestLoader.discover({str(RESEARCH)!r},pattern="test_*.py");'
        'result=unittest.TextTestRunner(verbosity=2).run(suite);print(json.dumps({"network_guard_events":events}));'
        'sys.exit(0 if result.wasSuccessful() else 1)')
    command = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', program]
    began = time.monotonic()
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    (work / 'research-tests.log').write_bytes(result.stdout)
    text = result.stdout.decode('utf-8', errors='replace')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
    assert result.returncode == 0 and match and re.search(r'\bOK\s*\n', text), text[-4000:]
    return {'methods': int(match[1]), 'suite_seconds': float(match[2]), 'wall_seconds': time.monotonic() - began,
            'exit_code': result.returncode, 'skipped': len(re.findall(r'\.\.\. skipped ', text)),
            'command': command, 'log_sha256': sha(work / 'research-tests.log')}


def run(args):
    work = args.work.resolve()
    assert work.is_relative_to(ROOT / 'product/.runtime'), 'all intermediate media belongs on E under .runtime'
    work.mkdir(parents=True, exist_ok=False)
    cv2.setNumThreads(4)
    cv2.ocl.setUseOpenCL(False)
    prior_path = args.previous_evidence.resolve(strict=True)
    previous = json.loads(prior_path.read_text(encoding='utf-8-sig'))
    reused = None
    if args.paired_baseline:
        reused = json.loads(args.paired_baseline.read_text(encoding='utf-8-sig'))
        assert reused['status'] == 'completed' and reused['production_after'] == frozen()
        assert reused['runtime']['python_sha256'] == sha(Path(sys.executable))
        assert reused['runtime']['opencv'] == cv2.__version__ and reused['runtime']['numpy'] == np.__version__
        for filename in ('flow_core.py', 'camera_motion.py', 'reference_core.py'):
            name = 'research/temporal-background/' + filename
            assert reused['research_before'][name] == sha(ROOT / name), name
    cases = {name: previous[name] for name in ('translation', 'two_surfaces', 'real_picture_holdout', 'natural_removal')}
    holdouts = None
    if args.holdouts:
        holdouts = json.loads(args.holdouts.read_text(encoding='utf-8-sig'))
        assert holdouts['generator_sha256'] == sha(ROOT / holdouts['generator'])
        for name, item in holdouts['cases'].items():
            cases[name] = {'artifact': item['path'], 'artifact_sha256': item['sha256'], 'fresh_holdout': True,
                'report': {'min_distinct_donor_frames': item['min_donors'], 'scene_cuts': item['scene_cuts']}}
    start = time.monotonic()
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'algorithm': candidate.ALGORITHM, 'parameters_predeclared_before_measurement': {
            'spatial_weight': candidate.SPATIAL_WEIGHT, 'temporal_weight': candidate.TEMPORAL_WEIGHT,
            'sweeps': candidate.SWEEPS, 'cv_rng_seed': 17018, 'array_budget_bytes': 1536 * 1024**2},
        'quality_gate_predeclared': 'Every scored region must have MSE and same-canvas error-delta MAE no worse than the paired current-runtime baseline. This does not accept natural removal.',
        'previous_evidence': str(prior_path), 'previous_evidence_sha256': sha(prior_path),
        'paired_baseline_reuse': {'path': str(args.paired_baseline), 'sha256': sha(args.paired_baseline)} if reused else None,
        'fresh_holdout_manifest': {'path': str(args.holdouts), 'sha256': sha(args.holdouts), 'record': holdouts} if holdouts else None,
        'runtime': {'python': sys.executable, 'python_sha256': sha(Path(sys.executable)),
            'opencv': cv2.__version__, 'numpy': np.__version__, 'opencv_threads': cv2.getNumThreads(),
            'opencv_opencl_enabled': cv2.ocl.useOpenCL(), 'native_windows': sys.platform == 'win32',
            'network_guard_events': EVENTS, 'model_runs': 0, 'downloads': False, 'browser_or_virtualization': False},
        'production_before': frozen(), 'research_before': research_frozen(), 'cases': {}}
    save(work / 'verification.json', record)
    def progress(case, engine):
        def callback(phase, index, total):
            if phase == 'reference' and index % 8 == 0:
                event = {'case': case, 'engine': engine, 'phase': phase, 'frame': index, 'frames': total}
                print(json.dumps(event), flush=True)
                with (work / 'progress.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                    stream.write(json.dumps(event) + '\n')
        return callback
    try:
        record['research_tests'] = tests(work)
        save(work / 'verification.json', record)
        for name, old in cases.items():
            original = Path(old['artifact']).resolve(strict=True)
            assert sha(original) == old['artifact_sha256'], name
            with np.load(original, allow_pickle=False) as data:
                source, forbidden, selected, fallback = [data[key] for key in ('source', 'forbidden', 'selected', 'fallback')]
                truth = data['truth'] if 'truth' in data else None
                regions = {key[:-7]: data[key] for key in data.files if key.endswith('_region') and np.any(data[key] & selected)}
                historical = data['output'] if 'output' in data else None
            min_donors = old['report']['min_distinct_donor_frames']
            cuts = old['report']['scene_cuts']
            kwargs = {'min_donors': min_donors, 'scene_cuts': cuts, 'budget': 1536 * 1024**2}
            reuse_case = reused['cases'].get(name) if reused else None
            if reuse_case:
                base_path = Path(reuse_case['artifact']).resolve(strict=True)
                assert sha(base_path) == reuse_case['artifact_sha256']
                with np.load(base_path, allow_pickle=False) as data:
                    for key, value in zip(('source', 'forbidden', 'selected', 'fallback'), (source, forbidden, selected, fallback)):
                        assert np.array_equal(data[key], value), (name, key)
                    before, old_used = data['baseline'], data['baseline_contributed']
                baseline_report = reuse_case['paired_baseline_report']
                baseline_seconds = reuse_case['baseline_seconds']
            else:
                cv2.setRNGSeed(17018)
                began = time.monotonic()
                before, old_used, baseline_report = baseline_run(source, forbidden, selected, fallback,
                    checkpoint=progress(name, 'paired-baseline'), **kwargs)
                baseline_seconds = time.monotonic() - began
            cv2.setRNGSeed(17018)
            began = time.monotonic()
            output, used, report = candidate.run(source, forbidden, selected, fallback,
                checkpoint=progress(name, 'coherent-candidate'), **kwargs)
            candidate_seconds = time.monotonic() - began
            assert np.array_equal(output[~selected], source[~selected])
            assert np.array_equal(output[:, :, :, 3], source[:, :, :, 3])
            arrays = {'source': source, 'forbidden': forbidden, 'selected': selected, 'fallback': fallback,
                      'baseline': before, 'output': output, 'contributed': used, 'baseline_contributed': old_used}
            if truth is not None:
                arrays['truth'] = truth
            arrays.update({key + '_region': value for key, value in regions.items()})
            artifact = work / (name + '.npz')
            np.savez_compressed(artifact, **arrays)
            metrics = {}
            if truth is not None:
                for key, mask in {'combined': selected, **regions}.items():
                    base, now = stats(before, truth, mask), stats(output, truth, mask)
                    gate = all(now[field] is not None and base[field] is not None and now[field] <= base[field]
                               for field in ('mse', 'same_canvas_error_delta_mae'))
                    metrics[key] = {'baseline': base, 'candidate': now, 'strict_paired_gate_passed': gate}
            contact_name = name.replace('real_picture_', '').replace('_removal', '')
            preview = contacts(work, contact_name, source, selected, fallback, output, used,
                               sorted(set([0, len(source)//4, len(source)//2, 3*len(source)//4, len(source)-1])), truth)
            record['cases'][name] = {'input_npz': str(original), 'input_sha256': sha(original),
                'artifact': str(artifact), 'artifact_sha256': sha(artifact), 'metrics': metrics,
                'baseline_seconds': baseline_seconds, 'candidate_seconds': candidate_seconds,
                'paired_baseline_reused': bool(reuse_case), 'fresh_holdout': old.get('fresh_holdout', False),
                'historical_baseline_rgba_equal': np.array_equal(before, historical) if historical is not None else None,
                'paired_baseline_report': baseline_report, 'candidate_report': report, 'contacts': preview,
                'outside_mask_rgba_exact': True, 'all_alpha_exact': True}
            save(work / 'verification.json', record)
            print(json.dumps({'completed': name, 'candidate_seconds': candidate_seconds,
                'scores': {k: {'before_db': v['baseline']['psnr_db'], 'after_db': v['candidate']['psnr_db'],
                              'strict_gate': v['strict_paired_gate_passed']} for k,v in metrics.items()}}, ensure_ascii=False), flush=True)
        record.update(status='completed', seconds=time.monotonic() - start,
            finished_at_utc=datetime.now(timezone.utc).isoformat(), production_after=frozen(),
            research_after=research_frozen(), process_memory=process_memory(), product_integrated=False,
            natural_removal_quality_accepted=False, full_jianying_parity_accepted=False)
        assert record['production_before'] == record['production_after']
        assert record['research_before'] == record['research_after']
        record['strict_all_scored_regions_passed'] = all(value['strict_paired_gate_passed']
            for case in record['cases'].values() for value in case['metrics'].values())
        record['fresh_holdout_strict_mse_gain_regions'] = sum(
            value['candidate']['mse'] < value['baseline']['mse']
            for case in record['cases'].values() if case['fresh_holdout'] for value in case['metrics'].values())
        record['numerical_improvement_supported_on_fresh_holdout'] = bool(
            record['strict_all_scored_regions_passed'] and record['fresh_holdout_strict_mse_gain_regions'])
        save(work / 'verification.json', record)
        print(json.dumps({'status': record['status'], 'research_methods': record['research_tests']['methods'],
            'strict_all_scored_regions_passed': record['strict_all_scored_regions_passed'], 'seconds': record['seconds']}), flush=True)
    except BaseException as exc:
        record.update(status='failed', exception=repr(exc), seconds=time.monotonic()-start)
        (work / 'exception.log').write_text(traceback.format_exc(), encoding='utf-8', newline='\n')
        save(work / 'verification.json', record)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-evidence', type=Path, default=ROOT/'docs/validation/evidence/temporal-reference-selection-20261016.json')
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--paired-baseline', type=Path)
    parser.add_argument('--holdouts', type=Path)
    run(parser.parse_args())
