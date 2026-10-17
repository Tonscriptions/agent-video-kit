"""Observed donor selection with bounded spatial and warped temporal penalties.

Research only. A reconstructed previous frame supplies a cost, never a donor,
and can be wrong. Observed-context scores do not establish hidden geometry.
"""
from __future__ import annotations

import warnings

import cv2
import numpy as np

from camera_motion import estimate_camera
from flow_core import _grid, _inside, _remap, estimate, validate_inputs
from reference_core import _context_error, choose_reference

ALGORITHM = 'observed-donor-coherence-with-motion-group-crossvalidation-v3'
SPATIAL_WEIGHT = .08
TEMPORAL_WEIGHT = .06
SWEEPS = 4


def array_bound(frames, height, width):
    return height * width * (256 * frames + 2048)


def _gather(bank, labels):
    height, width = labels.shape
    return bank[labels, np.arange(height)[:, None], np.arange(width)[None, :]]


def refine_labels(bank, unary, allowed, eligible, *, prior=None, prior_valid=None,
                  checkpoint=None, origin=(0, 0), groups=None):
    """Fixed red/black label refinements; no global-energy optimum is claimed.

    Neighbor labels are compared at the same pixel. Unsupported neighbor labels
    contribute no cost. Every selected label must still pass observed-source,
    distinct-frame and color-consensus admission from the caller.
    """
    if (bank.dtype != np.float32 or bank.ndim != 4 or bank.shape[-1] != 3
            or unary.shape != bank.shape[:3] or allowed.shape != unary.shape
            or allowed.dtype != np.bool_ or eligible.shape != bank.shape[1:3]
            or eligible.dtype != np.bool_ or not np.isfinite(bank[allowed]).all()
            or not np.isfinite(unary[allowed]).all()):
        raise ValueError('COHERENT_LABEL_CONTRACT_INVALID')
    if np.any(eligible & ~allowed.any(axis=0)):
        raise ValueError('COHERENT_LABEL_WITHOUT_DONOR')
    colors = np.nan_to_num(bank, nan=0., posinf=0., neginf=0.)
    cost = np.where(allowed, unary, np.inf).astype(np.float32)
    if (prior is None) != (prior_valid is None):
        raise ValueError('COHERENT_PRIOR_CONTRACT_INVALID')
    if prior is not None:
        if (prior.shape != bank.shape[1:] or prior.dtype != np.float32
                or prior_valid.shape != eligible.shape or prior_valid.dtype != np.bool_
                or not np.isfinite(prior).all()):
            raise ValueError('COHERENT_PRIOR_CONTRACT_INVALID')
        difference = np.minimum(np.mean(np.abs(colors - prior[None]), axis=3), 20.)
        cost += TEMPORAL_WEIGHT * difference * prior_valid[None]
    labels = np.argmin(cost, axis=0)
    y, x = np.indices(eligible.shape)
    changes = []
    for sweep in range(SWEEPS):
        if checkpoint:
            checkpoint('labels', sweep, SWEEPS)
        changed = 0
        for parity in (0, 1):
            value = cost.copy()
            for axis, offset in ((0, -1), (0, 1), (1, -1), (1, 1)):
                neighbor_labels = np.roll(labels, offset, axis=axis)
                support = np.roll(eligible, offset, axis=axis) & eligible
                if groups is not None:
                    support &= (np.roll(groups, offset, axis=axis) == groups) & (groups >= 0)
                if axis == 0:
                    support[0 if offset == 1 else -1, :] = False
                else:
                    support[:, 0 if offset == 1 else -1] = False
                neighbor_supported = _gather(allowed[:, :, :, None], neighbor_labels)[:, :, 0]
                support &= neighbor_supported
                neighbor_color = _gather(colors, neighbor_labels)
                penalty = np.minimum(np.mean(np.abs(colors - neighbor_color[None]), axis=3), 40.)
                value += (SPATIAL_WEIGHT / 4) * penalty * support[None]
            proposed = np.argmin(value, axis=0)
            active = eligible & ((x + y + sum(origin)) % 2 == parity)
            changed += int(np.count_nonzero(active & (proposed != labels)))
            labels[active] = proposed[active]
        changes.append(changed)
    return labels, {'label_changes_per_sweep': changes,
                    'spatial_weight': SPATIAL_WEIGHT, 'temporal_weight': TEMPORAL_WEIGHT,
                    'sweeps': SWEEPS, 'global_energy_optimum_proven': False}


