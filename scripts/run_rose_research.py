"""Prepare and execute ROSE against the unchanged V44 controlled/natural cases.

The worker receives source and selection only. Truth and historical baselines
are independently scored in this parent after actual model inference finishes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save
from smoke_fragments import frozen

OPTIONS = {'steps': 50, 'guidance': 6.0, 'seed': 0, 'prompt': '', 'negative_prompt': '',
           'text_dtype': 'bfloat16', 'transformer_dtype': 'bfloat16',
           'time_embedding_dtype': 'float32', 'vae_dtype': 'float32',
           'text_gpu_budget_mib': 7168, 'text_cpu_budget_mib': 8192}
CONTRACT = ROOT/'docs/specs/ROSE离线对象移除与副作用核验契约_v0.1_2026-10-19.md'
WORKER = ROOT/'research/temporal-neural/rose_worker.py'


def offline():
    sys.path.insert(0, str(ROOT/'product/src'))
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = str(ROOT/'product/.runtime')
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    from ai_ad_editor.rvm_worker import install_network_guard
    events = []
    install_network_guard(events)
    return events


def command(args, data=None, timeout=180):
    value = subprocess.run(list(map(str, args)), input=data, capture_output=True, timeout=timeout)
    if value.returncode:
        raise RuntimeError(value.stderr.decode('utf-8', 'replace'))
    return value.stdout


def decode(path, n, h, w):
    import numpy as np
    value = command(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-an',
                     '-pix_fmt', 'rgba', '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1'])
    return np.frombuffer(value, np.uint8).reshape(n, h, w, 4).copy()


def encode(path, rgba, audio=None):
    from fractions import Fraction
    import numpy as np
    n, h, w, _ = rgba.shape
    args = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba',
            '-video_size', f'{w}x{h}', '-framerate', '8', '-i', 'pipe:0']
    if audio:
        args += ['-i', audio, '-map', '0:v:0', '-map', '1:a:0?', '-c:a', 'pcm_s16le']
    args += ['-c:v', 'qtrle', '-pix_fmt', 'argb', '-video_track_timescale', '8', '-t', str(n/8), path]
    command(args, data=rgba.tobytes())
    actual = decode(path, n, h, w)
    if not np.array_equal(actual, rgba):
        raise RuntimeError('ROSE_LOSSLESS_RGBA_ROUNDTRIP_FAILED')
    probe = json.loads(command(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_entries', 'frame=pts_time', '-of', 'json', path]))
    if [Fraction(r['pts_time']) for r in probe['frames']] != [Fraction(i, 8) for i in range(n)]:
        raise RuntimeError('ROSE_EVERY_FRAME_PTS_FAILED')


def scores(result, truth, selection):
    """Integer row sums and explicit source coordinates, independent of FGT's roll scorer."""
    import numpy as np
    error = result[:, :, :, :3].astype(np.int32)-truth[:, :, :, :3].astype(np.int32)
    n, h, w, _ = result.shape
    rows = []
    for label, low, high in [('upper', 0, 144), ('lower', 144, h), ('overall', 0, h)]:
        squared_sum = 0
        selected_pixels = 0
        residual_sum = 0
        residual_samples = 0
        for frame in range(n):
            for y in range(low, high):
                xs = np.flatnonzero(selection[frame, y])
                differences = error[frame, y, xs].astype(np.int64)
                squared_sum += int(np.sum(differences*differences))
                selected_pixels += len(xs)
                if frame == 0:
                    continue
                dx = 2 if y < 144 else -3
                previous_x = (xs-dx) % w
                both = selection[frame-1, y, previous_x]
                current = error[frame, y, xs[both]]
                previous = error[frame-1, y, previous_x[both]]
                residual_sum += int(np.sum(np.abs(current-previous), dtype=np.int64))
                residual_samples += int(both.sum())*3
        mse = squared_sum/(selected_pixels*3)
        rows.append({'region': label, 'selected_pixels': selected_pixels, 'masked_squared_error_sum': squared_sum,
            'masked_mse': mse, 'masked_psnr_db': 10*math.log10(255**2/mse) if mse else 999.,
            'known_motion_residual_abs_sum': residual_sum,
            'known_motion_residual_mae_rgb': residual_sum/residual_samples,
            'temporal_samples_rgb': residual_samples})
    return rows


