"""Bounded local harmonic color correction with explicit convergence and reports."""
from __future__ import annotations

import math


def owned_array_bound(width, height, selected_pixels):
    return width * height * 24 + selected_pixels * 384


def _solve(rhs, degree, neighbors, iterations, tolerance, checkpoint=None):
    import numpy as np
    def apply(value):
        result = degree * value
        for direction in range(4):
            valid = neighbors[:, direction] >= 0
            result[valid] -= value[neighbors[valid, direction]]
        return result

    solution = np.zeros_like(rhs)
    residual = rhs.copy()
    target = max(1e-7, tolerance * float(np.linalg.norm(rhs)))
    error = float(np.linalg.norm(residual))
    if error <= target:
        return solution, 0, error, target
    preconditioned = residual / degree
    direction = preconditioned.copy()
    rz = float(np.dot(residual, preconditioned))
    for step in range(1, iterations + 1):
        if checkpoint and step % 32 == 1: checkpoint()
        product = apply(direction)
        denominator = float(np.dot(direction, product))
        if not math.isfinite(denominator) or denominator <= 0:
            raise ValueError('REPAIR_HARMONIZE_SOLVER_BREAKDOWN')
        weight = rz / denominator
        solution += weight * direction
        residual -= weight * product
        if float(np.linalg.norm(residual)) <= target:
            residual = rhs - apply(solution)
            error = float(np.linalg.norm(residual))
            if error <= target:
                return solution, step, error, target
            preconditioned = residual / degree
            direction = preconditioned.copy()
            rz = float(np.dot(residual, preconditioned))
            continue
        preconditioned = residual / degree
        next_rz = float(np.dot(residual, preconditioned))
        if not math.isfinite(next_rz) or next_rz <= 0:
            raise ValueError('REPAIR_HARMONIZE_SOLVER_BREAKDOWN')
        direction *= next_rz / rz
        direction += preconditioned
        rz = next_rz
    raise ValueError('REPAIR_HARMONIZE_NOT_CONVERGED')


def harmonize_region(source_rgba, prediction_rgb, selected, *, max_iterations=2000,
                     relative_tolerance=1e-6, array_budget=256 * 1024**2, checkpoint=None):
    import numpy as np
    if not isinstance(source_rgba, np.ndarray) or source_rgba.dtype != np.uint8 or source_rgba.ndim != 3 or source_rgba.shape[2] != 4:
        raise ValueError('REPAIR_HARMONIZE_SOURCE_INVALID')
    height, width = source_rgba.shape[:2]
    if min(height, width) < 1 or height * width > 16_777_216:
        raise ValueError('REPAIR_HARMONIZE_CANVAS_BUDGET')
    if not isinstance(prediction_rgb, np.ndarray) or prediction_rgb.dtype != np.float32 or prediction_rgb.shape != (height, width, 3) or not np.isfinite(prediction_rgb).all() or np.any(prediction_rgb < 0) or np.any(prediction_rgb > 255):
        raise ValueError('REPAIR_HARMONIZE_PREDICTION_INVALID')
    if not isinstance(selected, np.ndarray) or selected.dtype != np.bool_ or selected.shape != (height, width):
        raise ValueError('REPAIR_HARMONIZE_MASK_INVALID')
    if type(max_iterations) is not int or not 1 <= max_iterations <= 10000 or type(relative_tolerance) not in {int, float} or not math.isfinite(relative_tolerance) or not 0 < relative_tolerance <= .01 or type(array_budget) is not int or array_budget < 1:
        raise ValueError('REPAIR_HARMONIZE_OPTIONS_INVALID')
    if checkpoint is not None and not callable(checkpoint):
        raise ValueError('REPAIR_HARMONIZE_CHECKPOINT_INVALID')
    if checkpoint: checkpoint()
    count = int(np.count_nonzero(selected))
    metrics = {'selected_pixels': count, 'iterations': [0, 0, 0], 'residual_norm': [0., 0., 0.], 'residual_target': [1e-7, 1e-7, 1e-7],
               'boundary_edges': 0, 'owned_array_budget_bytes': 0, 'clipped_rgb_values': 0,
               'max_abs_correction': 0., 'solver': 'masked-four-neighbor-jacobi-pcg-float64',
               'budget_scope': 'incremental-owned-numpy-arrays-excludes-inputs-and-model'}
    if not count:
        return prediction_rgb, metrics
    if count == height * width:
        raise ValueError('REPAIR_HARMONIZE_FULL_MASK_NO_BOUNDARY')
    owned = owned_array_bound(width, height, count)
    if owned > array_budget:
        raise ValueError('REPAIR_HARMONIZE_ARRAY_BUDGET_EXCEEDED')
    ys, xs = np.nonzero(selected)
    index = np.full((height, width), -1, np.int32)
    index[ys, xs] = np.arange(count, dtype=np.int32)
    neighbors = np.full((count, 4), -1, np.int32)
    degree = np.zeros(count, np.float64)
    rhs = np.zeros((count, 3), np.float64)
    model = prediction_rgb[ys, xs].astype(np.float64)
    for column, (dy, dx) in enumerate([(-1, 0), (1, 0), (0, -1), (0, 1)]):
        valid = (ys + dy >= 0) & (ys + dy < height) & (xs + dx >= 0) & (xs + dx < width)
        at = np.flatnonzero(valid)
        qy, qx = ys[at] + dy, xs[at] + dx
        ids = index[qy, qx]
        degree[at] += 1
        neighbors[at, column] = ids
        boundary = ids < 0
        at, qy, qx = at[boundary], qy[boundary], qx[boundary]
        metrics['boundary_edges'] += len(at)
        extrapolated = model[at].copy()
        by, bx = ys[at] - dy, xs[at] - dx
        valid_back = (by >= 0) & (by < height) & (bx >= 0) & (bx < width)
        take = np.flatnonzero(valid_back)
        back_ids = np.full(len(at), -1, np.int32)
        back_ids[take] = index[by[take], bx[take]]
        take = np.flatnonzero(back_ids >= 0)
        extrapolated[take] += extrapolated[take] - model[back_ids[take]]
        rhs[at] += source_rgba[qy, qx, :3].astype(np.float64) - extrapolated
    correction = np.zeros_like(rhs)
    for channel in range(3):
        values, steps, residual, target = _solve(rhs[:, channel], degree, neighbors, max_iterations, relative_tolerance, checkpoint)
        correction[:, channel] = values
        metrics['iterations'][channel] = steps
        metrics['residual_norm'][channel] = residual
        metrics['residual_target'][channel] = target
    corrected = model + correction
    if not np.isfinite(corrected).all():
        raise ValueError('REPAIR_HARMONIZE_NONFINITE_RESULT')
    metrics['clipped_rgb_values'] = int(np.count_nonzero((corrected < 0) | (corrected > 255)))
    metrics['max_abs_correction'] = float(np.abs(correction).max())
    metrics['owned_array_budget_bytes'] = owned
    output = prediction_rgb.copy()
    output[ys, xs] = np.clip(corrected, 0, 255).astype(np.float32)
    return output, metrics


