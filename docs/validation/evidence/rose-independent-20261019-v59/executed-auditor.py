"""Re-decode published ROSE masters and independently check actual research evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save
from run_rose_research import decode
from smoke_fragments import frozen


def audit(public, natural, assets, evidence, output):
    import numpy as np
    from run_fgt_research import scores as original_roll_scores, public_fixture
    output.mkdir(parents=True, exist_ok=False)
    (output/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
    receipt = json.loads((evidence/'verification.json').read_bytes())
    historical = json.loads((ROOT/'docs/validation/evidence/fgt-temporal-20261018/verification.json').read_bytes())
    original_scorer = ROOT/'scripts/run_fgt_research.py'
    if sha(original_scorer) != historical['controlled']['runner_sha256'] or sha(original_scorer) != historical['natural']['runner_sha256']:
        raise ValueError('ROSE_ORIGINAL_V44_SCORER_OR_FIXTURE_CHANGED')
    (output/'original-v44-scorer.py').write_bytes(original_scorer.read_bytes())
    for row in receipt['files']:
        path = ROOT/row['path']
        if sha(path) != row['sha256'] or path.stat().st_size != row['bytes']:
            raise ValueError('ROSE_PUBLISHED_ARTIFACT_CHANGED: '+row['path'])
    if receipt['production_sha256'] != frozen() or receipt['production_files_frozen'] != 186:
        raise ValueError('ROSE_FROZEN_V58_PRODUCT_CHANGED')
    review = json.loads((evidence/'public-static-review.json').read_bytes())
    if (review['status'] != 'agent_static_contact_review_completed' or review['frame_indices'] != [0, 10, 21, 31]
            or review['contact_sha256'] != sha(assets/'contact.png')
            or review['contact_generator_sha256'] != sha(evidence/'public-executed-contact-generator.py')
            or review['continuous_playback_reviewed'] or review['audio_listening_reviewed']):
        raise ValueError('ROSE_PUBLIC_STATIC_REVIEW_BINDING_FAILED')
    source, selection, truth = public_fixture()
    for name, array in [('source', source), ('truth', truth)]:
        actual = decode(assets/(name+'-lossless.mp4'), 32, 240, 432)
        if not np.array_equal(actual, array):
            raise ValueError('ROSE_PUBLISHED_ORIGINAL_NOT_EXACT: '+name)
    remeasured = {}
    delivered = {}
    for name, score_key in [('rose-selected', 'rose_scores'), ('lama', 'lama_scores'), ('fgt', 'fgt_scores')]:
        rgba = decode(assets/(name+'-lossless.mp4'), 32, 240, 432)
        # This is the unchanged V44 roll-based scorer, separate from the new
        # row-coordinate/integer-sum implementation in run_rose_research.py.
        rows = original_roll_scores(rgba, truth, selection)
        expected = receipt['public'][score_key]
        if len(rows) != len(expected):
            raise ValueError('ROSE_INDEPENDENT_DELIVERED_REGION_COUNT_MISMATCH: '+name)
        for actual, reference in zip(rows, expected):
            for key in ('region', 'selected_pixels', 'temporal_samples_rgb'):
                if actual[key] != reference[key]:
                    raise ValueError('ROSE_INDEPENDENT_DELIVERED_SAMPLE_MISMATCH: '+name+' '+key)
            for key in ('masked_psnr_db', 'known_motion_residual_mae_rgb', 'masked_mse'):
                if not math.isclose(actual[key], reference[key], rel_tol=0, abs_tol=1e-10):
                    raise ValueError('ROSE_INDEPENDENT_DELIVERED_SCORE_MISMATCH: '+name+' '+key)
        if not np.array_equal(rgba[~selection], source[~selection]) or not np.array_equal(rgba[:, :, :, 3], source[:, :, :, 3]):
            raise ValueError('ROSE_DELIVERED_OUTSIDE_OR_ALPHA_CHANGED: '+name)
        remeasured[name] = rows
        delivered[name] = {'frames': len(rgba), 'decoded_rgba_sha256': 'sha256:'+hashlib.sha256(rgba.tobytes()).hexdigest()}
    raw = decode(assets/'rose-raw-lossless.mp4', 32, 240, 432)
    raw_changes = int(np.count_nonzero(np.any(raw[:, :, :, :3] != source[:, :, :, :3], axis=3) & ~selection))
    if raw_changes != receipt['public']['raw_outside_selection_changed_pixels']:
        raise ValueError('ROSE_RAW_OUTSIDE_DIFFERENCE_UNREPORTED')
    recalculated_gates = []
    for actual, baseline in zip(remeasured['rose-selected'], remeasured['fgt']):
        recalculated_gates.append({'region': actual['region'],
            'psnr_at_least_30': actual['masked_psnr_db'] >= 30,
            'psnr_no_worse_than_fgt': actual['masked_psnr_db'] >= baseline['masked_psnr_db'],
            'motion_mae_at_most_5': actual['known_motion_residual_mae_rgb'] <= 5,
            'motion_mae_no_worse_than_fgt': actual['known_motion_residual_mae_rgb'] <= baseline['known_motion_residual_mae_rgb']})
    gate_passed = all(all(value for key, value in row.items() if key != 'region') for row in recalculated_gates)
    if recalculated_gates != receipt['public']['quality_gates'] or gate_passed != receipt['public']['controlled_quality_passed']:
        raise ValueError('ROSE_PREDECLARED_GATES_MISREPORTED')
    forward_counts = []
    verified_local_files = {}
    acquisition = json.loads((evidence/'acquisition-verification.json').read_bytes())
    acquired_files = {Path(row['path']).resolve(): row for row in acquisition['files']}
    large_checkpoints = {}
    for name, work in [('public', public), ('natural', natural)]:
        request = json.loads((work/'request.json').read_bytes())
        case = json.loads((work/'case.json').read_bytes())
        worker = json.loads((work/'worker-response.json').read_bytes())
        if worker['status'] != 'succeeded' or worker['blocked_network_events'] or receipt[name]['parent_blocked_network_events']:
            raise ValueError('ROSE_ACTUAL_OFFLINE_INFERENCE_REQUIRED: '+name)
        if request['truth_path_provided'] or request['truth_read_allowed']:
            raise ValueError('ROSE_TRUTH_MUST_NOT_BE_PASSED_TO_WORKER')
        if any('independent-truth' in x['path'] or x['path'].endswith('/truth.npy') for x in request['frozen_files']):
            raise ValueError('ROSE_TRUTH_FOUND_IN_WORKER_REQUEST')
        expected = {'T5': 2, 'T5_blocks': 48, 'transformer': 50, 'transformer_blocks': 1500,
                    'VAE_encode': 1, 'VAE_decode': 1, 'CLIP': 0}
        if worker['model_calls'] != expected or len(worker['loaded_checkpoints']) != 3:
            raise ValueError('ROSE_REAL_FORWARD_OR_LOAD_COUNT_FAILED: '+name)
        if any(x['missing_keys'] or x['unexpected_keys'] or not x['strict'] or not x['assigned'] for x in worker['loaded_checkpoints']):
            raise ValueError('ROSE_STRICT_WEIGHTS_FAILED: '+name)
        if (worker['input']['model_frames'] != 33 or worker['input']['frames'] != 32 or
                not worker['text_encoder_released_before_generation']):
            raise ValueError('ROSE_STAGING_OR_PADDING_CHANGED: '+name)
        for row in request['frozen_files']:
            path = Path(row['path']).resolve()
            acquired = acquired_files.get(path)
            if acquired is not None and acquired['bytes'] >= 128*1024**2:
                # Each succeeded worker re-read the full SHA before and after
                # inference. Bind those checks; avoid scanning the same 15 GB
                # again merely to re-decode and score the delivered videos.
                if path.stat().st_size != acquired['bytes'] or row['sha256'] != acquired['sha256']:
                    raise ValueError('ROSE_POST_VERIFIED_CHECKPOINT_REFERENCE_CHANGED: '+str(path))
                large_checkpoints[str(path)] = {'sha256': row['sha256'], 'bytes': acquired['bytes']}
                continue
            if path not in verified_local_files:
                verified_local_files[path] = sha(path)
            if verified_local_files[path] != row['sha256']:
                raise ValueError('ROSE_FROZEN_INPUT_CHANGED_AFTER_PUBLICATION: '+row['path'])
        if sha(work/'executed-worker.py') != case['worker_sha256'] or sha(work/'executed-runner.py') != case['runner_sha256']:
            raise ValueError('ROSE_EXECUTED_CODE_ARCHIVE_MISMATCH: '+name)
        actual_source = np.load(work/'input.npy', allow_pickle=False)
        actual_final = np.load(work/'final.npy', allow_pickle=False)
        actual_selection = np.load(work/'effective-selection.npy', allow_pickle=False)
        if not np.array_equal(actual_source[~actual_selection], actual_final[~actual_selection]):
            raise ValueError('ROSE_LOCAL_OUTSIDE_REGION_FAILED: '+name)
        if not np.array_equal(actual_source[:, :, :, 3], actual_final[:, :, :, 3]):
            raise ValueError('ROSE_LOCAL_ALPHA_FAILED: '+name)
        observed = json.loads((evidence/(name+'-windows-process-monitor.json')).read_bytes())
        samples = [json.loads(line) for line in (evidence/(name+'-windows-process-samples.jsonl')).read_text(encoding='utf-8').splitlines()]
        if observed != receipt[name]['windows_process_observation'] or len(samples) != observed['samples']:
            raise ValueError('ROSE_WINDOWS_PROCESS_OBSERVATION_CHANGED: '+name)
        if not observed['read_only'] or observed['status'] != 'monitor_ended' or not samples:
            raise ValueError('ROSE_WINDOWS_OBSERVATION_INCOMPLETE: '+name)
        if any(row['pid'] != observed['pid'] for row in samples):
            raise ValueError('ROSE_WINDOWS_OBSERVATION_PID_MISMATCH: '+name)
        if (max(row['os_peak_working_set_bytes'] for row in samples) != observed['last_observed_os_peak_working_set_bytes']
                or max(row['private_bytes'] for row in samples) != observed['sampled_peak_private_bytes']):
            raise ValueError('ROSE_WINDOWS_MEMORY_AGGREGATION_MISMATCH: '+name)
        if 'global_gpu_snapshots' in receipt[name]:
            snapshots = [json.loads(line) for line in
                (evidence/(name+'-gpu-resource-snapshots.jsonl')).read_text(encoding='utf-8').splitlines()]
            if snapshots != receipt[name]['global_gpu_snapshots']:
                raise ValueError('ROSE_GLOBAL_GPU_SNAPSHOTS_CHANGED: '+name)
            sampler_sha = sha(evidence/(name+'-executed-gpu-sampler.py'))
            if any(not row['read_only'] or row['model_forward_calls_during_sampling'] != 0
                   or row['sampler_sha256'] != sampler_sha for row in snapshots):
                raise ValueError('ROSE_GLOBAL_GPU_SAMPLER_IDENTITY_FAILED: '+name)
        forward_counts.append({'case': name, **worker['model_calls']})
    # The curated ZIP contains only fixed source/config/license entries, no
    # checkpoints, author demos, or the separately licensed ProPainter code.
    prep = json.loads((evidence/'preparation.json').read_bytes())
    with zipfile.ZipFile(evidence/'pinned-original-core.zip') as archive:
        if set(archive.namelist()) != {r['path'] for r in prep['original_files']}:
            raise ValueError('ROSE_CURATED_ZIP_INVENTORY_CHANGED')
        for row in prep['original_files']:
            if 'sha256:'+hashlib.sha256(archive.read(row['path'])).hexdigest() != row['sha256']:
                raise ValueError('ROSE_CURATED_ORIGINAL_BYTES_CHANGED')
    result = {'status': 'independent_delivered_checks_passed_quality_separate', 'files_rehashed': len(receipt['files']),
        'production_files_frozen': 186, 'independent_scorer': 'unchanged V44 roll scorer vs V59 explicit row-coordinate sums',
        'original_scorer_sha256': sha(original_scorer),
        'delivered_remeasured': remeasured, 'delivered': delivered, 'model_calls_by_case': forward_counts,
        'new_source_scenes': 0, 'same_v44_controlled_fixture': True, 'raw_outside_changed_pixels': raw_changes,
        'controlled_quality_passed': receipt['public']['controlled_quality_passed'], 'natural_quality_accepted': False,
        'quality_gates_independently_recomputed': recalculated_gates,
        'windows_process_observations_checked': 2,
        'unique_frozen_local_files_rehashed': len(verified_local_files),
        'large_checkpoint_evidence': 'full SHA in each succeeded worker before and after inference; acquisition SHA binding and current lengths here',
        'large_checkpoints_current_lengths_checked': large_checkpoints,
        'product_integrated': False, 'natural_pixels_published': False, 'curated_original_files': len(prep['original_files']),
        'source_receipt_sha256': sha(evidence/'verification.json'), 'generator_sha256': sha(Path(__file__)),
        'full_product_regression_rerun': False, 'current_historical_full_regression': 'V58 1357/1357',
        'continuous_playback_reviewed': False, 'audio_listening_reviewed': False}
    save(output/'verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'natural', 'assets', 'evidence', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    audit(**{k: v.resolve() for k, v in vars(args).items()})