def prepare(case, work):
    import numpy as np
    from PIL import Image, ImageFilter
    from run_fgt_research import public_fixture
    events = offline()
    work.mkdir(parents=True, exist_ok=False)
    save(work/'product-before.json', frozen())
    (work/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (work/'executed-worker.py').write_bytes(WORKER.read_bytes())
    record = {'case': case, 'runner_sha256': sha(Path(__file__)), 'worker_sha256': sha(WORKER),
              'contract_sha256': sha(CONTRACT), 'options': OPTIONS, 'historical_files': []}
    if case == 'public':
        source, selected, truth = public_fixture()
        directory = ROOT/'docs/assets/fgt-temporal-20261018'
        public_record = json.loads((ROOT/'docs/validation/evidence/fgt-temporal-20261018/verification.json').read_bytes())
        expected = {row['path']: row for row in public_record['public_files']}
        for name in ('source', 'truth', 'final', 'lama'):
            path = directory/(name+'-lossless.mp4')
            # Published files are already frozen by the V44 source receipt.
            key = path.relative_to(ROOT).as_posix()
            entry = expected[key]
            digest = entry['sha256'] if isinstance(entry, dict) else entry
            if sha(path) != digest:
                raise ValueError('ROSE_HISTORICAL_PUBLIC_VIDEO_CHANGED: '+name)
            frames = decode(path, 32, 240, 432)
            record['historical_files'].append({'path': str(path), 'sha256': digest})
            if name in {'source', 'truth'}:
                if not np.array_equal(frames, source if name == 'source' else truth):
                    raise ValueError('ROSE_V44_GENERATOR_OR_DECODE_MISMATCH: '+name)
            else:
                np.save(work/('fgt.npy' if name == 'final' else 'lama.npy'), frames, allow_pickle=False)
        np.save(work/'independent-truth.npy', truth, allow_pickle=False)
        record['fgt_reference_scores'] = public_record['controlled']['fgt_scores']
        record['lama_reference_scores'] = public_record['controlled']['lama_scores']
        record['audio_source'] = None
    else:
        project = ROOT/'product/.runtime/mask-edit-natural-20261018/project'
        content = json.loads((project/'project.json').read_bytes())
        assets = {row['id']: project/row['uri'] for row in content['assets']}
        source = decode(assets['source'], 32, 288, 512)
        mask = decode(assets['fixed'], 32, 288, 512)
        selected = np.stack([np.asarray(Image.fromarray(frame[:, :, 3]).filter(ImageFilter.MaxFilter(9))) > 127 for frame in mask])
        old = ROOT/'product/.runtime/fgt-natural-v1-20261018'
        if not np.array_equal(source, np.load(old/'input.npy', allow_pickle=False)) or not np.array_equal(selected, np.load(old/'effective-selection.npy', allow_pickle=False)):
            raise ValueError('ROSE_NATURAL_CASE_MUST_BE_IDENTICAL_TO_V44')
        for name in ('source', 'fixed', 'repaired'):
            record['historical_files'].append({'path': str(assets[name]), 'sha256': sha(assets[name])})
        record.update(audio_source=str(assets['source']), natural_truth_available=False,
                      new_natural_source_scenes=0)
    np.save(work/'input.npy', source, allow_pickle=False)
    np.save(work/'effective-selection.npy', selected, allow_pickle=False)
    record.update(input_sha256=sha(work/'input.npy'), selection_sha256=sha(work/'effective-selection.npy'),
                  frames=len(source), height=source.shape[1], width=source.shape[2], fps='8/1',
                  network='disabled', blocked_network_events=events, status='prepared_not_inferred')
    save(work/'case.json', record)
    return record


def run(work, prepared, bundle, acquisition):
    import numpy as np
    events = offline()
    case = json.loads((work/'case.json').read_bytes())
    if (case['runner_sha256'] != sha(Path(__file__)) or case['worker_sha256'] != sha(WORKER)
            or case['contract_sha256'] != sha(CONTRACT)):
        raise ValueError('ROSE_PREPARED_CODE_OR_CONTRACT_CHANGED_CREATE_NEW_RUN')
    before = json.loads((work/'product-before.json').read_bytes())
    if frozen() != before:
        raise ValueError('ROSE_PRODUCT_INPUTS_CHANGED_SINCE_PREPARATION')
    output = work/'output'
    output.mkdir(exist_ok=False)
    try:
        receipt = json.loads(acquisition.read_bytes())
        if receipt['status'] != 'acquired_and_verified':
            raise ValueError('ROSE_PINNED_WEIGHT_ACQUISITION_NOT_COMPLETE')
        source_receipt = json.loads((prepared/'preparation.json').read_bytes())
        rows = [{'path': row['path'], 'sha256': row['sha256']} for row in source_receipt['prepared_files']]
        rows += [{'path': row['path'], 'sha256': row['sha256']} for row in receipt['files']]
        paths = [WORKER, prepared/'compatibility.patch', prepared/'preparation.json', acquisition,
                 CONTRACT, work/'input.npy', work/'effective-selection.npy', Path(sys.executable)]
        rows += [{'path': str(path), 'sha256': sha(path)} for path in paths]
        request = {'project_root': str(ROOT), 'source_root': str(prepared/'source'), 'bundle_root': str(bundle),
                   'input_path': str(work/'input.npy'), 'selection_path': str(work/'effective-selection.npy'),
                   'output_path': str(output), 'response': str(work/'worker-response.json'),
                   'clip_reference': None, 'options': OPTIONS, 'frozen_files': rows,
                   'truth_path_provided': False, 'truth_read_allowed': False}
        save(work/'request.json', request)
        started = time.monotonic()
        print(json.dumps({'case': case['case'], 'stage': 'starting-native-offline-rose', 'steps': OPTIONS['steps']}), flush=True)
        with (work/'worker.log').open('wb') as log:
            process = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(WORKER), str(work/'request.json')],
                                     stdout=log, stderr=subprocess.STDOUT, timeout=7200, cwd=work)
        worker = json.loads((work/'worker-response.json').read_bytes())
        if process.returncode or worker['status'] != 'succeeded':
            raise RuntimeError('ROSE_WORKER_FAILED: '+worker.get('error', 'unknown'))
        source = np.load(work/'input.npy', allow_pickle=False)
        selection = np.load(work/'effective-selection.npy', allow_pickle=False)
        if sha(work/'input.npy') != case['input_sha256'] or sha(work/'effective-selection.npy') != case['selection_sha256']:
            raise RuntimeError('ROSE_PARENT_SOURCE_OR_MASK_CHANGED')
        raw = np.load(output/'raw-result.npy', allow_pickle=False)
        final = source.copy()
        final[:, :, :, :3][selection] = raw[selection]
        raw_rgba = source.copy()
        raw_rgba[:, :, :, :3] = raw
        raw_changed = int(np.count_nonzero(np.any(raw != source[:, :, :, :3], axis=3) & ~selection))
        if not np.array_equal(final[~selection], source[~selection]) or not np.array_equal(final[:, :, :, 3], source[:, :, :, 3]):
            raise RuntimeError('ROSE_FINAL_OUTSIDE_OR_ALPHA_CHANGED')
        np.save(work/'final.npy', final, allow_pickle=False)
        encode(work/'raw.mov', raw_rgba)
        encode(work/'final.mov', final, audio=case['audio_source'])
        record = {'status': 'execution_verified_quality_unaccepted', 'case': case['case'], 'worker': worker,
            'frames': len(source), 'height': source.shape[1], 'width': source.shape[2], 'fps': '8/1',
            'duration_seconds': len(source)/8, 'raw_outside_selection_changed_pixels': raw_changed,
            'final_outside_selection_changed_pixels': 0, 'original_alpha_exact': True,
            'rgba_roundtrip_exact': True, 'every_pts_exact': True, 'audio': None,
            'parent_network': 'disabled', 'parent_blocked_network_events': events,
            'product_integrated': False, 'natural_quality_accepted': False,
            'continuous_playback_reviewed': False, 'audio_listening_reviewed': False,
            'runner_sha256': sha(Path(__file__)), 'worker_sha256': sha(WORKER), 'contract_sha256': sha(CONTRACT),
            'total_seconds': time.monotonic()-started}
        if case['audio_source']:
            pcm = [command(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vn', '-ar', '48000', '-ac', '2',
                            '-t', '4', '-f', 's16le', 'pipe:1']) for path in (case['audio_source'], work/'final.mov')]
            if pcm[0] != pcm[1] or len(pcm[0]) != 768000:
                raise RuntimeError('ROSE_NATURAL_AUDIO_PCM_CHANGED')
            record['audio'] = {'exact': True, 'decoded_pcm_bytes': len(pcm[0]), 'sha256': 'sha256:'+hashlib.sha256(pcm[0]).hexdigest()}
        else:
            truth = np.load(work/'independent-truth.npy', allow_pickle=False)
            record['rose_scores'] = scores(final, truth, selection)
            for label in ('fgt', 'lama'):
                record[label+'_scores'] = scores(np.load(work/(label+'.npy'), allow_pickle=False), truth, selection)
                for actual, expected in zip(record[label+'_scores'], case[label+'_reference_scores']):
                    for key in ('masked_psnr_db', 'known_motion_residual_mae_rgb'):
                        if not math.isclose(actual[key], expected[key], rel_tol=0, abs_tol=1e-10):
                            raise RuntimeError('ROSE_INDEPENDENT_BASELINE_SCORE_MISMATCH: '+label+' '+key)
            gates = []
            for actual, baseline in zip(record['rose_scores'], record['fgt_scores']):
                gates.append({'region': actual['region'], 'psnr_at_least_30': actual['masked_psnr_db'] >= 30,
                    'psnr_no_worse_than_fgt': actual['masked_psnr_db'] >= baseline['masked_psnr_db'],
                    'motion_mae_at_most_5': actual['known_motion_residual_mae_rgb'] <= 5,
                    'motion_mae_no_worse_than_fgt': actual['known_motion_residual_mae_rgb'] <= baseline['known_motion_residual_mae_rgb']})
            record['quality_gates'] = gates
            record['controlled_quality_passed'] = all(all(v for k, v in row.items() if k != 'region') for row in gates)
        save(work/'verification.json', record)
        print(json.dumps({k: record[k] for k in ('case', 'status', 'frames', 'raw_outside_selection_changed_pixels')}, ensure_ascii=False), flush=True)
    except BaseException as error:
        save(work/'failure.json', {'status': 'failed', 'error': repr(error), 'traceback': traceback.format_exc()})
        raise
    finally:
        after = frozen()
        save(work/'product-after.json', after)
        if before != after:
            raise RuntimeError('ROSE_PRODUCT_BYTES_CHANGED_DURING_RESEARCH')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['prepare', 'run'], required=True)
    parser.add_argument('--case', choices=['public', 'natural'])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--acquisition', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        if not args.case:
            parser.error('--case is required for preparation')
        print(json.dumps(prepare(args.case, args.work.resolve()), ensure_ascii=False))
    else:
        if any(getattr(args, key) is None for key in ('prepared', 'bundle', 'acquisition')):
            parser.error('--prepared, --bundle, --acquisition are required for execution')
        run(args.work.resolve(), args.prepared.resolve(), args.bundle.resolve(), args.acquisition.resolve())