SOLVER = 'masked-four-neighbor-jacobi-pcg-float64'
BUDGET_SCOPE = 'incremental-owned-numpy-arrays-excludes-inputs-and-model'


def required_blend_bytes(width, height, count, options):
    if options.get('blend_mode', 'direct') == 'direct' or count == 0:
        return 0
    if count == width * height:
        raise ValueError('REPAIR_HARMONIZE_FULL_MASK_NO_BOUNDARY')
    return owned_array_bound(width, height, count)


def joint_blend_overhead(width, height, options):
    # Additional full-frame floating intermediates, separate from solver arrays.
    return width * height * 24 if options.get('blend_mode') == 'harmonic' else 0


def blend_budget_plan(width, height, options, budget, base=None):
    enabled = options['blend_mode'] == 'harmonic'
    result = {'mode': options['blend_mode'], 'mask_pixel_count_known': False,
              'solver_owned_minimum_nonempty_bytes': owned_array_bound(width, height, 1) if enabled else 0,
              'solver_owned_maximum_bytes': owned_array_bound(width, height, max(0, width * height - 1)) if enabled else 0,
              'state_budget_bytes': budget,
              'admission': 'actual-selected-pixels-before-each-model-call-and-before-blend',
              'scope': 'owned-arrays-excludes-model-torch-and-total-process-or-device-memory'}
    if base is not None:
        result['owned_array_base_bytes'] = base
        result['available_solver_bytes'] = max(0, budget - base)
    return result


def new_blend_report(options):
    return {'mode': options.get('blend_mode', 'direct'), 'solver': SOLVER if options.get('blend_mode') == 'harmonic' else 'none',
            'frames': 0, 'max_selected_pixels': 0, 'owned_array_peak_bytes': 0,
            'iterations_max': [0, 0, 0], 'residual_ratio_max': 0., 'boundary_edges': 0,
            'clipped_rgb_values': 0, 'max_abs_correction': 0., 'seconds': 0., 'samples': []}


def record_blend(report, frame, detail, elapsed):
    report['frames'] += 1
    report['max_selected_pixels'] = max(report['max_selected_pixels'], detail['selected_pixels'])
    report['owned_array_peak_bytes'] = max(report['owned_array_peak_bytes'], detail['owned_array_budget_bytes'])
    report['iterations_max'] = [max(a, b) for a, b in zip(report['iterations_max'], detail['iterations'])]
    report['residual_ratio_max'] = max(report['residual_ratio_max'], max(a/b for a, b in zip(detail['residual_norm'], detail['residual_target'])))
    report['boundary_edges'] += detail['boundary_edges']
    report['clipped_rgb_values'] += detail['clipped_rgb_values']
    report['max_abs_correction'] = max(report['max_abs_correction'], detail['max_abs_correction'])
    report['seconds'] += elapsed
    if len(report['samples']) < 16:
        report['samples'].append({'frame': frame, **detail})