def refine_region(bank, unary, allowed, eligible, *, prior, prior_valid, checkpoint=None, groups=None):
    """Run identical local updates in the active rectangle, preserving parity."""
    labels = np.argmin(np.where(allowed, unary, np.inf), axis=0)
    ys, xs = np.flatnonzero(eligible.any(axis=1)), np.flatnonzero(eligible.any(axis=0))
    if not len(ys):
        return labels, {'label_changes_per_sweep': [0] * SWEEPS, 'active_rectangle': None}
    y1, y2, x1, x2 = int(ys[0]), int(ys[-1])+1, int(xs[0]), int(xs[-1])+1
    crop = np.s_[y1:y2, x1:x2]
    result, report = refine_labels(bank[:, y1:y2, x1:x2], unary[:, y1:y2, x1:x2],
        allowed[:, y1:y2, x1:x2], eligible[crop], prior=prior[crop], prior_valid=prior_valid[crop],
        checkpoint=checkpoint, origin=(y1, x1), groups=None if groups is None else groups[crop])
    labels[crop] = result
    report['active_rectangle'] = [x1, y1, x2, y2]
    return labels, report


def observed_gate(source_rgb, known, bank, baseline_labels, candidate_labels, eligible, groups=None):
    """Use only changed, actually visible predictions for local crossvalidation.

    This is a rejection heuristic, not a bound on unobserved-region error.
    """
    before, after = _gather(bank, baseline_labels), _gather(bank, candidate_labels)
    visible = known & eligible & np.isfinite(before).all(axis=2) & np.isfinite(after).all(axis=2)
    visible &= np.any(before != after, axis=2)
    first, second = before - source_rgb, after - source_rgb
    groups = np.zeros(eligible.shape, np.int8) if groups is None else groups
    gate = np.zeros(eligible.shape, bool)
    for group in (0, 1):
        observed = visible & (groups == group)
        count = cv2.boxFilter(observed.astype(np.float32), -1, (65, 65),
                             normalize=False, borderType=cv2.BORDER_CONSTANT)
        def aggregate(values):
            return cv2.boxFilter(np.where(observed, values, 0).astype(np.float32), -1,
                (65, 65), normalize=False, borderType=cv2.BORDER_CONSTANT) / np.maximum(count, 1)
        before_mae, after_mae = aggregate(np.mean(np.abs(first), axis=2)), aggregate(np.mean(np.abs(second), axis=2))
        before_mse, after_mse = aggregate(np.mean(first ** 2, axis=2)), aggregate(np.mean(second ** 2, axis=2))
        gate |= (groups == group) & (count >= 64) & (after_mae <= before_mae - .1) & (after_mse <= before_mse * .99)
    return gate, {'changed_visible_pixels': int(visible.sum()), 'minimum_changed_visible_pixels': 64,
                  'visible_window_pixels': 65, 'required_visible_mae_improvement': .1,
                  'visible_mse_max_ratio': .99, 'unobserved_error_bound_proven': False}


