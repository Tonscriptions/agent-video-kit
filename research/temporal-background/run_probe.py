"""Reproducible local research CLI, with synthetic and real-picture holdout truth.

This produces diagnostic artifacts only. It does not register project assets,
change a timeline, run a learned model or establish publication/quality approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
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
from PIL import Image, ImageDraw
from flow_core import ALGORITHM, array_bound, run
from ai_ad_editor.media import ffmpeg_path, probe_media
from ai_ad_editor.runtime import configure_local_runtime


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def code_hashes():
    files = [*ROOT.joinpath('product/src').rglob('*.py'), *ROOT.joinpath('product/tests').glob('*.py'), *ROOT.joinpath('scripts').glob('*.py')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


def local_file(raw):
    if not isinstance(raw, str) or raw.startswith(('\\\\', '//')) or '://' in raw:
        raise ValueError('expected explicit local regular file')
    path = Path(raw)
    if path.is_symlink() or not path.is_file() or path.stat().st_size < 1:
        raise ValueError('missing, empty or symbolic input')
    return path.resolve()


def progress(stage, index, total):
    if index % 8 == 0 or index == total - 1:
        print(json.dumps({'phase': stage, 'index': index, 'total': total}), flush=True)


def grow(mask, radius):
    return np.array([cv2.dilate(frame.astype(np.uint8), np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)) != 0 for frame in mask])


def score(output, baseline, truth, selected, used):
    def mse(array, mask):
        return float(np.mean((array[:, :, :, :3][mask].astype(np.float64) - truth[:, :, :, :3][mask].astype(np.float64)) ** 2)) if mask.any() else None
    before, after = mse(baseline, selected), mse(output, selected)
    psnr = lambda value: float(10 * np.log10(255**2 / value)) if value and value > 0 else None
    return {'selected_pixels': int(selected.sum()), 'contributed_pixels': int((used & selected).sum()),
            'observation_availability_fraction': float((used & selected).sum() / selected.sum()) if selected.any() else 0.,
            'masked_mse_before': before, 'masked_mse_after': after,
            'masked_psnr_before_db': psnr(before), 'masked_psnr_after_db': psnr(after),
            'contributed_mse': mse(output, used & selected), 'availability_is_not_accuracy': True}


def contacts(folder, prefix, source, selected, baseline, result, used, indices, truth=None):
    records = []
    for start in range(0, len(indices), 7):
        group = indices[start:start + 7]
        views = 6 if truth is not None else 5
        sheet = Image.new('RGB', (256 * views, 166 * len(group)), '#20232a')
        draw = ImageDraw.Draw(sheet)
        for row, index in enumerate(group):
            panels = [('input', source[index, :, :, :3]), ('selection', np.repeat(selected[index, :, :, None], 3, axis=2).astype(np.uint8) * 255),
                      ('fallback', baseline[index, :, :, :3]), ('flow observations', result[index, :, :, :3]),
                      ('contributed', np.repeat(used[index, :, :, None], 3, axis=2).astype(np.uint8) * 255)]
            if truth is not None: panels.append(('independent truth', truth[index, :, :, :3]))
            for column, (label, pixels) in enumerate(panels):
                sheet.paste(Image.fromarray(pixels).resize((256, 144)), (column * 256, row * 166 + 22))
                draw.text((column * 256 + 4, row * 166 + 4), f'{label} / {index}', fill='white')
        path = folder / f'{prefix}-contact-{start // 7 + 1}.png'
        sheet.save(path)
        records.append({'path': str(path), 'sha256': sha(path), 'frames': group})
    return records


def synthetic(folder, budget):
    frames, height, width = 12, 96, 160
    rng = np.random.default_rng(42)
    full = cv2.GaussianBlur(rng.integers(20, 235, (height + 20, width + 50, 3), dtype=np.uint8), (5, 5), 0)
    truth_rgb = np.stack([full[4:4 + height, 2 * i:2 * i + width] for i in range(frames)])
    truth = np.concatenate([truth_rgb, np.full((frames, height, width, 1), 255, np.uint8)], axis=3)
    source = truth.copy()
    selected = np.zeros(source.shape[:3], bool)
    for i in range(frames): selected[i, 25:67, 8 + 9 * i:8 + 9 * i + 18] = True
    source[selected, :3] = [251, 1, 173]
    fallback = source.copy(); fallback[selected, :3] = 110
    result, used, report = run(source, selected, selected, fallback, min_donors=2, budget=budget, checkpoint=progress)
    metrics = score(result, fallback, truth, selected, used)
    if not used.any() or metrics['masked_mse_after'] >= metrics['masked_mse_before']:
        raise AssertionError('independent translation truth did not improve')
    path = folder / 'synthetic.npz'
    np.savez_compressed(path, source=source, selection=selected, fallback=fallback, truth=truth, output=result, contributed=used)
    return {'truth_kind': 'seeded-independent-translated-texture-before-foreground-overlay', 'seed': 42,
            'artifact': str(path), 'artifact_sha256': sha(path), 'metrics': metrics, 'report': report,
            'contacts': contacts(folder, 'synthetic', source, selected, fallback, result, used, [0, 5, 11], truth)}


def decode_inputs(paths, budget):
    source_probe = probe_media(paths['source'])
    video = source_probe['video']
    width, height = video['width'], video['height']
    stream = next(s for s in source_probe['streams'] if s.get('codec_type') == 'video')
    frames = int(stream['nb_frames'])
    if not 2 <= frames <= 65 or min(width, height) < 16 or width * height > 1_048_576 or array_bound(frames, height, width) > budget:
        raise ValueError('research batch exceeds explicit frame/raster/array budget')
    values = {}
    for name, path in paths.items():
        probe = probe_media(path)
        other = probe['video']
        if (other['width'], other['height'], other['fps']) != (width, height, video['fps']):
            raise ValueError('research input geometry/rate mismatch; no inferred resampling')
        raw = subprocess.check_output([ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-protocol_whitelist', 'file,pipe',
            '-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn', '-fps_mode', 'passthrough', '-frames:v', str(frames + 1), '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'], timeout=120)
        if len(raw) != frames * height * width * 4: raise ValueError('research input frame count mismatch')
        values[name] = np.frombuffer(raw, np.uint8).reshape(frames, height, width, 4)
    return values, source_probe


def natural(folder, values, budget, scene_cuts):
    source, fallback = values['source'], values['fallback']
    selected = grow(values['target_mask'][:, :, :, 3] > 127.5, 4)
    forbidden = grow(values['exclusion_mask'][:, :, :, 3] > 127.5, 8) | selected
    result, used, report = run(source, forbidden, selected, fallback, scene_cuts=scene_cuts, budget=budget, checkpoint=progress)
    path = folder / 'natural.npz'
    np.savez_compressed(path, output=result, contributed=used)
    indices = [i for i in [0, 4, 8, 12, 13, 16, 17, 21, 25, 26, 29, 30, 31] if i < len(source)]
    return {'artifact': str(path), 'artifact_sha256': sha(path), 'report': report,
            'observation_availability_fraction': float(used.sum() / selected.sum()) if selected.any() else 0.,
            'natural_removal_truth_available': False, 'natural_removal_psnr_reported': False,
            'target_mask_grow': 4, 'exclusion_mask_grow': 8,
            'contacts': contacts(folder, 'natural', source, selected, fallback, result, used, indices)}


def holdout(folder, values, budget, scene_cuts):
    truth = values['source']
    frames, height, width, _ = truth.shape
    if width != 512 or height != 288:
        raise ValueError('fixed holdout geometry requires the documented 512x288 fixture')
    foreground = grow(values['exclusion_mask'][:, :, :, 3] > 127.5, 8)
    wall = np.zeros(truth.shape[:3], bool); bed = wall.copy()
    for i in range(frames):
        x = 310 + (i * 3) % 65
        wall[i, 65:130, x:x + 34] = True
        x = 45 + (i * 7) % 200
        bed[i, 248:275, x:x + 35] = True
    wall &= ~foreground; bed &= ~foreground
    selected = wall | bed
    source = truth.copy(); source[selected, :3] = [251, 1, 173]
    fallback = source.copy()
    for i in range(frames):
        erased = source[i, :, :, :3].copy(); erased[selected[i]] = 0
        fallback[i, :, :, :3] = cv2.inpaint(erased, selected[i].astype(np.uint8), 5, cv2.INPAINT_TELEA)
    result, used, report = run(source, foreground | selected, selected, fallback, scene_cuts=scene_cuts, budget=budget, checkpoint=progress)
    path = folder / 'holdout.npz'
    np.savez_compressed(path, truth=truth, occluded=source, selected=selected, wall=wall, bed=bed, fallback=fallback, output=result, contributed=used)
    return {'truth_kind': 'original-real-video-pixels-before-artificial-magenta-occluder',
            'truth_is_not_human_removal_ground_truth': True, 'baseline': 'OpenCV-Telea-radius-5',
            'wall': score(result, fallback, truth, wall, used), 'bed': score(result, fallback, truth, bed, used),
            'combined': score(result, fallback, truth, selected, used), 'artifact': str(path), 'artifact_sha256': sha(path), 'report': report,
            'contacts': contacts(folder, 'holdout', source, selected, fallback, result, used, sorted(set([0, frames // 4, frames // 2, 3 * frames // 4, frames - 1])), truth)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-manifest', required=True, help='JSON with source, target_mask, exclusion_mask, fallback local video paths')
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--array-budget-mib', type=int, default=1024)
    parser.add_argument('--scene-cut-frame', type=int, action='append', default=[])
    args = parser.parse_args()
    if not 1 <= args.array_budget_mib <= 2048: raise ValueError('array-budget-mib must be 1..2048')
    manifest = local_file(args.input_manifest)
    content = json.loads(manifest.read_text(encoding='utf-8-sig'))
    paths = {name: local_file(content[name]) for name in ('source', 'target_mask', 'exclusion_mask', 'fallback')}
    folder = Path(args.output_root).resolve()
    if folder.exists() or str(folder).startswith('\\\\'): raise ValueError('output directory must be new and local')
    folder.mkdir(parents=True)
    before = code_hashes()
    research = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    inputs = {name: {'path': str(path), 'sha256': sha(path)} for name, path in paths.items()}
    input_manifest_sha = sha(manifest)
    began = time.monotonic()
    configure_local_runtime(); cv2.setNumThreads(4); cv2.setRNGSeed(0)
    tests = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-m', 'unittest', 'discover', '-s', str(Path(__file__).parent), '-p', 'test_flow_core.py', '-v'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (folder / 'tests.log').write_bytes(tests.stdout)
    if tests.returncode: raise AssertionError(tests.stdout.decode('utf-8', errors='replace'))
    budget = args.array_budget_mib * 1024**2
    controlled = synthetic(folder, budget)
    values, probe = decode_inputs(paths, budget)
    removal = natural(folder, values, budget, args.scene_cut_frame)
    held_out = holdout(folder, values, budget, args.scene_cut_frame)
    after = code_hashes()
    assert before == after
    assert research == {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    assert all(sha(paths[name]) == value['sha256'] for name, value in inputs.items()) and sha(manifest) == input_manifest_sha
    baseline = json.loads((ROOT / 'docs/validation/evidence/repair-blend-smoke-20261016.json').read_text(encoding='utf-8-sig'))
    assert before == baseline['implementation_sha256']
    ffmpeg = Path(ffmpeg_path())
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'research-completed-quality-unaccepted',
              'algorithm': ALGORITHM, 'seconds': time.monotonic() - began, 'arguments': vars(args), 'inputs': inputs,
              'manifest_sha256': input_manifest_sha, 'runtime': {'native_python': sys.executable, 'python_sha256': sha(sys.executable),
              'opencv': cv2.__version__, 'numpy': np.__version__, 'opencv_threads': cv2.getNumThreads(), 'ffmpeg': str(ffmpeg), 'ffmpeg_sha256': sha(ffmpeg),
              'network_guard_installed': True, 'blocked_network_events': EVENTS, 'model_downloads': False, 'learned_model_runs': 0,
              'docker_wsl_virtualization_started': False, 'browser_started': False}, 'independent_research_tests': {'count': 10, 'exit_code': 0, 'log_sha256': sha(folder / 'tests.log'), 'log': tests.stdout.decode('utf-8', errors='replace')},
              'synthetic': controlled, 'natural_removal': removal, 'real_picture_holdout': held_out,
              'production_source_sha256_before': before, 'production_source_sha256_after': after,
              'production_source_matches_completed_363_regression': True, 'research_source_sha256': research,
              'product_integrated': False, 'continuous_playback_reviewed': False, 'full_jianying_parity_accepted': False}
    save(folder / 'summary.json', report)
    print(json.dumps({'status': report['status'], 'seconds': report['seconds'], 'synthetic': controlled['metrics'],
                      'removal_availability': removal['observation_availability_fraction'], 'holdout_wall': held_out['wall'],
                      'holdout_bed': held_out['bed'], 'holdout_combined': held_out['combined']}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
