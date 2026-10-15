"""Deterministic motion/IoU association; no model loading or network calls."""
from __future__ import annotations

import math
from typing import Any


def decode_detections(rows: Any, width: int, height: int, resized: tuple[int, int], padding: tuple[int, int], *, threshold: float, classes: list[int], roi: dict[str, float]) -> list[dict[str, Any]]:
    """Undo integer letterboxing, using independent actual x/y resize ratios."""
    rw, rh = resized
    px, py = padding
    result = []
    for row in rows:
        if len(row) != 6:
            raise ValueError("YOLO_OUTPUT_SHAPE_INVALID")
        x1, y1, x2, y2, score, label = map(float, row)
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2, score, label)) or not 0 <= score <= 1 or label != int(label) or not 0 <= label < 80:
            raise ValueError("YOLO_OUTPUT_VALUE_INVALID")
        if score < threshold or int(label) not in classes:
            continue
        # Normalizing after inverse resizing cancels the original dimensions.
        left, right = max(0.0, (x1 - px) / rw), min(1.0, (x2 - px) / rw)
        top, bottom = max(0.0, (y1 - py) / rh), min(1.0, (y2 - py) / rh)
        if right <= left or bottom <= top:
            continue
        x, y = (left + right) / 2, (top + bottom) / 2
        if not roi['x'] <= x <= roi['x'] + roi['width'] or not roi['y'] <= y <= roi['y'] + roi['height']:
            continue
        result.append({'x': x, 'y': y, 'width': right - left, 'height': bottom - top, 'confidence': score, 'class_id': int(label)})
    return sorted(result, key=lambda d: (d['class_id'], d['x'], d['y'], -d['confidence']))


def iou(a: dict[str, float], b: dict[str, float]) -> float:
    left = max(a['x'] - a['width']/2, b['x'] - b['width']/2)
    right = min(a['x'] + a['width']/2, b['x'] + b['width']/2)
    top = max(a['y'] - a['height']/2, b['y'] - b['height']/2)
    bottom = min(a['y'] + a['height']/2, b['y'] + b['height']/2)
    intersection = max(0.0, right-left) * max(0.0, bottom-top)
    return intersection / max(1e-12, a['width']*a['height'] + b['width']*b['height'] - intersection)


def assignment(cost: list[list[float]]) -> list[tuple[int, int]]:
    """Rectangular Hungarian minimization, with deterministic tie breaking."""
    if not cost:
        return []
    n, m = len(cost), len(cost[0])
    if n > m or not m or any(len(row) != m for row in cost):
        raise ValueError('ASSIGNMENT_SHAPE_INVALID')
    u, v, p, way = [0.0]*(n+1), [0.0]*(m+1), [0]*(m+1), [0]*(m+1)
    for i in range(1, n+1):
        p[0], j0 = i, 0
        minimum, used = [float('inf')]*(m+1), [False]*(m+1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], float('inf'), 0
            for j in range(1, m+1):
                if not used[j]:
                    current = cost[i0-1][j-1] - u[i0] - v[j]
                    if current < minimum[j]:
                        minimum[j], way[j] = current, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(m+1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return sorted((p[j]-1, j-1) for j in range(1, m+1) if p[j])


class MotionTracker:
    """Two-stage detector association; deliberately has no appearance ReID."""
    def __init__(self, *, confidence: float, match_iou: float, max_gap_seconds: float, max_objects: int):
        self.confidence, self.match_iou = confidence, match_iou
        self.max_gap, self.max_objects = max_gap_seconds, max_objects
        self.tracks: list[dict[str, Any]] = []
        self.observations = 0

    @staticmethod
    def predict(track: dict[str, Any], at: float) -> dict[str, float]:
        frames = track['frames']
        result = dict(frames[-1])
        if len(frames) >= 2:
            last, previous = frames[-1], frames[-2]
            dt = last['at_seconds'] - previous['at_seconds']
            if dt > 0:
                horizon = min(at-last['at_seconds'], dt*3)
                for key in ('x', 'y'):
                    result[key] += (last[key]-previous[key]) / dt * horizon
        return result

    def update(self, detections: list[dict[str, Any]], at: float) -> None:
        active = [i for i, t in enumerate(self.tracks) if at-t['frames'][-1]['at_seconds'] <= self.max_gap + 1e-8]
        remaining_tracks = active[:]
        high = [i for i, d in enumerate(detections) if d['confidence'] >= self.confidence]
        low = [i for i, d in enumerate(detections) if d['confidence'] < self.confidence]
        matches: list[tuple[int, int]] = []
        for candidates in (high, low):
            costs = []
            for index in remaining_tracks:
                track = self.tracks[index]
                predicted = self.predict(track, at)
                values = []
                for j in candidates:
                    detection = detections[j]
                    overlap = iou(predicted, detection)
                    distance = math.hypot(predicted['x']-detection['x'], predicted['y']-detection['y'])
                    radius = max(predicted['width'], predicted['height'], detection['width'], detection['height']) * .75
                    admissible = track['class_id'] == detection['class_id'] and (overlap >= self.match_iou or distance <= radius)
                    values.append(1-overlap + distance*.1 if admissible else 1000.0)
                costs.append(values + [2.0]*len(remaining_tracks))
            paired = [(remaining_tracks[i], candidates[j]) for i, j in assignment(costs) if j < len(candidates) and costs[i][j] < 2.0]
            matches.extend(paired)
            used_tracks = {i for i, _ in paired}
            remaining_tracks = [i for i in remaining_tracks if i not in used_tracks]
        used = {j for _, j in matches}
        for i, j in matches:
            track = self.tracks[i]
            gap = at-track['frames'][-1]['at_seconds']
            track['max_observation_gap_seconds'] = max(track['max_observation_gap_seconds'], gap)
            track['frames'].append({'at_seconds': at, **detections[j]})
            self.observations += 1
        for j in high:
            if j in used:
                continue
            if len(self.tracks) >= self.max_objects:
                raise ValueError('YOLO_OBJECT_LIMIT_EXCEEDED')
            self.tracks.append({'object_id': f'obj_{len(self.tracks)+1:04d}', 'class_id': detections[j]['class_id'], 'frames': [{'at_seconds': at, **detections[j]}], 'max_observation_gap_seconds': 0.0})
            self.observations += 1
        if self.observations > 50_000:
            raise ValueError('YOLO_OBSERVATION_LIMIT_EXCEEDED')