def motion_groups(index, known, models, blocked=None):
    """Infer two observed residual-motion groups; ambiguous extrapolation abstains.

    Group IDs are local to this frame, never object identities. Training uses
    visible source locations only; hidden completed flow is merely assigned.
    """
    groups = np.full(known.shape, -1, np.int8)
    if 'dense' not in models or 'camera' not in models:
        return groups, {'status': 'missing-motion-model'}
    fields, support, observed_pairs = [], [], []
    for neighbor in (index-1, index+1):
        key = index, neighbor
        dense, dense_ok = models['dense']
        camera, camera_ok = models['camera']
        if key not in dense or key not in camera:
            continue
        fields.append((dense[key] - camera[key]) * (1 if neighbor > index else -1))
        support.append(dense_ok[key] & camera_ok[key])
        paired = support[-1] & known
        if blocked is not None:
            base = _grid(*known.shape)
            paired &= (_remap((~blocked[neighbor]).astype(np.float32), base+dense[key]) >= 1.)
            paired &= (_remap((~blocked[neighbor]).astype(np.float32), base+camera[key]) >= 1.)
        observed_pairs.append(paired)
    if not fields:
        return groups, {'status': 'no-common-motion-edge'}
    valid = np.logical_and.reduce(support)
    signature = np.mean(np.stack(fields), axis=0)
    samples = signature[np.logical_and.reduce(observed_pairs)]
    if len(samples) < 128:
        return groups, {'status': 'insufficient-visible-motion'}
    axis = int(np.argmax(np.var(samples, axis=0)))
    order = np.argsort(samples[:, axis])
    centers = samples[order[[len(order)//5, 4*len(order)//5]]].copy()
    for _ in range(8):
        assigned = np.argmin(np.sum((samples[:, None] - centers[None]) ** 2, axis=2), axis=1)
        counts = [int((assigned == k).sum()) for k in (0, 1)]
        if min(counts) < max(64, len(samples)//20):
            groups[valid] = 0
            return groups, {'status': 'single-supported-motion', 'visible_samples': len(samples)}
        centers = np.stack([np.median(samples[assigned == k], axis=0) for k in (0, 1)])
    separation = float(np.linalg.norm(centers[0] - centers[1]))
    if separation < .75:
        groups[valid] = 0
        return groups, {'status': 'single-residual-motion', 'center_separation': separation}
    distance = np.linalg.norm(signature[:, :, None, :] - centers[None, None], axis=3)
    resolved = valid & (np.abs(distance[:, :, 0] - distance[:, :, 1]) >= .25) & (distance.min(axis=2) <= 1.5)
    groups[resolved] = np.argmin(distance, axis=2)[resolved]
    return groups, {'status': 'two-residual-motion-groups', 'centers': centers.tolist(),
                    'visible_samples': len(samples), 'center_separation': separation,
                    'unresolved_pixels': int((groups < 0).sum()), 'surface_identity_proven': False}


def temporal_prior(index, source_rgb, blocked, output, contributed, models, base):
    """Warp prior reconstruction, rank geometry on unmodified visible RGB only."""
    height, width = blocked.shape[1:]
    values, valid_masks, own_contexts = [], [], []
    for flows, confidence in models.values():
        key = index, index - 1
        if key not in flows:
            continue
        coordinates = base + flows[key]
        path = confidence[key] & _inside(coordinates, height, width)
        observed = path & (_remap((~blocked[index - 1]).astype(np.float32), coordinates) >= 1.)
        valid = path & (_remap(contributed[index - 1].astype(np.float32), coordinates) >= 1.)
        own_contexts.append((~blocked[index]) & observed)
        valid_masks.append(valid)
        values.append((_remap(source_rgb[index - 1], coordinates),
                       _remap(output[index - 1, :, :, :3].astype(np.float32), coordinates)))
    if not values:
        return np.zeros((height, width, 3), np.float32), np.zeros((height, width), bool)
    common = np.logical_and.reduce(own_contexts)
    common_count = cv2.boxFilter(common.astype(np.float32), -1, (65, 65),
                                normalize=False, borderType=cv2.BORDER_CONSTANT)
    costs, usable = [], []
    for (observed_rgb, _), context, valid in zip(values, own_contexts, valid_masks):
        own_error, own_count = _context_error(source_rgb[index], observed_rgb, context)
        shared_error, _ = _context_error(source_rgb[index], observed_rgb, common)
        costs.append(np.where(common_count >= 64, shared_error, own_error))
        usable.append(valid & (own_count >= 64))
    costs, usable = np.stack(costs), np.stack(usable)
    if len(values) > 1:
        usable &= (common_count >= 64)[None] | (usable.sum(axis=0) == 1)[None]
    usable &= costs <= 12
    costs = np.where(usable, costs, np.inf)
    chosen = np.argmin(costs, axis=0)
    return _gather(np.stack([value[1] for value in values]), chosen), np.isfinite(costs.min(axis=0))


def propagate(source, forbidden, selected, fallback, models, *, min_donors=3,
              max_spread=10., checkpoint=None):
    frames, height, width, _ = source.shape
    base = _grid(height, width)
    blocked = forbidden | selected | (source[:, :, :, 3] < 255)
    rgb = source[:, :, :, :3].astype(np.float32)
    rgb[blocked] = 0
    output, contributed = fallback.copy(), np.zeros(selected.shape, bool)
    # Retain actual sampled observations, never feathered fallback/model RGB,
    # as the next frame's temporal penalty reference.
    observed_history = np.zeros(source.shape[:3] + (3,), np.float32)
    reports = []
    for index in range(frames):
        if checkpoint:
            checkpoint('reference', index, frames)
        info = {'frame': index, 'selected': int(selected[index].sum()),
                'contributed': 0, 'donor_frames': [], 'temporal_prior_pixels': 0}
        if not selected[index].any():
            reports.append(info)
            continue
        values, masks, costs, donors = [], [], [], []
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
                        raise ValueError('COHERENT_MAP_CONTRACT_INVALID')
                    path_ok &= _remap(quality.astype(np.float32), coordinates) >= 1.
                    coordinates += _remap(flow, coordinates)
                    path_ok &= _inside(coordinates, height, width)
                    states[name] = coordinates, path_ok, donor
                    valid = path_ok & (_remap((~blocked[donor]).astype(np.float32), coordinates) >= 1.)
                    candidates.append((name, _remap(rgb[donor], coordinates), valid))
                if not states:
                    break
                best, valid, context_cost, _, _ = choose_reference(rgb[index], candidates, ~blocked[index])
                values.append(best)
                masks.append(valid)
                costs.append(context_cost + .1 * abs(donor - index))
                donors.append(donor)
        if not donors:
            reports.append(info)
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
        components, labels, stats, _ = cv2.connectedComponentsWithStats(eligible.astype(np.uint8), 8)
        for label in range(1, components):
            if stats[label, cv2.CC_STAT_AREA] < 64:
                eligible[labels == label] = False
        prior, prior_valid = temporal_prior(index, rgb, blocked, observed_history, contributed, models, base)
        unary = context_cost + .05 * deviation
        baseline_labels = np.argmin(np.where(agreeing, unary, np.inf), axis=0)
        ring = cv2.dilate(selected[index].astype(np.uint8), np.ones((65, 65), np.uint8)) != 0
        optimize = (agreeing.sum(axis=0) >= min_donors) & (eligible | (ring & ~blocked[index]))
        groups, group_report = motion_groups(index, ~blocked[index], models, blocked=blocked)
        candidate_labels, label_report = refine_region(bank, unary, agreeing, optimize,
            prior=prior, prior_valid=prior_valid & optimize, checkpoint=checkpoint, groups=groups)
        gate, gate_report = observed_gate(rgb[index], ~blocked[index], bank,
            baseline_labels, candidate_labels, optimize, groups=groups)
        choice = baseline_labels.copy()
        choice[gate & eligible] = candidate_labels[gate & eligible]
        label_report.update(visible_crossvalidation=gate_report,
            motion_groups=group_report,
            coherent_changed_selected_pixels=int(np.count_nonzero(eligible & gate & (choice != baseline_labels))))
        best = _gather(bank, choice)
        weight = np.minimum(cv2.distanceTransform(eligible.astype(np.uint8), cv2.DIST_L2, 3) / 3, 1)
        use = eligible & np.isfinite(best).all(axis=2)
        output[index, use, :3] = np.rint(np.clip(
            best[use] * weight[use, None] + fallback[index, use, :3] * (1 - weight[use, None]),
            0, 255)).astype(np.uint8)
        contributed[index] = use
        observed_history[index, use] = best[use]
        info.update(contributed=int(use.sum()), donor_frames=donors,
                    temporal_prior_pixels=int(prior_valid.sum()), **label_report)
        reports.append(info)
    return output, contributed, reports


def run(source, forbidden, selected, fallback, *, scene_cuts=(), min_donors=3,
        max_spread=10., budget=1536 * 1024**2, checkpoint=None):
    frames, height, width = validate_inputs(source, forbidden, selected, fallback, budget)
    if (type(min_donors) is not int or not 1 <= min_donors <= 64
            or type(max_spread) not in {int, float} or not np.isfinite(max_spread)
            or not 0 <= max_spread <= 64 or any(type(i) is not int or not 0 < i < frames for i in scene_cuts)
            or len(set(scene_cuts)) != len(scene_cuts) or (checkpoint is not None and not callable(checkpoint))):
        raise ValueError('COHERENT_OPTIONS_INVALID')
    owned = array_bound(frames, height, width)
    if owned > budget:
        raise ValueError('COHERENT_OWNED_ARRAY_BUDGET_EXCEEDED')
    if checkpoint:
        checkpoint('prepare', 0, frames)
    excluded = forbidden | selected
    camera, camera_quality, camera_report = estimate_camera(source, excluded, scene_cuts=scene_cuts, checkpoint=checkpoint)
    dense, dense_quality, dense_report = estimate(source, excluded, scene_cuts=scene_cuts, checkpoint=checkpoint)
    output, used, per_frame = propagate(source, excluded, selected, fallback,
        {'camera': (camera, camera_quality), 'dense': (dense, dense_quality)},
        min_donors=min_donors, max_spread=max_spread, checkpoint=checkpoint)
    if (not np.array_equal(output[~selected], source[~selected])
            or not np.array_equal(output[:, :, :, 3], source[:, :, :, 3])):
        raise ValueError('COHERENT_PRESERVATION_FAILED')
    return output, used, {'algorithm': ALGORITHM, 'frames': frames, 'width': width, 'height': height,
        'scene_cuts': list(scene_cuts), 'min_distinct_donor_frames': min_donors,
        'max_spread': max_spread, 'owned_array_estimate_bytes': owned,
        'budget_scope': 'conservative-owned-array-estimate-excludes-inputs-opencv-internals-total-process-ram',
        'camera_edges': camera_report, 'dense_edges': dense_report, 'per_frame': per_frame,
        'selected_pixels': int(selected.sum()), 'contributed_pixels': int(used.sum()),
        'temporal_prior_is_cost_not_observation': True, 'availability_is_not_accuracy': True,
        'outside_mask_changed_pixels': 0, 'source_alpha_exact': True,
        'hidden_motion_verified': False, 'full_video_temporal_quality_accepted': False,
        'product_integrated': False}
