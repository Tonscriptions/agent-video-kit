"""Research repair using independently scored camera and dense references.

Each donor frame contributes at most one candidate, even when two motion models
reach it. Scores use observed context only; hidden geometry remains unverified.
"""
from __future__ import annotations

import warnings

import cv2
import numpy as np

from camera_motion import estimate_camera
from flow_core import _grid, _inside, _remap, estimate, validate_inputs


ALGORITHM = 'observed-context-camera-dense-reference-selection-v1'


def array_bound(frames, height, width):
    return height * width * (192 * frames + 1536)


def _context_error(target_rgb, sampled_rgb, known):
    count = cv2.boxFilter(known.astype(np.float32), -1, (65, 65), normalize=False,
                         borderType=cv2.BORDER_CONSTANT)
    error = np.mean(np.abs(target_rgb - sampled_rgb), axis=2)
    total = cv2.boxFilter(np.where(known, error, 0), -1, (65, 65), normalize=False,
                         borderType=cv2.BORDER_CONSTANT)
    return total / np.maximum(count, 1), count


def choose_reference(target_rgb, candidates, target_known):
    """One observation per donor; compare motion models on common visible pixels.

    Candidate entries are (model name, RGB, observed endpoint/path mask). The
    lower-level caller supplies erased RGB and validates all array contracts.
    """
    errors, eligible, names = [], [], []
    common = target_known.copy()
    for _, _, valid in candidates:
        common &= valid
    common_count = cv2.boxFilter(common.astype(np.float32), -1, (65, 65), normalize=False,
                                borderType=cv2.BORDER_CONSTANT)
    for name, rgb, valid in candidates:
        own_error, own_count = _context_error(target_rgb, rgb, target_known & valid)
        common_error, _ = _context_error(target_rgb, rgb, common)
        # When both paths lack common context, do not rank their disjoint samples
        # as if they were the same experiment. Only a single supported path may
        # be used there; otherwise this donor abstains.
        errors.append(np.where(common_count >= 64, common_error, own_error))
        eligible.append(valid & (own_count >= 64))
        names.append(name)
    costs = np.stack(errors)
    usable = np.stack(eligible)
    if len(candidates) > 1:
        usable &= (common_count >= 64)[None] | (usable.sum(axis=0) == 1)[None]
    usable &= costs <= 12
    costs = np.where(usable, costs, np.inf)
    choice = np.argmin(costs, axis=0)
    height, width = target_known.shape
    values = np.stack([entry[1] for entry in candidates])
    best = values[choice, np.arange(height)[:, None], np.arange(width)[None, :]]
    cost = np.min(costs, axis=0)
    return best, np.isfinite(cost), cost, choice, names


def propagate_references(source, forbidden, selected, fallback, models, *,
                         min_donors=3, max_spread=10., checkpoint=None):
    """Lower-level bounded-batch propagation; run() performs input validation."""
    frames, height, width, _ = source.shape
    base = _grid(height, width)
    blocked = forbidden | selected | (source[:, :, :, 3] < 255)
    rgb = source[:, :, :, :3].astype(np.float32)
    rgb[blocked] = 0
    output, contributed = fallback.copy(), np.zeros(selected.shape, bool)
    reports = []
    for index in range(frames):
        if checkpoint:
            checkpoint('reference', index, frames)
        if not selected[index].any():
            reports.append({'frame': index, 'selected': 0, 'contributed': 0, 'donor_frames': []})
            continue
        values, masks, costs, donors = [], [], [], []
        selected_models = {name: 0 for name in models}
        for direction in (-1, 1):
            states = {name: (base.copy(), np.ones((height, width), bool), index) for name in models}
            for donor in range(index + direction, frames if direction > 0 else -1, direction):
                candidates = []
                for name, (flows, confidence) in models.items():
                    if name not in states:
                        continue
                    coordinates, path_ok, previous = states[name]
                    key = previous, donor
                    if key not in flows:
                        del states[name]
                        continue
                    flow, quality = flows[key], confidence.get(key)
                    if (not isinstance(flow, np.ndarray) or flow.dtype != np.float32
                            or flow.shape != (height, width, 2) or not np.isfinite(flow).all()
                            or not isinstance(quality, np.ndarray) or quality.dtype != np.bool_
                            or quality.shape != (height, width)):
                        raise ValueError('REFERENCE_MAP_CONTRACT_INVALID')
                    path_ok &= _remap(quality.astype(np.float32), coordinates) >= 1.
                    coordinates += _remap(flow, coordinates)
                    path_ok &= _inside(coordinates, height, width)
                    states[name] = coordinates, path_ok, donor
                    valid = path_ok & (_remap((~blocked[donor]).astype(np.float32), coordinates) >= 1.)
                    candidates.append((name, _remap(rgb[donor], coordinates), valid))
                if not states:
                    break
                best, valid, context_cost, choice, names = choose_reference(
                    rgb[index], candidates, ~blocked[index])
                for number, name in enumerate(names):
                    selected_models[name] += int((valid & selected[index] & (choice == number)).sum())
                values.append(best)
                masks.append(valid)
                costs.append(context_cost + .1 * abs(donor - index))
                donors.append(donor)
        if not donors:
            reports.append({'frame': index, 'selected': int(selected[index].sum()),
                            'contributed': 0, 'donor_frames': [], 'selected_model_candidates': selected_models})
            continue
        bank, valid, context_cost = np.stack(values), np.stack(masks), np.stack(costs)
        del values, masks, costs
        bank[~valid] = np.nan
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='All-NaN slice encountered')
            median = np.nanmedian(bank, axis=0)
            deviation = np.nanmax(np.abs(bank - median), axis=3)
        agreeing = valid & (deviation <= max_spread)
        eligible = (agreeing.sum(axis=0) >= min_donors) & selected[index]
        # There is one entry per frame ID, so two models never manufacture two
        # independent agreeing observations from the same underlying frame.
        cost = np.where(agreeing, context_cost + .05 * deviation, np.inf)
        choice = np.argmin(cost, axis=0)
        best = bank[choice, np.arange(height)[:, None], np.arange(width)[None, :]]
        components, labels, stats, _ = cv2.connectedComponentsWithStats(eligible.astype(np.uint8), 8)
        for label in range(1, components):
            if stats[label, cv2.CC_STAT_AREA] < 64:
                eligible[labels == label] = False
        weight = np.minimum(cv2.distanceTransform(eligible.astype(np.uint8), cv2.DIST_L2, 3) / 3, 1)
        use = eligible & np.isfinite(best).all(axis=2)
        output[index, use, :3] = np.rint(np.clip(
            best[use] * weight[use, None] + fallback[index, use, :3] * (1 - weight[use, None]),
            0, 255)).astype(np.uint8)
        contributed[index] = use
        reports.append({'frame': index, 'selected': int(selected[index].sum()),
                        'contributed': int(use.sum()), 'donor_frames': donors,
                        'selected_model_candidates': selected_models})
    return output, contributed, reports


