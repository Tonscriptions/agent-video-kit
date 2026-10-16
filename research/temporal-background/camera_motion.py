"""Observed-background camera registration for local repair research.

A similarity transform is a candidate for rigid background, not a verified
description of an occluded or deforming surface. No selected RGB enters LK.
"""
from __future__ import annotations

import cv2
import numpy as np

from flow_core import _grid, _inside, _remap


def fit_similarity(first, second, height, width):
    """Robustly fit observed point pairs; reject weak or implausible geometry."""
    if (not isinstance(first, np.ndarray) or not isinstance(second, np.ndarray)
            or first.shape != second.shape or first.ndim != 2
            or first.shape[1] != 2 or not np.isfinite(first).all()
            or not np.isfinite(second).all()):
        raise ValueError('CAMERA_POINT_PAIRS_INVALID')
    report = {'tracks': len(first), 'inliers': 0, 'status': 'insufficient-tracks'}
    if len(first) < 12:
        return None, report
    matrix, inliers = cv2.estimateAffinePartial2D(
        first, second, method=cv2.RANSAC, ransacReprojThreshold=.8,
        maxIters=5000, confidence=.999, refineIters=20)
    if matrix is None or inliers is None or not np.isfinite(matrix).all():
        report['status'] = 'fit-rejected'
        return None, report
    accepted = inliers[:, 0] != 0
    count = int(accepted.sum())
    report.update(inliers=count, inlier_fraction=count / len(first))
    area = float(cv2.contourArea(cv2.convexHull(first[accepted].astype(np.float32)))) if count >= 3 else 0.
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    angle = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    report.update(inlier_hull_fraction=area / (height * width), scale=scale, rotation_degrees=angle)
    if count < 12 or count / len(first) < .35 or area < height * width * .03:
        report['status'] = 'insufficient-spatial-support'
        return None, report
    if (not .8 <= scale <= 1.25 or abs(angle) > 15
            or np.linalg.norm(matrix[:, 2]) > 64 or np.linalg.det(matrix[:, :2]) <= 0):
        report['status'] = 'motion-out-of-profile'
        return None, report
    value = np.vstack([matrix, [0., 0., 1.]])
    report.update(status='estimated', matrix=value.tolist())
    return value, report


def estimate_camera(source, forbidden, *, scene_cuts=(), checkpoint=None):
    """Lower-level estimator; caller must validate arrays, cuts and budget first."""
    frames, height, width, _ = source.shape
    base = _grid(height, width)
    blocked = forbidden | (source[:, :, :, 3] < 255)
    grey, safe = [], []
    for image, mask in zip(source, blocked):
        value = cv2.cvtColor(np.ascontiguousarray(image[:, :, :3]), cv2.COLOR_RGB2GRAY)
        value[mask] = 0
        grey.append(value)
        safe.append(cv2.erode((~mask).astype(np.uint8), np.ones((33, 33), np.uint8),
                             borderType=cv2.BORDER_CONSTANT, borderValue=0))
    flows, confidence, reports = {}, {}, []
    for index in range(frames - 1):
        if checkpoint:
            checkpoint('camera', index, frames - 1)
        report = {'from': index, 'to': index + 1}
        if index + 1 in scene_cuts:
            reports.append(dict(report, status='explicit-scene-cut'))
            continue
        points = cv2.goodFeaturesToTrack(
            grey[index], maxCorners=1600, qualityLevel=.005,
            minDistance=5, mask=safe[index], blockSize=5)
        if points is None or len(points) < 12:
            reports.append(dict(report, status='insufficient-features'))
            continue
        options = dict(winSize=(21, 21), maxLevel=2,
                       criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, .01))
        tracked, forward_ok, _ = cv2.calcOpticalFlowPyrLK(
            grey[index], grey[index + 1], points, None, **options)
        if tracked is None or forward_ok is None or not np.isfinite(tracked).all():
            reports.append(dict(report, status='forward-tracking-rejected'))
            continue
        returned, backward_ok, _ = cv2.calcOpticalFlowPyrLK(
            grey[index + 1], grey[index], tracked, None, **options)
        if returned is None or backward_ok is None or not np.isfinite(returned).all():
            reports.append(dict(report, status='backward-tracking-rejected'))
            continue
        first, second = points[:, 0], tracked[:, 0]
        rounded = np.rint(second).astype(np.int32)
        inside = ((rounded[:, 0] >= 0) & (rounded[:, 0] < width)
                  & (rounded[:, 1] >= 0) & (rounded[:, 1] < height))
        good = ((forward_ok[:, 0] != 0) & (backward_ok[:, 0] != 0)
                & (np.linalg.norm(returned[:, 0] - first, axis=1) < .5) & inside)
        ids = np.flatnonzero(inside)
        good[ids] &= safe[index + 1][rounded[ids, 1], rounded[ids, 0]] != 0
        matrix, fit = fit_similarity(first[good], second[good], height, width)
        reports.append(dict(report, **fit))
        if matrix is None:
            continue
        inverse = np.linalg.inv(matrix)
        for a, b, transform in [(index, index + 1, matrix), (index + 1, index, inverse)]:
            coordinates = cv2.perspectiveTransform(base, transform).astype(np.float32)
            known = ((~blocked[a]) & _inside(coordinates, height, width)
                     & (_remap((~blocked[b]).astype(np.float32), coordinates) >= 1.))
            difference = np.mean(np.abs(source[a, :, :, :3].astype(np.float32)
                                      - _remap(source[b, :, :, :3], coordinates).astype(np.float32)), axis=2)
            count = cv2.boxFilter(known.astype(np.float32), -1, (65, 65), normalize=False)
            support = cv2.boxFilter((known & (difference <= 12)).astype(np.float32), -1,
                                    (65, 65), normalize=False)
            flows[a, b] = coordinates - base
            confidence[a, b] = (support >= 64) & (support >= count * .65)
    return flows, confidence, reports
