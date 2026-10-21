"""Local, bounded affine camera-clock estimation and sealed report validation."""
from __future__ import annotations
import hashlib
import json
import math
import re
from typing import Any

from .errors import AppError, argument_error, dependency_error

PROTOCOL = 'multicam-affine-clock-v1'
FEATURE_HZ = 50


def _numpy():
    try:
        import numpy as np
        return np
    except ImportError as exc:
        raise dependency_error('仿射机位同步需要本地 NumPy', '使用已核验的八轮离线媒体包') from exc


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise argument_error(name + ' 必须为有限数值', name)
    return float(value)


def validate_affine_options(*, max_offset_seconds, max_drift_ppm, window_seconds, anchor_count):
    offset = _number(max_offset_seconds, 'max_offset_seconds')
    drift = _number(max_drift_ppm, 'max_drift_ppm')
    window = _number(window_seconds, 'window_seconds')
    if not 0 <= offset <= 300:
        raise argument_error('max_offset_seconds 必须位于 0..300', 'max_offset_seconds')
    if not 0 < drift <= 20_000:
        raise argument_error('max_drift_ppm 必须位于 0..20000', 'max_drift_ppm')
    if not 4 <= window <= 60:
        raise argument_error('drift_window_seconds 必须位于 4..60', 'window_seconds')
    if isinstance(anchor_count, bool) or not isinstance(anchor_count, int) or not 3 <= anchor_count <= 31:
        raise argument_error('drift_anchors 必须为 3..31 的整数', 'anchor_count')
    return offset, drift, window, anchor_count


def seal_clock(model):
    body = {key: value for key, value in model.items() if key != 'calibration_sha256'}
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {**body, 'calibration_sha256': 'sha256:' + hashlib.sha256(payload).hexdigest()}


