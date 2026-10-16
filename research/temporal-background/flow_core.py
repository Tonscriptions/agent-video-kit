"""Experimental observed-background propagation; not a production repair engine.

Inputs are already aligned CFR RGBA frames and Boolean output-space masks.
Occluded flow is extrapolated, so forward/backward agreement is a rejection
heuristic and must never be presented as proof of correct hidden geometry.
"""
from __future__ import annotations

import warnings
import cv2
import numpy as np


ALGORITHM = 'erased-background-dis-ns-flow-nearest-agreeing-reference-v1'


def array_bound(frames, height, width):
    return height * width * (128 * frames + 1024)


def validate_inputs(source, forbidden, selected, fallback, budget):
    if not isinstance(source, np.ndarray) or source.dtype != np.uint8 or source.ndim != 4 or source.shape[3] != 4:
        raise ValueError('FLOW_SOURCE_RGBA_INVALID')
    frames, height, width, _ = source.shape
    if not 2 <= frames <= 65 or min(height, width) < 16 or height * width > 1_048_576:
        raise ValueError('FLOW_RASTER_OR_FRAME_BUDGET')
    for mask in (forbidden, selected):
        if not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.shape != source.shape[:3]:
            raise ValueError('FLOW_BOOLEAN_MASK_INVALID')
    if not isinstance(fallback, np.ndarray) or fallback.dtype != np.uint8 or fallback.shape != source.shape:
        raise ValueError('FLOW_FALLBACK_RGBA_INVALID')
    if type(budget) is not int or not 1 <= budget <= 2 * 1024**3 or array_bound(frames, height, width) > budget:
        raise ValueError('FLOW_OWNED_ARRAY_BUDGET_EXCEEDED')
    if not np.array_equal(source[:, :, :, 3], fallback[:, :, :, 3]) or not np.array_equal(source[~selected], fallback[~selected]):
        raise ValueError('FLOW_FALLBACK_CHANGED_UNSELECTED_OR_ALPHA')
    return frames, height, width


def _grid(height, width):
    y, x = np.indices((height, width), dtype=np.float32)
    return np.stack([x, y], axis=2)