def run(source, forbidden, selected, fallback, *, scene_cuts=(), min_donors=3,
        max_spread=10., budget=1536 * 1024**2, checkpoint=None):
    frames, height, width = validate_inputs(source, forbidden, selected, fallback, budget)
    if (type(min_donors) is not int or not 1 <= min_donors <= 64
            or type(max_spread) not in {int, float} or not np.isfinite(max_spread)
            or not 0 <= max_spread <= 64):
        raise ValueError('REFERENCE_DONOR_OPTIONS_INVALID')
    if (any(type(i) is not int or not 0 < i < frames for i in scene_cuts)
            or len(set(scene_cuts)) != len(scene_cuts)):
        raise ValueError('REFERENCE_SCENE_CUT_INVALID')
    if checkpoint is not None and not callable(checkpoint):
        raise ValueError('REFERENCE_CHECKPOINT_INVALID')
    owned = array_bound(frames, height, width)
    if owned > budget:
        raise ValueError('REFERENCE_OWNED_ARRAY_BUDGET_EXCEEDED')
    if checkpoint:
        checkpoint('prepare', 0, frames)
    excluded = forbidden | selected
    camera, camera_quality, camera_report = estimate_camera(
        source, excluded, scene_cuts=scene_cuts, checkpoint=checkpoint)
    dense, dense_quality, dense_report = estimate(
        source, excluded, scene_cuts=scene_cuts, checkpoint=checkpoint)
    output, used, per_frame = propagate_references(
        source, excluded, selected, fallback,
        {'camera': (camera, camera_quality), 'dense': (dense, dense_quality)},
        min_donors=min_donors, max_spread=max_spread, checkpoint=checkpoint)
    if (not np.array_equal(output[~selected], source[~selected])
            or not np.array_equal(output[:, :, :, 3], source[:, :, :, 3])):
        raise ValueError('REFERENCE_PRESERVATION_FAILED')
    return output, used, {
        'algorithm': ALGORITHM, 'frames': frames, 'width': width, 'height': height,
        'scene_cuts': list(scene_cuts), 'min_distinct_donor_frames': min_donors,
        'max_spread': max_spread, 'context_window_pixels': 65,
        'minimum_context_pixels': 64, 'maximum_context_rgb_mae': 12,
        'owned_array_estimate_bytes': owned,
        'budget_scope': 'conservative-owned-array-estimate-excludes-inputs-opencv-internals-total-process-ram',
        'camera_edges': camera_report, 'dense_edges': dense_report, 'per_frame': per_frame,
        'selected_pixels': int(selected.sum()), 'contributed_pixels': int(used.sum()),
        'availability_is_not_accuracy': True, 'outside_mask_changed_pixels': 0,
        'source_alpha_exact': True, 'hidden_motion_verified': False,
        'full_video_temporal_quality_accepted': False, 'product_integrated': False}
