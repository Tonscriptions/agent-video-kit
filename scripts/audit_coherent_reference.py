"""Independently audit an unsuccessful repair experiment; never accept natural quality."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'product/src')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.rvm_worker import install_network_guard
EVENTS = []
install_network_guard(EVENTS)
import cv2
import numpy as np
from PIL import Image
from ai_ad_editor.media import ffmpeg_path, ffprobe_path


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def independently_score(output, truth, mask):
    difference = output[..., :3].astype(np.int16) - truth[..., :3].astype(np.int16)
    values = difference[mask].astype(np.float64)
    squared_error = float(np.sum(values * values) / values.size)
    absolute_delta = 0.0
    delta_values = 0
    for index in range(1, len(output)):
        overlap = mask[index] & mask[index - 1]
        delta = (difference[index][overlap].astype(np.int32)
                 - difference[index - 1][overlap].astype(np.int32))
        absolute_delta += float(np.abs(delta).sum())
        delta_values += delta.size
    return {'selected_pixels': int(mask.sum()), 'mse': squared_error,
            'psnr_db': 10 * math.log10(255 * 255 / squared_error) if squared_error else None,
            'same_canvas_error_delta_mae': absolute_delta / delta_values if delta_values else None,
            'same_canvas_error_delta_values': delta_values}


def true_backward_map(name, index, height, width):
    """Analytic fixture geometry, used ONLY by this post-hoc diagnostic scorer."""
    y, x = np.indices((height, width), dtype=np.float32)
    previous_x, previous_y = x.copy(), y.copy()
    if name == 'translation':
        previous_x += 2
    elif name == 'two_surfaces':
        previous_x = np.where(y < 80, x + 2, x - 1)
        previous_y = np.where(y < 80, y, y + 2 * (
            np.sin(x / 25 + index * .6) - np.sin((x - 1) / 25 + (index - 1) * .6)))
    elif name == 'two_motion_cut':
        previous_x = np.where(y < 48, x + 1.5, x - 1)
        previous_y = np.where(y < 48, y, y + .3)
    elif name == 'elastic_exposure':
        target_u = x + 24 + 1.2 * index + 2 * np.sin(y / 15 + .25 * index)
        target_v = y + 16 + .3 * index + np.sin(x / 17 + .4 * index)
        previous_x += 1.2
        previous_y += .3
        prior = index - 1
        for _ in range(8):
            u = previous_x + 24 + 1.2 * prior + 2 * np.sin(previous_y / 15 + .25 * prior)
            v = previous_y + 16 + .3 * prior + np.sin(previous_x / 17 + .4 * prior)
            du, dv = u - target_u, v - target_v
            a = (2 / 15) * np.cos(previous_y / 15 + .25 * prior)
            b = (1 / 17) * np.cos(previous_x / 17 + .4 * prior)
            determinant = 1 - a * b
            previous_x -= (du - a * dv) / determinant
            previous_y -= (dv - b * du) / determinant
        error_u = previous_x + 24 + 1.2 * prior + 2 * np.sin(previous_y / 15 + .25 * prior) - target_u
        error_v = previous_y + 16 + .3 * prior + np.sin(previous_x / 17 + .4 * prior) - target_v
        assert float(np.max(np.abs(error_u))) < 1e-4
        assert float(np.max(np.abs(error_v))) < 1e-4
    else:
        assert name == 'stationary', name
    return previous_x.astype(np.float32), previous_y.astype(np.float32)


def motion_compensated_diagnostic(name, output, truth, mask, cuts):
    """Error stability along known background paths, not raw-video flicker or perception."""
    error = output[..., :3].astype(np.float32) - truth[..., :3].astype(np.float32)
    absolute_sum = squared_sum = 0.0
    count = pairs = 0
    for index in range(1, len(output)):
        if index in cuts:
            continue
        h, w = mask.shape[1:]
        px, py = true_backward_map(name, index, h, w)
        inside = (px >= 0) & (py >= 0) & (px <= w - 1) & (py <= h - 1)
        # Require all four mathematical bilinear corners in the previous region.
        x0, y0 = np.floor(px).astype(np.int32), np.floor(py).astype(np.int32)
        x0, y0 = np.clip(x0, 0, w - 1), np.clip(y0, 0, h - 1)
        x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
        old = mask[index - 1]
        valid = mask[index] & inside & old[y0, x0] & old[y0, x1] & old[y1, x0] & old[y1, x1]
        warped = cv2.remap(error[index - 1], px, py, cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        delta = (error[index][valid] - warped[valid]).astype(np.float64)
        absolute_sum += float(np.abs(delta).sum())
        squared_sum += float(np.square(delta).sum())
        count += delta.size
        pairs += int(bool(delta.size))
    return {'mae': absolute_sum / count if count else None,
            'mse': squared_sum / count if count else None, 'channel_values': count,
            'frame_pairs': pairs, 'skipped_cut_frames': list(cuts),
            'geometry': 'analytic fixture backward map; OpenCV INTER_LINEAR error sampling',
            'perceptual_or_natural_quality_gate': False,
            'declared_after_candidate_measurement_not_primary_acceptance_gate': True}


def read_arrays(path, expected_sha):
    assert sha(path) == expected_sha, path
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def verify_cases(record):
    result = {}
    for name, case in record['cases'].items():
        arrays = read_arrays(Path(case['artifact']), case['artifact_sha256'])
        original = read_arrays(Path(case['input_npz']), case['input_sha256'])
        for key in ('source', 'forbidden', 'selected', 'fallback'):
            assert np.array_equal(original[key], arrays[key]), (name, key)
        source, selected, baseline, output = [arrays[key] for key in ('source', 'selected', 'baseline', 'output')]
        assert np.array_equal(output[~selected], source[~selected]), name
        assert np.array_equal(output[..., 3], source[..., 3]), name
        assert np.array_equal(baseline[~selected], source[~selected]), name
        assert np.array_equal(baseline[..., 3], source[..., 3]), name
        regions = {'combined': selected, **{key[:-7]: value for key, value in arrays.items()
                                           if key.endswith('_region') and np.any(value & selected)}}
        metrics = {}
        if 'truth' in arrays:
            for key, mask in regions.items():
                before = independently_score(baseline, arrays['truth'], mask)
                now = independently_score(output, arrays['truth'], mask)
                old = case['metrics'][key]
                for actual, reported in ((before, old['baseline']), (now, old['candidate'])):
                    for field, value in actual.items():
                        assert ((value is None and reported[field] is None) or
                                math.isclose(value, reported[field], rel_tol=1e-12, abs_tol=1e-12)), (name, key, field)
                gate = all(now[k] is not None and before[k] is not None and now[k] <= before[k]
                           for k in ('mse', 'same_canvas_error_delta_mae'))
                assert gate == old['strict_paired_gate_passed']
                metrics[key] = {'baseline': before, 'candidate': now, 'strict_paired_gate_passed': gate}
                if name in {'translation', 'two_surfaces', 'stationary', 'two_motion_cut', 'elastic_exposure'}:
                    cuts = case['candidate_report']['scene_cuts']
                    metrics[key]['motion_compensated_error_diagnostic'] = {
                        'baseline': motion_compensated_diagnostic(name, baseline, arrays['truth'], mask, cuts),
                        'candidate': motion_compensated_diagnostic(name, output, arrays['truth'], mask, cuts)}
        assert bool(metrics) == bool(case['metrics']), name
        result[name] = {'metrics': metrics, 'frames': len(source), 'width': source.shape[2], 'height': source.shape[1],
            'changed_candidate_rgb_pixels': int(np.any(output[..., :3] != baseline[..., :3], axis=3).sum()),
            'reference_rgba_equal': np.array_equal(output, baseline),
            'outside_mask_rgba_exact': True, 'all_alpha_exact': True,
            'fresh_holdout': case.get('fresh_holdout', False), 'truth_available': 'truth' in arrays,
            'candidate_seconds': case['candidate_seconds']}
    return result


def run(args):
    final = load(args.final)
    development = load(args.development)
    assert final['status'] == development['status'] == 'completed'
    for record in (final, development):
        assert record['production_before'] == record['production_after']
        assert record['research_before'] == record['research_after']
        tests = record['research_tests']
        log = Path(record is final and args.final or args.development).parent / 'research-tests.log'
        assert sha(log) == tests['log_sha256']
        text = log.read_text('utf-8')
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
        assert match and int(match[1]) == tests['methods'] and tests['exit_code'] == tests['skipped'] == 0
        assert re.search(r'\nOK\s*\n', text)
        assert '"network_guard_events": []' in text
    assert final['research_tests']['methods'] == 41 and development['research_tests']['methods'] == 35
    prior = load(ROOT / 'docs/validation/evidence/html-motion-20261018.json')
    assert prior['full']['methods'] == 975
    assert final['production_after'] == prior['full']['frozen_after']
    assert len(final['production_after']) == 137
    for key, expected in final['production_after'].items():
        assert sha(ROOT / key) == expected, key
    for key, expected in final['research_after'].items():
        assert sha(ROOT / key) == expected, key
    holdouts = final['fresh_holdout_manifest']
    assert sha(Path(holdouts['path'])) == holdouts['sha256']
    assert sha(ROOT / holdouts['record']['generator']) == holdouts['record']['generator_sha256']
    for name, case in holdouts['record']['cases'].items():
        assert sha(Path(case['path'])) == case['sha256']
        assert final['cases'][name]['fresh_holdout']
    final_cases = verify_cases(final)
    development_cases = verify_cases(development)
    scored = [v for c in final_cases.values() for v in c['metrics'].values()]
    all_passed = all(v['strict_paired_gate_passed'] for v in scored)
    assert all_passed == final['strict_all_scored_regions_passed'] == False
    fresh_gain = sum(v['candidate']['mse'] < v['baseline']['mse']
                     for c in final_cases.values() if c['fresh_holdout'] for v in c['metrics'].values())
    assert fresh_gain == final['fresh_holdout_strict_mse_gain_regions'] == 0
    assert not final['numerical_improvement_supported_on_fresh_holdout']
    assert not final['product_integrated'] and not final['natural_removal_quality_accepted']

    dev_zip = args.development.parent / 'source-frozen.zip'
    with zipfile.ZipFile(dev_zip) as archive:
        assert archive.testzip() is None and set(archive.namelist()) == set(development['research_before'])
        for name, expected in development['research_before'].items():
            assert digest(archive.read(name)) == expected
    revision = ROOT / 'product/.runtime/coherent-reference-revision-20261018'
    with zipfile.ZipFile(revision / 'revision-v2-frozen.zip') as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 4
        quick = json.loads(archive.read('quick-comparison.json'))
        assert digest(archive.read('coherent_reference.py')) == quick['candidate_sha256']
        assert archive.read('quick-comparison.json') == (revision / 'quick-comparison.json').read_bytes()
    assert load(revision / 'quick-comparison-v3.json')['candidate_sha256'] == sha(ROOT / 'research/temporal-background/coherent_reference.py')

    gallery = ROOT / 'docs/assets/coherent-reference-20261018'
    media = load(gallery / 'verification.json')
    assert sha(ROOT / media['generator']) == media['generator_sha256']
    assert not media['product_integrated'] and not media['natural_media_published']
    assert media['network_guard_events'] == []
    assert set(media['cases']) == {'two_surfaces', 'two_motion_cut', 'elastic_exposure'}
    for name, item in media['files'].items():
        assert sha(gallery / name) == item['sha256'], name
    for name in media['cases']:
        case = final['cases'][name]
        arrays = read_arrays(Path(case['artifact']), case['artifact_sha256'])
        with np.load(gallery / (name + '.npz'), allow_pickle=False) as public:
            for key in ('source', 'forbidden', 'selected', 'fallback', 'truth', 'baseline', 'output', 'contributed'):
                assert np.array_equal(public[key], arrays[key]), (name, key)
        with Image.open(gallery / (name + '-comparison.gif')) as gif:
            delays = []
            for index in range(gif.n_frames):
                gif.seek(index)
                delays.append(gif.info['duration'])
            assert gif.n_frames == 12 and sum(delays) == 1000
        result = subprocess.run([ffmpeg_path(), '-v', 'error', '-i', str(gallery / (name + '-candidate.nut')),
                '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], capture_output=True, timeout=60)
        assert result.returncode == 0 and result.stdout == arrays['output'].tobytes(), name
    for path in sorted(gallery.iterdir()):
        if path.suffix not in {'.nut', '.mp4'}:
            continue
        result = subprocess.run([ffprobe_path(), '-v', 'error', '-show_streams', '-of', 'json', str(path)],
                                capture_output=True, timeout=60)
        assert result.returncode == 0
        streams = json.loads(result.stdout)['streams']
        assert len(streams) == 1 and streams[0]['codec_type'] == 'video'

    smoke = ROOT / 'product/.runtime/coherent-reference-cli-smoke-20261018'
    invocations = load(smoke / 'invocations.json')
    assert invocations['status'] == 'completed' and not invocations['product_cli']
    for item in invocations['invocations']:
        assert item['exit_code'] == item['expected_exit_code']
        assert sha(Path(item['log'])) == item['log_sha256']
        record = load(Path(item['verification']))
        assert record['generator_sha256'] == sha(ROOT / record['generator'])
        assert not record['truth_loaded_by_repair'] and not record['product_integrated']
        assert record['network_guard_events'] == []
    assert load(smoke / 'cancelled/verification.json')['error'] == "RuntimeError('RESEARCH_CANCELLED')"
    assert not (smoke / 'cancelled/result.npz').exists()
    case = final['cases']['elastic_exposure']
    reference = read_arrays(Path(case['artifact']), case['artifact_sha256'])
    for path in (smoke / 'public/result.npz', ROOT / 'product/.runtime/coherent-reference-cli-20261018/result.npz'):
        with np.load(path, allow_pickle=False) as data:
            assert np.array_equal(data['output'], reference['output'])
            assert np.array_equal(data['contributed'], reference['contributed'])

    # All verification above completes before creating the publishable evidence directory.
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence')
    output.mkdir(parents=True, exist_ok=False)
    support = {
        'development.json': args.development,
        'development-tests.log': args.development.parent / 'research-tests.log',
        'development-source.zip': dev_zip,
        'revision-v2-source.zip': revision / 'revision-v2-frozen.zip',
        'revision-v2-comparison.json': revision / 'quick-comparison.json',
        'revision-v3-exploration.json': revision / 'quick-comparison-v3.json',
        'final.json': args.final,
        'research-tests.log': args.final.parent / 'research-tests.log',
        'holdouts-manifest.json': Path(holdouts['path']),
        'cli-invocations.json': smoke / 'invocations.json',
        'cli-public.json': smoke / 'public/verification.json',
        'cli-public.log': smoke / 'public.log',
        'cli-cancelled.json': smoke / 'cancelled/verification.json',
        'cli-cancelled.log': smoke / 'cancelled.log',
        'cli-cancelled-exception.log': smoke / 'cancelled/exception.log',
        'cli-first.json': ROOT / 'product/.runtime/coherent-reference-cli-20261018/verification.json',
    }
    for name, path in support.items():
        (output / name).write_bytes(path.read_bytes())
    sources = {**final['research_after'], **{p: sha(ROOT / p) for p in [
        holdouts['record']['generator'], 'scripts/run_coherent_reference_fixture.py',
        'scripts/build_coherent_reference_media.py', 'scripts/audit_coherent_reference.py']}}
    with zipfile.ZipFile(output / 'final-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(sources):
            archive.writestr(path, (ROOT / path).read_bytes())
    files = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.iterdir())}
    record = {'status': 'research_completed_quality_gate_failed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator': 'scripts/audit_coherent_reference.py', 'generator_sha256': sha(Path(__file__)),
        'network_guard_events': EVENTS, 'goal_still_active': True, 'candidate_promoted': False,
        'natural_quality_accepted': False, 'complete_capcut_parity_accepted': False,
        'candidate': final['algorithm'], 'strict_all_scored_regions_passed': all_passed,
        'scored_regions': len(scored), 'failed_scored_regions': sum(not v['strict_paired_gate_passed'] for v in scored),
        'fresh_holdout_strict_mse_gain_regions': fresh_gain,
        'numerical_improvement_supported_on_fresh_holdout': False,
        'research_tests': final['research_tests'], 'development_tests_not_additive': development['research_tests'],
        'research_candidate_frames': sum(c['frames'] for c in final_cases.values()),
        'research_seconds': final['seconds'], 'process_memory': final['process_memory'],
        'final_cases': final_cases, 'development_cases': development_cases,
        'product_baseline': {'version': 'V41', 'methods': 975, 'suite_seconds': prior['full']['suite_seconds'],
            'files': len(final['production_after']), 'full_regression_rerun_this_research_round': False,
            'frozen_hashes_equal_to_prior': True, 'evidence': 'docs/validation/evidence/html-motion-20261018.json'},
        'frozen_product': final['production_after'], 'frozen_sources': sources,
        'source_archives': {'development_members': 10, 'revision_v2_members': 4, 'final_members': len(sources)},
        'public_media': {'directory': gallery.relative_to(ROOT).as_posix(), 'record_sha256': sha(gallery / 'verification.json'),
            'files': len(media['files']) + 1, 'lossless_streams': len(media['lossless_streams']),
            'every_lossless_frame_roundtrip_checked_by_generator': True,
            'independent_candidate_decode_equal_to_final_npz': True, 'natural_media_published': False,
            'continuous_playback_reviewed': False, 'listening_reviewed': False},
        'research_cli': {'successful_invocations': 2, 'preexecution_cancelled_invocations': 1,
                         'successful_rgba_and_contributed_match_paired_experiment': True, 'production_cli': False},
        'support_files': files}
    (output / 'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                                             encoding='utf-8', newline='\n')
    print(json.dumps({k: record[k] for k in ('status', 'scored_regions', 'failed_scored_regions',
        'research_candidate_frames', 'fresh_holdout_strict_mse_gain_regions')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', type=Path, required=True)
    parser.add_argument('--development', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