def _remap(array, coordinates):
    return cv2.remap(array, coordinates[:, :, 0], coordinates[:, :, 1], cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _inside(coordinates, height, width):
    return ((coordinates[:, :, 0] >= 0) & (coordinates[:, :, 0] < width - 1)
            & (coordinates[:, :, 1] >= 0) & (coordinates[:, :, 1] < height - 1))


def estimate(source, forbidden, *, scene_cuts=(), checkpoint=None):
    """Infer adjacent bidirectional motion from erased, observed background only.

    Call validate_inputs before this lower-level function. A rejected edge is
    absent from the maps, preventing all propagation across that edge.
    """
    frames, height, width, _ = source.shape
    if any(type(i) is not int or not 0 < i < frames for i in scene_cuts) or len(set(scene_cuts)) != len(scene_cuts):
        raise ValueError('FLOW_SCENE_CUT_INVALID')
    blocked = forbidden | (source[:, :, :, 3] < 255)
    base = _grid(height, width)
    grey = []
    for frame, mask in zip(source, blocked):
        raw = cv2.cvtColor(np.ascontiguousarray(frame[:, :, :3]), cv2.COLOR_RGB2GRAY)
        raw[mask] = 0
        grey.append(cv2.inpaint(raw, mask.astype(np.uint8), 5, cv2.INPAINT_TELEA))
    flows, confidence, samples = {}, {}, []
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale(0)
    for index in range(frames - 1):
        if checkpoint: checkpoint('flow', index, frames - 1)
        if index + 1 in scene_cuts:
            samples.append({'from': index, 'to': index + 1, 'status': 'explicit-scene-cut'})
            continue
        if any(np.count_nonzero(~blocked[i]) < max(64, height * width // 100) for i in (index, index + 1)):
            samples.append({'from': index, 'to': index + 1, 'status': 'insufficient-observed-background'})
            continue
        pairs = [(index, index + 1), (index + 1, index)]
        raw_flows = {(a, b): dis.calc(grey[a], grey[b], None) for a, b in pairs}
        completed, qualities = {}, {}
        for a, b in pairs:
            flow = raw_flows[a, b]
            if flow.dtype != np.float32 or flow.shape != (height, width, 2) or not np.isfinite(flow).all():
                raise ValueError('FLOW_NATIVE_RESULT_INVALID')
            coordinates = base + flow
            known = (~blocked[a]) & (_remap((~blocked[b]).astype(np.float32), coordinates) >= 1.) & _inside(coordinates, height, width)
            fb = np.linalg.norm(flow + _remap(raw_flows[b, a], coordinates), axis=2)
            photometric = np.abs(grey[a].astype(np.float32) - _remap(grey[b], coordinates).astype(np.float32))
            known &= (fb <= 1.5) & (photometric <= 18) & (np.linalg.norm(flow, axis=2) <= 64)
            known = cv2.erode(known.astype(np.uint8), np.ones((3, 3), np.uint8)) != 0
            if np.count_nonzero(known) < max(64, height * width // 100):
                break
            hole = (~known).astype(np.uint8)
            value = np.stack([cv2.inpaint(np.where(known, flow[:, :, c], 0).astype(np.float32), hole, 5, cv2.INPAINT_NS) for c in range(2)], axis=2)
            if not np.isfinite(value).all(): raise ValueError('FLOW_COMPLETION_NONFINITE')
            completed[a, b] = value
            qualities[a, b] = cv2.distanceTransform(hole, cv2.DIST_L2, 3) <= 48
            samples.append({'from': a, 'to': b, 'status': 'estimated', 'observed_anchors': int(known.sum()),
                            'known_flow_median': np.median(flow[known], axis=0).tolist()})
        if len(completed) != 2:
            samples.append({'from': index, 'to': index + 1, 'status': 'insufficient-consistent-anchors'})
            continue
        flows.update(completed)
        confidence.update(qualities)
    for (a, b), flow in flows.items():
        coordinates = base + flow
        fb = np.linalg.norm(flow + _remap(flows[b, a], coordinates), axis=2)
        confidence[a, b] &= (fb <= 2) & _inside(coordinates, height, width)
    return flows, confidence, samples


def propagate(source, forbidden, selected, fallback, flows, confidence, *, min_donors=3,
              max_spread=10., checkpoint=None):
    """Use only observed, agreeing references; preserve fallback elsewhere.

    Extrapolated motion may still be wrong. The returned contributed-pixel mask
    is availability, not reconstruction correctness. Its interior feather also
    blends fallback RGB; it is not an exact observed-source copy guarantee.
    """
    if type(min_donors) is not int or not 1 <= min_donors <= 64 or type(max_spread) not in {int, float} or not np.isfinite(max_spread) or not 0 <= max_spread <= 64:
        raise ValueError('FLOW_DONOR_OPTIONS_INVALID')
    frames, height, width, _ = source.shape
    blocked = forbidden | selected | (source[:, :, :, 3] < 255)
    base = _grid(height, width)
    result = fallback.copy()
    contributed = np.zeros(selected.shape, bool)
    frame_metrics = []
    for index in range(frames):
        if checkpoint: checkpoint('propagate', index, frames)
        candidates, eligibility, donors = [], [], []
        for direction in (-1, 1):
            coordinates = base.copy()
            valid_path = np.ones((height, width), bool)
            previous = index
            for donor in range(index + direction, frames if direction > 0 else -1, direction):
                key = previous, donor
                if key not in flows: break
                flow, quality = flows[key], confidence.get(key)
                if not isinstance(flow, np.ndarray) or flow.dtype != np.float32 or flow.shape != (height, width, 2) or not np.isfinite(flow).all() or not isinstance(quality, np.ndarray) or quality.dtype != np.bool_ or quality.shape != (height, width):
                    raise ValueError('FLOW_MAP_CONTRACT_INVALID')
                valid_path &= _remap(quality.astype(np.float32), coordinates) >= 1.
                coordinates += _remap(flow, coordinates)
                valid_path &= _inside(coordinates, height, width)
                previous = donor
                valid = valid_path & (_remap((~blocked[donor]).astype(np.float32), coordinates) >= 1.)
                candidates.append(_remap(np.ascontiguousarray(source[donor, :, :, :3]).astype(np.float32), coordinates))
                eligibility.append(valid)
                donors.append(donor)
        if not donors:
            frame_metrics.append({'frame': index, 'selected': int(selected[index].sum()), 'contributed': 0, 'donor_frames': []})
            continue
        values = np.stack(candidates)
        valid = np.stack(eligibility)
        del candidates, eligibility
        values[~valid] = np.nan
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='All-NaN slice encountered')
            median = np.nanmedian(values, axis=0)
            deviation = np.nanmax(np.abs(values - median), axis=3)
            spread = np.nanmedian(deviation, axis=0)
        agreeing = valid & (deviation <= max_spread)
        enough = (agreeing.sum(axis=0) >= min_donors) & np.isfinite(spread) & (spread <= max_spread)
        cost = np.where(agreeing, np.array([abs(donor - index) for donor in donors], np.float32)[:, None, None] + deviation * .05, np.inf)
        choice = np.argmin(cost, axis=0)
        best = values[choice, np.arange(height)[:, None], np.arange(width)[None, :]]
        eligible = enough & selected[index]
        components, labels, stats, _ = cv2.connectedComponentsWithStats(eligible.astype(np.uint8), 8)
        for label in range(1, components):
            if stats[label, cv2.CC_STAT_AREA] < 64: eligible[labels == label] = False
        weight = np.minimum(cv2.distanceTransform(eligible.astype(np.uint8), cv2.DIST_L2, 3) / 3, 1)
        use = eligible & np.isfinite(best).all(axis=2)
        result[index, use, :3] = np.rint(np.clip(best[use] * weight[use, None] + fallback[index, use, :3] * (1 - weight[use, None]), 0, 255)).astype(np.uint8)
        contributed[index] = use
        frame_metrics.append({'frame': index, 'selected': int(selected[index].sum()), 'contributed': int(use.sum()), 'donor_frames': donors})
    return result, contributed, frame_metrics


def run(source, forbidden, selected, fallback, *, scene_cuts=(), min_donors=3,
        max_spread=10., budget=1024**3, checkpoint=None):
    frames, height, width = validate_inputs(source, forbidden, selected, fallback, budget)
    # Union explicitly removes selected colors from both motion and references.
    excluded = forbidden | selected
    flows, confidence, edges = estimate(source, excluded, scene_cuts=scene_cuts, checkpoint=checkpoint)
    output, used, metrics = propagate(source, excluded, selected, fallback, flows, confidence,
                                     min_donors=min_donors, max_spread=max_spread, checkpoint=checkpoint)
    if not np.array_equal(output[~selected], source[~selected]) or not np.array_equal(output[:, :, :, 3], source[:, :, :, 3]):
        raise ValueError('FLOW_PRESERVATION_FAILED')
    return output, used, {'algorithm': ALGORITHM, 'frames': frames, 'width': width, 'height': height,
                         'scene_cuts': list(scene_cuts), 'min_donors': min_donors, 'max_spread': max_spread,
                         'owned_array_estimate_bytes': array_bound(frames, height, width),
                         'budget_scope': 'conservative-owned-array-estimate-excludes-inputs-opencv-internals-total-process-ram',
                         'edges': edges, 'per_frame': metrics, 'contributed_pixels': int(used.sum()),
                         'selected_pixels': int(selected.sum()), 'outside_mask_changed_pixels': 0,
                         'source_alpha_exact': True, 'hidden_motion_verified': False,
                         'full_video_temporal_quality_accepted': False, 'product_integrated': False}
