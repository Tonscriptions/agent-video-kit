"""Bounded identities and validation for explicit generated video context."""
from __future__ import annotations

import hashlib
import json
import re

from .errors import AppError

PROTOCOL = 'agent-vace-generated-context-v1'
TRACE_PROTOCOL = 'agent-vace-conditioning-trace-v1'
HASH = re.compile(r'sha256:[0-9a-f]{64}\Z')


def validate_generation_metadata(value, *, asset):
    """Keep explicit sampling in saved rendered assets and fragment copies."""
    from .local_vace import normalize_generation
    try:
        if asset['kind'] != 'video' or not isinstance(value, dict):
            raise ValueError('VACE generation metadata requires a video and parameters')
        stream = next(s for s in asset['probe']['streams'] if s.get('codec_type') == 'video'
                      and not s.get('disposition', {}).get('attached_pic'))
        frames = int(stream['nb_frames'])
        if frames < 1 or normalize_generation(**value, frames=frames) != value:
            raise ValueError('Noncanonical VACE generation metadata')
    except (AppError, KeyError, ValueError, TypeError, StopIteration, OverflowError) as exc:
        raise AppError('VACE_GENERATION_METADATA_INVALID', 'VACE 生成参数或输出帧范围无效', exit_code=2, cause=str(exc)) from exc


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('utf8')


class ConditioningTrace:
    """Hash actual contiguous uint8 model inputs without retaining their arrays."""
    def __init__(self):
        self.calls = 0
        self.samples = []
        self.digest = hashlib.sha256()

    def add(self, images, masks):
        shape, mask_shape = list(images.shape), list(masks.shape)
        if (str(images.dtype) != 'uint8' or str(masks.dtype) != 'uint8' or len(shape) != 4
                or shape[-1] != 3 or shape[:-1] != mask_shape
                or not images.flags.c_contiguous or not masks.flags.c_contiguous):
            raise ValueError('VACE_CONDITIONING_TRACE_INPUT_INVALID')
        row = {'call': self.calls, 'rgb_shape': shape, 'mask_shape': mask_shape,
               'rgb_sha256': 'sha256:'+hashlib.sha256(memoryview(images).cast('B')).hexdigest(),
               'mask_sha256': 'sha256:'+hashlib.sha256(memoryview(masks).cast('B')).hexdigest()}
        self.digest.update(_encoded(row))
        if len(self.samples) < 16:
            self.samples.append(row)
        self.calls += 1

    def snapshot(self):
        return {'protocol': TRACE_PROTOCOL, 'calls': self.calls,
                'sha256': 'sha256:'+self.digest.hexdigest(), 'samples': list(self.samples)}