def validate_blend_report(metrics, options, *, width, height, frames):
    """Validate observable solver/admission statistics before publishing media."""
    report = metrics.get('blend')
    expected = new_blend_report(options)
    if not isinstance(report, dict) or set(report) != set(expected) or report['mode'] != expected['mode'] or report['solver'] != expected['solver']:
        raise ValueError('repair blend execution mode or fields')
    nonempty = frames - metrics['empty_mask_frames']
    expected_frames = nonempty if options['blend_mode'] == 'harmonic' else 0
    if type(report['frames']) is not int or report['frames'] != expected_frames:
        raise ValueError('repair blend frame count')
    area = width * height
    def number(value):
        return type(value) in {int, float} and math.isfinite(value) and value >= 0
    for key in ('max_selected_pixels', 'owned_array_peak_bytes', 'boundary_edges', 'clipped_rgb_values'):
        if type(report[key]) is not int or report[key] < 0:
            raise ValueError('repair blend integer metrics')
    if any(not number(report[k]) for k in ('residual_ratio_max', 'max_abs_correction', 'seconds')):
        raise ValueError('repair blend numeric metrics')
    if not isinstance(report['iterations_max'], list) or len(report['iterations_max']) != 3 or any(type(v) is not int or v < 0 for v in report['iterations_max']) or not isinstance(report['samples'], list):
        raise ValueError('repair blend list metrics')
    if not expected_frames:
        if report != expected:
            raise ValueError('repair blend bypass must not report execution')
        return
    if not 1 <= report['max_selected_pixels'] < area or report['max_selected_pixels'] > metrics['mask_pixels']:
        raise ValueError('repair blend selected pixels')
    if report['owned_array_peak_bytes'] != owned_array_bound(width, height, report['max_selected_pixels']):
        raise ValueError('repair blend owned-array estimate')
    if not expected_frames <= report['boundary_edges'] <= 4 * metrics['mask_pixels'] or report['clipped_rgb_values'] > 3 * metrics['mask_pixels']:
        raise ValueError('repair blend boundary/clipping counters')
    if any(not number(report[k]) for k in ('residual_ratio_max', 'max_abs_correction', 'seconds')) or report['residual_ratio_max'] > 1.:
        raise ValueError('repair blend convergence or elapsed metrics')
    iterations = report['iterations_max']
    if not isinstance(iterations, list) or len(iterations) != 3 or any(type(v) is not int or not 0 <= v <= options['blend_max_iterations'] for v in iterations):
        raise ValueError('repair blend iteration metrics')
    samples = report['samples']
    if not isinstance(samples, list) or len(samples) != min(16, expected_frames):
        raise ValueError('repair blend sample count')
    last = -1
    for sample in samples:
        if not isinstance(sample, dict) or type(sample.get('frame')) is not int or not last < sample['frame'] < frames:
            raise ValueError('repair blend sample frame')
        last = sample['frame']
        count = sample.get('selected_pixels')
        if type(count) is not int or not 1 <= count <= report['max_selected_pixels'] or sample.get('solver') != SOLVER or sample.get('budget_scope') != BUDGET_SCOPE:
            raise ValueError('repair blend sample selection/solver')
        if type(sample.get('owned_array_budget_bytes')) is not int or sample['owned_array_budget_bytes'] != owned_array_bound(width, height, count):
            raise ValueError('repair blend sample budget')
        for key in ('iterations', 'residual_norm', 'residual_target'):
            if not isinstance(sample.get(key), list) or len(sample[key]) != 3:
                raise ValueError('repair blend sample residual shape')
        for c in range(3):
            it, residual, target = sample['iterations'][c], sample['residual_norm'][c], sample['residual_target'][c]
            if type(it) is not int or not 0 <= it <= iterations[c] or not number(residual) or not number(target) or target < 1e-7 or residual > target or residual/target > report['residual_ratio_max']:
                raise ValueError('repair blend sample convergence')
        if type(sample.get('boundary_edges')) is not int or not 1 <= sample['boundary_edges'] <= 4 * count or type(sample.get('clipped_rgb_values')) is not int or not 0 <= sample['clipped_rgb_values'] <= 3 * count or not number(sample.get('max_abs_correction')) or sample['max_abs_correction'] > report['max_abs_correction']:
            raise ValueError('repair blend sample statistics')
    if expected_frames <= 16 and (sum(s['selected_pixels'] for s in samples) != metrics['mask_pixels'] or max(s['selected_pixels'] for s in samples) != report['max_selected_pixels']):
        raise ValueError('repair blend sample aggregation')
