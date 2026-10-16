"""Offline camera/dense reference diagnostics, never a publication approval.

Requires the same four existing local video inputs as run_probe.py. Truth is
retained by the fixture/scorer and is never passed into either repair kernel.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent), str(ROOT / 'product/src')]
from ai_ad_editor.rvm_worker import install_network_guard
EVENTS = []
install_network_guard(EVENTS)
import cv2
import numpy as np
from ai_ad_editor.media import ffmpeg_path, probe_media
from ai_ad_editor.runtime import configure_local_runtime
from flow_core import run as previous_run
from reference_core import ALGORITHM, array_bound, run
from run_probe import code_hashes, contacts, decode_inputs, grow, local_file, progress, save, score, sha


def process_memory():
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ['peak_working_set', 'working_set',
             'peak_paged_pool', 'paged_pool', 'peak_nonpaged_pool', 'nonpaged_pool',
             'pagefile', 'peak_pagefile', 'private_usage']]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise OSError(ctypes.get_last_error(), 'GetProcessMemoryInfo')
    return {'peak_working_set_bytes': counters.peak_working_set,
            'peak_pagefile_bytes': counters.peak_pagefile,
            'scope': 'native-diagnostic-python-process-only-excludes-test-and-ffmpeg-children-not-system-total'}


def tests(folder):
    program = (
        'import sys,unittest,json;'
        f'sys.path[:0]=[{str(ROOT / "product/src")!r},{str(Path(__file__).parent)!r}];'
        'from ai_ad_editor.rvm_worker import install_network_guard;events=[];install_network_guard(events);'
        f'suite=unittest.defaultTestLoader.discover({str(Path(__file__).parent)!r},pattern="test_*core.py");'
        'result=unittest.TextTestRunner(verbosity=2).run(suite);'
        'print(json.dumps({"network_guard_events":events}));'
        'sys.exit(0 if result.wasSuccessful() else 1)')
    result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', program],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (folder / 'tests.log').write_bytes(result.stdout)
    text = result.stdout.decode('utf-8', errors='replace')
    count = re.search(r'Ran (\d+) tests? in ', text)
    if result.returncode or count is None:
        raise AssertionError(text)
    return {'count': int(count[1]), 'exit_code': result.returncode,
            'network_guard_installed': True, 'log_sha256': sha(folder / 'tests.log'), 'log': text}


def execute(folder, name, source, forbidden, selected, fallback, budget, *, truth=None,
            regions=None, scene_cuts=(), min_donors=3, previous=None):
    began = time.monotonic()
    output, used, report = run(source, forbidden, selected, fallback, budget=budget,
                             scene_cuts=scene_cuts, min_donors=min_donors, checkpoint=progress)
    arrays = dict(output=output, contributed=used, source=source, forbidden=forbidden,
                  selected=selected, fallback=fallback)
    result = {'seconds': time.monotonic() - began, 'report': report,
              'truth_available_for_scoring': truth is not None, 'metrics': {}}
    if truth is not None:
        arrays['truth'] = truth
        masks = {'combined': selected, **(regions or {})}
        result['metrics'] = {key: score(output, fallback, truth, mask, used) for key, mask in masks.items()}
        if previous is not None:
            prior_output, prior_used = previous
            arrays.update(previous_output=prior_output, previous_contributed=prior_used)
            result['previous_metrics'] = {key: score(prior_output, fallback, truth, mask, prior_used)
                                          for key, mask in masks.items()}
        for key, mask in masks.items():
            arrays[key + '_region'] = mask
    path = folder / (name + '.npz')
    np.savez_compressed(path, **arrays)
    indices = [i for i in [0, 4, 8, 12, 13, 16, 17, 21, 25, 26, 29, 30, 31] if i < len(source)] if name == 'natural' else sorted(set(
        [0, len(source) // 4, len(source) // 2, 3 * len(source) // 4, len(source) - 1]))
    result.update(artifact=str(path), artifact_sha256=sha(path),
                  contacts=contacts(folder, name, source, selected, fallback, output, used, indices, truth))
    print(json.dumps({'case': name, 'seconds': result['seconds'], 'metrics': result['metrics'],
                      'contributed_pixels': report['contributed_pixels'],
                      'selected_pixels': report['selected_pixels']}, ensure_ascii=False), flush=True)
    return result


def simple_translation(folder, budget):
    rng = np.random.default_rng(42)
    full = cv2.GaussianBlur(rng.integers(20, 235, (116, 210, 3), dtype=np.uint8), (5, 5), 0)
    rgb = np.stack([full[4:100, 2 * i:2 * i + 160] for i in range(12)])
    truth = np.concatenate([rgb, np.full((12, 96, 160, 1), 255, np.uint8)], axis=3)
    selected = np.zeros(truth.shape[:3], bool)
    for i in range(12):
        selected[i, 25:67, 8 + 9 * i:26 + 9 * i] = True
    source = truth.copy()
    source[selected, :3] = [251, 1, 173]
    fallback = source.copy()
    fallback[selected, :3] = 110
    previous = previous_run(source, selected, selected, fallback, min_donors=2, budget=budget)[:2]
    result = execute(folder, 'translation', source, selected, selected, fallback, budget,
                     truth=truth, min_donors=2, previous=previous)
    result['truth_kind'] = 'seed-42-independent-translated-texture-before-occlusion'
    return result


def two_surfaces(folder, budget):
    frames, height, width = 12, 160, 256
    rng = np.random.default_rng(615)
    textures = [cv2.GaussianBlur(rng.integers(20, 235, (200, 320, 3), dtype=np.uint8), (5, 5), 0)
                for _ in range(2)]
    y, x = np.indices((height, width), dtype=np.float32)
    rgb = []
    for index in range(frames):
        top = _sample(textures[0], x + 28 + 2 * index, y + 8)
        bottom = _sample(textures[1], x + 28 - index,
                         y + 8 + 2 * np.sin(x / 25 + index * .6))
        rgb.append(np.where((y < 80)[:, :, None], top, bottom))
    truth = np.concatenate([np.stack(rgb), np.full((frames, height, width, 1), 255, np.uint8)], axis=3)
    upper = np.zeros(truth.shape[:3], bool)
    lower = upper.copy()
    for i in range(frames):
        upper[i, 25:65, 16 + 12 * i:36 + 12 * i] = True
        lower[i, 108:140, 120 - 7 * i:144 - 7 * i] = True
    selected = upper | lower
    source, fallback = truth.copy(), truth.copy()
    source[selected, :3] = [251, 1, 173]
    for i in range(frames):
        erased = source[i, :, :, :3].copy()
        erased[selected[i]] = 0
        fallback[i, :, :, :3] = cv2.inpaint(erased, selected[i].astype(np.uint8), 5, cv2.INPAINT_TELEA)
    previous = previous_run(source, selected, selected, fallback, budget=budget)[:2]
    result = execute(folder, 'two-surfaces', source, selected, selected, fallback, budget,
                     truth=truth, regions={'rigid': upper, 'deforming': lower}, previous=previous)
    result.update(truth_kind='seed-615-independent-two-textures-before-occlusion',
                  geometry='upper-2px-per-frame-translation;lower-opposite-translation-and-sinusoidal-deformation')
    return result


def _sample(texture, x, y):
    return cv2.remap(texture, x, y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def real_holdout(folder, values, budget, cuts, prior):
    truth = values['source']
    frames, height, width, _ = truth.shape
    if (width, height) != (512, 288):
        raise ValueError('fixed real holdout profile requires 512x288')
    foreground = grow(values['exclusion_mask'][:, :, :, 3] > 127.5, 8)
    wall = np.zeros(truth.shape[:3], bool)
    bed = wall.copy()
    for i in range(frames):
        x = 310 + (i * 3) % 65
        wall[i, 65:130, x:x + 34] = True
        x = 45 + (i * 7) % 200
        bed[i, 248:275, x:x + 35] = True
    wall &= ~foreground
    bed &= ~foreground
    selected = wall | bed
    source = truth.copy()
    source[selected, :3] = [251, 1, 173]
    fallback = source.copy()
    for i in range(frames):
        erased = source[i, :, :, :3].copy()
        erased[selected[i]] = 0
        fallback[i, :, :, :3] = cv2.inpaint(erased, selected[i].astype(np.uint8), 5, cv2.INPAINT_TELEA)
    previous = None
    if prior:
        artifact = local_file(prior['real_picture_holdout']['artifact'])
        if sha(artifact) != prior['real_picture_holdout']['artifact_sha256']:
            raise ValueError('previous holdout artifact digest mismatch')
        with np.load(artifact, allow_pickle=False) as saved:
            for key, value in [('truth', truth), ('occluded', source), ('selected', selected), ('fallback', fallback)]:
                if not np.array_equal(saved[key], value):
                    raise ValueError('previous holdout comparison input mismatch: ' + key)
            previous = saved['output'].copy(), saved['contributed'].copy()
    result = execute(folder, 'holdout', source, foreground | selected, selected, fallback, budget,
                     truth=truth, regions={'wall': wall, 'bed': bed}, scene_cuts=cuts, previous=previous)
    result.update(truth_kind='real-video-pixels-before-artificial-magenta-occlusion',
                  truth_is_not_human_removal_ground_truth=True, baseline='OpenCV-Telea-radius-5')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-manifest', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--array-budget-mib', type=int, default=1536)
    parser.add_argument('--scene-cut-frame', action='append', type=int, default=[])
    parser.add_argument('--compare-evidence', help='optional prior local JSON; requires its bound artifact files')
    args = parser.parse_args()
    if not 1 <= args.array_budget_mib <= 2048:
        raise ValueError('array-budget-mib must be 1..2048')
    manifest = local_file(args.input_manifest)
    paths = {k: local_file(v) for k, v in json.loads(manifest.read_text(encoding='utf-8-sig')).items()
             if k in {'source', 'target_mask', 'exclusion_mask', 'fallback'}}
    if set(paths) != {'source', 'target_mask', 'exclusion_mask', 'fallback'}:
        raise ValueError('four explicit local inputs required')
    folder = Path(args.output_root).resolve()
    if folder.exists() or str(folder).startswith('\\\\') or '://' in args.output_root:
        raise ValueError('output directory must be new and local')
    budget = args.array_budget_mib * 1024**2
    configure_local_runtime()
    probe = probe_media(paths['source'])
    stream = next(s for s in probe['streams'] if s.get('codec_type') == 'video')
    if array_bound(int(stream['nb_frames']), probe['video']['height'], probe['video']['width']) > budget:
        raise ValueError('reference array budget exceeded before input decode')
    folder.mkdir(parents=True)
    production = code_hashes()
    baseline = json.loads((ROOT / 'docs/validation/evidence/repair-blend-smoke-20261016.json').read_text(encoding='utf-8-sig'))
    if production != baseline['implementation_sha256']:
        raise ValueError('production source no longer matches completed 363 regression')
    research = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    inputs = {name: {'path': str(path), 'sha256': sha(path)} for name, path in paths.items()}
    manifest_sha = sha(manifest)
    prior = None
    if args.compare_evidence:
        prior_path = local_file(args.compare_evidence)
        prior = json.loads(prior_path.read_text(encoding='utf-8-sig'))
        if any(prior['inputs'][name]['sha256'] != record['sha256'] for name, record in inputs.items()):
            raise ValueError('prior evidence input digest mismatch')
        if sorted(prior['arguments'].get('scene_cut_frame', [])) != sorted(args.scene_cut_frame):
            raise ValueError('prior evidence scene-cut configuration mismatch')
    began = time.monotonic()
    checked_tests = tests(folder)
    cv2.setNumThreads(4)
    cv2.setRNGSeed(0)
    translation = simple_translation(folder, budget)
    surfaces = two_surfaces(folder, budget)
    values, _ = decode_inputs(paths, budget)
    held_out = real_holdout(folder, values, budget, args.scene_cut_frame, prior)
    selected = grow(values['target_mask'][:, :, :, 3] > 127.5, 4)
    forbidden = grow(values['exclusion_mask'][:, :, :, 3] > 127.5, 8) | selected
    removal = execute(folder, 'natural', values['source'], forbidden, selected,
                      values['fallback'], budget, scene_cuts=args.scene_cut_frame)
    removal['natural_removal_truth_available'] = False
    after = code_hashes()
    if production != after or research != {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}:
        raise ValueError('source changed during diagnostic')
    if any(sha(paths[name]) != record['sha256'] for name, record in inputs.items()) or sha(manifest) != manifest_sha:
        raise ValueError('input changed during diagnostic')
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'algorithm': ALGORITHM,
              'status': 'research-completed-quality-unaccepted', 'seconds': time.monotonic() - began,
              'arguments': vars(args), 'inputs': inputs, 'manifest_sha256': manifest_sha,
              'prior_evidence_sha256': sha(prior_path) if prior else None,
              'runtime': {'python': sys.executable, 'python_sha256': sha(sys.executable),
                          'opencv': cv2.__version__, 'numpy': np.__version__, 'opencv_threads': cv2.getNumThreads(),
                          'ffmpeg': ffmpeg_path(), 'ffmpeg_sha256': sha(ffmpeg_path()),
                          'network_guard_installed': True, 'blocked_network_events': EVENTS,
                          'learned_model_runs': 0, 'model_downloads': False,
                          'docker_wsl_virtualization_started': False, 'browser_started': False,
                          'memory': process_memory()},
              'independent_research_tests': checked_tests, 'translation': translation,
              'two_surfaces': surfaces, 'real_picture_holdout': held_out, 'natural_removal': removal,
              'production_source_sha256_before': production, 'production_source_sha256_after': after,
              'production_source_matches_completed_363_regression': True, 'full_product_regression_rerun': False,
              'research_source_sha256': research, 'product_integrated': False,
              'continuous_playback_reviewed': False, 'natural_removal_quality_accepted': False,
              'full_jianying_parity_accepted': False}
    save(folder / 'summary.json', report)
    print(json.dumps({'status': report['status'], 'seconds': report['seconds'],
                      'research_tests': checked_tests['count'], 'runtime_memory': report['runtime']['memory']}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