def _integer(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def validate_context_report(metrics, execution, generation, *, width, height, windows):
    """Validate closure-bound worker evidence; hashes do not establish image quality."""
    if not isinstance(execution, dict):
        raise ValueError('VACE_MODEL_EXECUTION_REPORT_INVALID')
    mode = generation.get('temporal_context', 'none')
    report = metrics.get('temporal_context')
    if mode == 'none':
        if report is not None or execution.get('conditioning_trace') is not None:
            raise ValueError('VACE_UNREQUESTED_TEMPORAL_CONTEXT')
        return
    if mode != 'previous' or generation['window_overlap'] < 1:
        raise ValueError('VACE_TEMPORAL_CONTEXT_MODE_INVALID')
    fields = {'protocol', 'mode', 'source_kind', 'output_policy', 'generated_context_is_ground_truth',
              'windows_conditioned', 'frames_conditioned', 'pixels_conditioned', 'peak_frames', 'peak_bytes',
              'capacity_bytes', 'scene_resets', 'cross_scene_frames', 'input_trace'}
    if (not isinstance(report, dict) or set(report) != fields or report['protocol'] != PROTOCOL
            or report['mode'] != mode or report['source_kind'] != 'previous-emitted-generated-rgba'
            or report['output_policy'] != 'retain-emitted-prefix' or report['generated_context_is_ground_truth'] is not False):
        raise ValueError('VACE_TEMPORAL_CONTEXT_REPORT_INVALID')
    calls, overlap, pixels = metrics['model_calls'], generation['window_overlap'], width*height
    bounds = {'windows_conditioned': calls, 'frames_conditioned': calls*overlap,
              'pixels_conditioned': calls*overlap*pixels, 'peak_frames': overlap,
              'peak_bytes': overlap*pixels*4, 'capacity_bytes': overlap*pixels*4,
              'scene_resets': len(generation['scene_cut_frames']), 'cross_scene_frames': 0}
    if any(not _integer(report.get(key), maximum) for key, maximum in bounds.items()):
        raise ValueError('VACE_TEMPORAL_CONTEXT_COUNTER_INVALID')
    if (report['peak_bytes'] != report['peak_frames']*pixels*4 or report['capacity_bytes'] != overlap*pixels*4
            or report['scene_resets'] != len(generation['scene_cut_frames'])
            or report['frames_conditioned'] > report['windows_conditioned']*overlap
            or report['windows_conditioned'] > report['frames_conditioned']
            or not report['frames_conditioned'] <= report['pixels_conditioned'] <= report['frames_conditioned']*pixels
            or metrics['overlap_frames_blended'] != 0):
        raise ValueError('VACE_TEMPORAL_CONTEXT_COUNTER_MISMATCH')
    trace = report['input_trace']
    if (not isinstance(trace, dict) or set(trace) != {'protocol', 'calls', 'sha256', 'samples'}
            or trace['protocol'] != TRACE_PROTOCOL or type(trace['calls']) is not int or trace['calls'] != calls
            or not isinstance(trace['sha256'], str) or not HASH.fullmatch(trace['sha256'])
            or not isinstance(trace['samples'], list) or len(trace['samples']) != min(calls, 16)):
        raise ValueError('VACE_CONDITIONING_TRACE_INVALID')
    encoded_samples = hashlib.sha256()
    shapes = execution.get('window_input_shapes', [])
    if not isinstance(shapes, list) or calls and len(shapes) != calls:
        raise ValueError('VACE_MODEL_CONDITIONING_SHAPES_MISSING')
    for index, row in enumerate(trace['samples']):
        if (not isinstance(row, dict) or set(row) != {'call', 'rgb_shape', 'mask_shape', 'rgb_sha256', 'mask_sha256'}
                or type(row['call']) is not int or row['call'] != index):
            raise ValueError('VACE_CONDITIONING_TRACE_SAMPLE_INVALID')
        shape = row['rgb_shape']
        mask_shape = row['mask_shape']
        if (not isinstance(shape, list) or len(shape) != 4 or any(type(v) is not int or v < 1 for v in shape)
                or shape[-1] != 3 or not isinstance(mask_shape, list)
                or any(type(v) is not int for v in mask_shape) or mask_shape != shape[:-1]
                or shapes[index] != shape[:-1]
                or any(not isinstance(row[k], str) or not HASH.fullmatch(row[k]) for k in ('rgb_sha256', 'mask_sha256'))):
            raise ValueError('VACE_CONDITIONING_TRACE_SHAPE_OR_HASH_INVALID')
        encoded_samples.update(_encoded(row))
    if calls <= 16 and trace['sha256'] != 'sha256:'+encoded_samples.hexdigest():
        raise ValueError('VACE_CONDITIONING_TRACE_DIGEST_INVALID')
    if calls and execution.get('conditioning_trace') != trace:
        raise ValueError('VACE_MODEL_CONDITIONING_TRACE_MISMATCH')
    if not calls and execution.get('conditioning_trace') is not None:
        raise ValueError('VACE_UNEXECUTED_MODEL_CONDITIONING_TRACE')
    samples = metrics.get('window_samples')
    if not isinstance(samples, list) or len(samples) != min(len(windows), 16):
        raise ValueError('VACE_TEMPORAL_WINDOW_SAMPLES_INVALID')
    seen_windows = seen_frames = seen_pixels = 0
    sampled_calls = 0
    for index, (sample, spec) in enumerate(zip(samples, windows)):
        if not isinstance(sample, dict):
            raise ValueError('VACE_TEMPORAL_WINDOW_SAMPLE_INVALID')
        rows = sample.get('context_inputs')
        if (sample.get('start') != spec['start'] or sample.get('end') != spec['end']
                or sample.get('model_frames') != spec['model_frames'] or sample.get('seed') != spec['seed']
                or type(sample.get('model_calls')) is not int or sample['model_calls'] not in (0, 1)
                or not isinstance(rows, list) or len(rows) > overlap or len(rows) > report['peak_frames']):
            raise ValueError('VACE_TEMPORAL_WINDOW_SAMPLE_INVALID')
        if rows and (not sample['model_calls'] or index == 0 or spec['scene_start'] != windows[index-1]['scene_start']):
            raise ValueError('VACE_TEMPORAL_CONTEXT_WITHOUT_PREDECESSOR')
        previous_end = windows[index-1]['end'] if index else spec['start']
        last = spec['start']-1
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {'frame', 'pixels', 'rgba_sha256'}
                    or type(row['frame']) is not int or not last < row['frame'] < min(previous_end, spec['end'])
                    or not _integer(row['pixels'], pixels) or row['pixels'] == 0
                    or not isinstance(row['rgba_sha256'], str) or not HASH.fullmatch(row['rgba_sha256'])):
                raise ValueError('VACE_TEMPORAL_CONTEXT_FRAME_INVALID')
            last = row['frame']
            seen_pixels += row['pixels']
        seen_windows += bool(rows)
        seen_frames += len(rows)
        sampled_calls += sample['model_calls']
    remaining = len(windows)-len(samples)
    if not sampled_calls <= calls <= sampled_calls+remaining:
        raise ValueError('VACE_TEMPORAL_MODEL_CALL_SAMPLE_TOTAL_MISMATCH')
    for key, observed, extra in (('windows_conditioned', seen_windows, remaining),
                                ('frames_conditioned', seen_frames, remaining*overlap),
                                ('pixels_conditioned', seen_pixels, remaining*overlap*pixels)):
        if not observed <= report[key] <= observed+extra:
            raise ValueError('VACE_TEMPORAL_CONTEXT_SAMPLE_TOTAL_MISMATCH')