def _coarse_offset(reference, candidate, search_seconds, minimum_seconds):
    np = _numpy()
    # Ten-Hz discovery is only a search-center hint. Final anchors use 50 Hz.
    left = reference[:reference.size // 5 * 5].reshape(-1, 5).mean(axis=1)
    right = candidate[:candidate.size // 5 * 5].reshape(-1, 5).mean(axis=1)
    cross = np.correlate(left, right, mode='full')
    def prefix(values):
        return np.concatenate(([0.], np.cumsum(values, dtype=np.float64)))
    a, aa = prefix(left), prefix(left * left)
    b, bb = prefix(right), prefix(right * right)
    ranked = []
    maximum = int(math.ceil(search_seconds * 10))
    for lag in range(max(-right.size + 1, -maximum), min(left.size - 1, maximum) + 1):
        start_a, start_b = max(0, lag), max(0, -lag)
        count = min(left.size - start_a, right.size - start_b)
        if count < minimum_seconds * 10:
            continue
        x, y = a[start_a + count] - a[start_a], b[start_b + count] - b[start_b]
        xx = max(0., aa[start_a + count] - aa[start_a] - x * x / count)
        yy = max(0., bb[start_b + count] - bb[start_b] - y * y / count)
        denominator = math.sqrt(xx * yy)
        score = (cross[lag + right.size - 1] - x * y / count) / denominator if denominator > 1e-12 else -1.
        ranked.append((float(score), count, -abs(lag), lag))
    if not ranked:
        raise AppError('MULTICAM_CLOCK_SPAN_SHORT', '没有足够的共同音频时段校准漂移', exit_code=2)
    return -max(ranked)[3] / 10.


def _anchor(reference, candidate, center, half_bins, offset, rate, radius):
    np = _numpy()
    half_source = max(1, int(round(half_bins * rate)))
    template_positions = center * FEATURE_HZ + np.arange(-half_source, half_source + 1) / rate
    template = np.interp(template_positions, np.arange(reference.size), reference)
    predicted_center = offset + rate * center
    first = max(0, int(math.floor((predicted_center - radius) * FEATURE_HZ)) - half_source)
    final = min(candidate.size, int(math.ceil((predicted_center + radius) * FEATURE_HZ)) + half_source + 1)
    row = {'reference_seconds': round(center, 9), 'template_rate': round(rate, 12),
           'source_search_start_seconds': first / FEATURE_HZ, 'source_search_end_seconds': final / FEATURE_HZ,
           'accepted': False}
    values = candidate[first:final]
    if values.size < template.size:
        return {**row, 'reason': 'source_window_short'}
    template = template - template.mean()
    template_energy = float(np.dot(template, template))
    sums = np.concatenate(([0.], np.cumsum(values, dtype=np.float64)))
    squares = np.concatenate(([0.], np.cumsum(values * values, dtype=np.float64)))
    width = template.size
    total = sums[width:] - sums[:-width]
    variance = np.maximum(0., squares[width:] - squares[:-width] - total * total / width)
    denominator = np.sqrt(variance * template_energy)
    scores = np.full(variance.size, -1., dtype=np.float64)
    np.divide(np.correlate(values, template, mode='valid'), denominator, out=scores, where=denominator > 1e-12)
    scores = np.clip(scores, -1., 1.)
    best = int(np.argmax(scores))
    peak = float(scores[best])
    delta = 0.
    if 0 < best < scores.size - 1:
        before, after = float(scores[best - 1]), float(scores[best + 1])
        curvature = before - 2 * peak + after
        if curvature < -1e-12:
            delta = max(-.5, min(.5, .5 * (before - after) / curvature))
    alternatives = scores.copy()
    exclusion = max(1, int(round(.1 * FEATURE_HZ)))
    alternatives[max(0, best - exclusion):min(scores.size, best + exclusion + 1)] = -1.
    second = float(np.max(alternatives)) if alternatives.size else -1.
    margin = peak - second
    accepted = peak >= .55 and margin >= .03
    return {**row, 'source_seconds': round((first + best + half_source + delta) / FEATURE_HZ, 9),
            'score': round(peak, 9), 'second_peak_score': round(second, 9), 'peak_margin': round(margin, 9),
            'subsample_peak_bins': round(delta, 9), 'accepted': accepted,
            'reason': 'matched' if accepted else ('ambiguous_peak' if margin < .03 else 'low_correlation')}


def _fit(anchors, window, required):
    np = _numpy()
    good = [row for row in anchors if row['accepted']]
    if len(good) < required:
        raise AppError('MULTICAM_CLOCK_LOW_CONFIDENCE', '可靠且无歧义的音频锚点不足', exit_code=2,
                       cause=json.dumps({'accepted': len(good), 'required': required}, ensure_ascii=False))
    x = np.array([row['reference_seconds'] for row in good], dtype=np.float64)
    y = np.array([row['source_seconds'] for row in good], dtype=np.float64)
    slopes = [(y[j] - y[i]) / (x[j] - x[i]) for i in range(x.size)
              for j in range(i + 1, x.size) if x[j] - x[i] >= window]
    if not slopes or float(x.max() - x.min()) < 2 * window:
        raise AppError('MULTICAM_CLOCK_SPAN_SHORT', '可靠锚点时间跨度不足两个分析窗口', exit_code=2)
    rate = float(np.median(slopes))
    offset = float(np.median(y - rate * x))
    residual = y - (offset + rate * x)
    median = float(np.median(np.abs(residual)))
    threshold = min(.04, max(1. / FEATURE_HZ, 4.5 * median))
    keep = np.abs(residual) <= threshold
    # Do not accept one locally linear half of a nonlinear recording as a full calibration.
    if int(keep.sum()) < max(required, math.ceil(len(good) * .8)):
        raise AppError('MULTICAM_CLOCK_NONAFFINE', '锚点不符合单一仿射时钟；拒绝按半段数据隐式校准', exit_code=2)
    active_x, active_y = x[keep], y[keep]
    if float(active_x.max() - active_x.min()) < 2 * window:
        raise AppError('MULTICAM_CLOCK_SPAN_SHORT', '拟合内点的时间跨度不足', exit_code=2)
    centered = active_x - active_x.mean()
    rate = float(np.dot(centered, active_y - active_y.mean()) / np.dot(centered, centered))
    offset = float(active_y.mean() - rate * active_x.mean())
    final_residual = y - (offset + rate * x)
    for index, row in enumerate(good):
        row['residual_seconds'] = round(float(final_residual[index]), 9)
        if not bool(keep[index]):
            row.update(accepted=False, reason='fit_outlier')
    accepted_residual = final_residual[keep]
    if float(np.max(np.abs(accepted_residual))) > .04:
        raise AppError('MULTICAM_CLOCK_NONAFFINE', '仿射时钟残差超过 40ms', exit_code=2)
    standard_error = math.sqrt(float(np.dot(accepted_residual, accepted_residual)) /
                               max(1, active_x.size - 2) / float(np.dot(centered, centered)))
    return rate, offset, {'accepted_anchors': int(keep.sum()), 'rejected_anchors': len(anchors) - int(keep.sum()),
        'anchor_span_seconds': round(float(active_x.max() - active_x.min()), 9),
        'maximum_residual_seconds': round(float(np.max(np.abs(accepted_residual))), 9),
        'rms_residual_seconds': round(float(np.sqrt(np.mean(accepted_residual ** 2))), 9),
        'slope_standard_error_ppm': round(standard_error * 1e6, 6),
        'outlier_threshold_seconds': threshold}


def estimate_affine_clock(reference, candidate, *, max_offset_seconds=30., max_drift_ppm=5000.,
                          window_seconds=12., anchor_count=9):
    np = _numpy()
    maximum_offset, maximum_drift, window, count = validate_affine_options(
        max_offset_seconds=max_offset_seconds, max_drift_ppm=max_drift_ppm,
        window_seconds=window_seconds, anchor_count=anchor_count)
    arrays = []
    for name, value in (('reference', reference), ('candidate', candidate)):
        array = np.asarray(value, dtype=np.float64)
        if array.ndim != 1 or array.size > 46_000 or not bool(np.all(np.isfinite(array))):
            raise argument_error('音频特征必须为有界的一维有限数组', name)
        if array.size < 3 * window * FEATURE_HZ:
            raise AppError('MULTICAM_CLOCK_SPAN_SHORT', '音频长度不足三个漂移窗口', exit_code=2)
        scale = float(np.std(array))
        if scale <= 1e-9:
            raise AppError('MULTICAM_CLOCK_SIGNAL_FLAT', '音频特征平坦，无法校准漂移', exit_code=2)
        arrays.append((array - array.mean()) / scale)
    left, right = arrays
    radius = maximum_drift / 1e6 * left.size / FEATURE_HZ + .12
    offset = _coarse_offset(left, right, maximum_offset + radius, 2 * window)
    rate = 1.
    half_bins = max(1, int(round(window * FEATURE_HZ / 2)))
    centers = np.linspace(half_bins, left.size - 1 - half_bins, count) / FEATURE_HZ
    required = max(3, math.ceil(count * .55))
    passes = []
    for iteration in range(3):
        anchors = [_anchor(left, right, float(center), half_bins, offset, rate, radius) for center in centers]
        rate, offset, fit = _fit(anchors, window, required)
        if abs(rate - 1.) * 1e6 > maximum_drift or abs(offset) > maximum_offset + 1. / FEATURE_HZ:
            raise AppError('MULTICAM_CLOCK_OUT_OF_RANGE', '估计的偏移或设备漂移超过显式上限', exit_code=2)
        passes.append({'iteration': iteration + 1, 'source_per_reference': rate, 'offset_seconds': offset,
                       'anchors': anchors, 'fit': fit})
        # Keep the original ambiguity search domain even during refinement.
    rate, offset = round(rate, 12), round(offset, 9)
    accepted = [row for row in anchors if row['accepted']]
    valid_start = max(0., -offset / rate, min(row['reference_seconds'] for row in accepted) - half_bins / FEATURE_HZ)
    valid_end = min(left.size / FEATURE_HZ, (right.size / FEATURE_HZ - offset) / rate,
                    max(row['reference_seconds'] for row in accepted) + (half_bins + 1) / FEATURE_HZ)
    if valid_end <= valid_start:
        raise AppError('MULTICAM_CLOCK_SPAN_SHORT', '校准没有共同的已观察源时钟范围', exit_code=2)
    model = {
        'protocol': PROTOCOL, 'kind': 'affine', 'status': 'calibrated',
        'offset_seconds': offset, 'source_per_reference': rate, 'drift_ppm': round((rate - 1.) * 1e6, 6),
        'inverse': {'reference_per_source': round(1. / rate, 15), 'offset_seconds': round(-offset / rate, 15)},
        'valid_reference_range': {'start_seconds': round(valid_start, 9), 'end_seconds': round(valid_end, 9)},
        'parameters': {'feature_rate_hz': FEATURE_HZ, 'window_seconds': window, 'anchor_count': count,
                       'max_drift_ppm': maximum_drift, 'max_offset_seconds': maximum_offset},
        'feature_counts': {'reference': int(left.size), 'source': int(right.size)},
        'anchors': anchors, 'fit': fit, 'refinement_passes': passes,
        'quantization_seconds': 1. / FEATURE_HZ, 'subsample_peak': 'parabolic_local_approximation',
        'limits': ['single_affine_clock', 'observed_prefix_only', 'no_discontinuous_or_piecewise_clock',
                   'statistical_fit_is_not_natural_audio_or_listening_acceptance']}
    return seal_clock(model)


def clock_for_alignment(sync: dict[str, Any], alignment: dict[str, Any], asset_id: str):
    """Validate a bound model and return its forward mapping and valid range."""
    reference_id = str(sync.get('reference_asset_id', ''))
    affine_requested = sync.get('parameters', {}).get('clock_model') == 'affine'
    model = alignment.get('clock_model')
    if model is None:
        if affine_requested and asset_id != reference_id:
            raise AppError('MULTICAM_CLOCK_INVALID', '仿射同步结果缺少机位校准模型', exit_code=2)
        return None
    try:
        if not isinstance(model, dict) or model.get('protocol') != PROTOCOL or model.get('kind') != 'affine' or model.get('status') != 'calibrated':
            raise ValueError('unknown clock model or unsuccessful calibration')
        if model.get('calibration_sha256') != seal_clock(model)['calibration_sha256']:
            raise ValueError('clock content digest mismatch')
        if model.get('source_asset_id') != asset_id or model.get('reference_asset_id') != reference_id:
            raise ValueError('clock asset IDs mismatch')
        reference = next(row for row in sync.get('offsets', []) if row.get('asset_id') == reference_id)
        source_sha = model.get('source_sha256')
        reference_sha = model.get('reference_sha256')
        if any(not isinstance(value, str) or re.fullmatch(r'sha256:[0-9a-f]{64}', value) is None
               for value in (source_sha, reference_sha)):
            raise ValueError('missing or malformed source hash identity')
        if source_sha != alignment.get('evidence', {}).get('sha256') or reference_sha != reference.get('evidence', {}).get('sha256'):
            raise ValueError('clock source hashes mismatch')
        rate = _number(model['source_per_reference'], 'clock.source_per_reference')
        offset = _number(model['offset_seconds'], 'clock.offset_seconds')
        if not .98 <= rate <= 1.02 or abs(offset) > 300.02:
            raise ValueError('clock coefficients outside protocol bounds')
        if not math.isclose(_number(model['drift_ppm'], 'clock.drift_ppm'), (rate - 1.) * 1e6, abs_tol=.001, rel_tol=0.):
            raise ValueError('declared drift differs from actual clock rate')
        if not math.isclose(_number(alignment['relative_delay_seconds'], 'clock.zero_time_projection'), offset, abs_tol=1e-7, rel_tol=0.):
            raise ValueError('legacy zero-time offset disagrees with affine clock')
        inverse = model['inverse']
        if not math.isclose(_number(inverse['reference_per_source'], 'clock.inverse.rate'), 1. / rate, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError('clock inverse rate mismatch')
        if not math.isclose(_number(inverse['offset_seconds'], 'clock.inverse.offset'), -offset / rate, rel_tol=1e-9, abs_tol=1e-7):
            raise ValueError('clock inverse offset mismatch')
        bounds = model['valid_reference_range']
        start = _number(bounds['start_seconds'], 'clock.range.start_seconds')
        end = _number(bounds['end_seconds'], 'clock.range.end_seconds')
        if start < 0 or end <= start:
            raise ValueError('invalid observed calibration range')
        reference_duration = _number(reference.get('evidence', {}).get('duration_seconds'), 'clock.reference_duration')
        source_duration = _number(alignment.get('evidence', {}).get('duration_seconds'), 'clock.source_duration')
        if reference_duration <= 0 or source_duration <= 0 or end > reference_duration + 2. / FEATURE_HZ:
            raise ValueError('observed range exceeds reference media')
        if offset + rate * start < -1e-7 or offset + rate * end > source_duration + 2. / FEATURE_HZ:
            raise ValueError('observed range exceeds source media')
        return rate, offset, start, end
    except (AppError, KeyError, TypeError, ValueError, StopIteration, OverflowError) as exc:
        raise AppError('MULTICAM_CLOCK_INVALID', '多机位时钟模型无效或与当前源不匹配', exit_code=2, cause=str(exc)) from exc
