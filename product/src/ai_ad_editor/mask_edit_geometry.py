"""Bounded, editable mask geometry on an explicitly bound CFR pixel grid."""
from __future__ import annotations

from bisect import bisect_right
import copy
import math


def finite(value):
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        return False


def checked(value, binding):
    if (not isinstance(value, dict) or set(value) - {'version', 'coordinate_space', 'mask', 'scene_cut_frames', 'operations', 'samples_per_axis'}
            or value.get('version') != '1.0.0' or value.get('coordinate_space') != 'normalized-output'
            or value.get('mask') != binding):
        raise ValueError('MASK_EDIT_BINDING_INVALID')
    # Dict equality alone admits bools for integers; require exact binding types.
    if any(type(value['mask'][k]) is not type(v) for k, v in binding.items()):
        raise ValueError('MASK_EDIT_BINDING_INVALID')
    cuts = value.get('scene_cut_frames')
    if (not isinstance(cuts, list) or any(type(i) is not int or not 0 < i < binding['frames'] for i in cuts)
            or cuts != sorted(set(cuts))):
        raise ValueError('MASK_EDIT_SCENE_CUT_INVALID')
    samples = value.get('samples_per_axis', 1)
    if type(samples) is not int or samples not in {1, 2, 4}:
        raise ValueError('MASK_EDIT_SAMPLING_INVALID')
    operations = value.get('operations')
    if not isinstance(operations, list) or not 1 <= len(operations) <= 64:
        raise ValueError('MASK_EDIT_OPERATION_COUNT_INVALID')
    names, total_keys, total_points = set(), 0, 0
    for op in operations:
        required = {'id', 'mode', 'type', 'start_frame', 'end_frame', 'interpolation', 'keyframes'}
        if (not isinstance(op, dict) or not required <= set(op) or set(op) - required - {'feather_pixels', 'opacity'}
                or not isinstance(op['id'], str) or not 1 <= len(op['id']) <= 64 or op['id'] in names
                or any(not (c.isascii() and (c.isalnum() or c in '_-')) for c in op['id'])
                or op['mode'] not in {'add', 'subtract', 'intersect', 'replace'}
                or op['type'] not in {'rectangle', 'ellipse', 'polygon', 'brush'}
                or op['interpolation'] not in {'hold', 'linear'}):
            raise ValueError('MASK_EDIT_OPERATION_INVALID')
        names.add(op['id'])
        start, end = op['start_frame'], op['end_frame']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= binding['frames']:
            raise ValueError('MASK_EDIT_RANGE_INVALID')
        feather, opacity = op.get('feather_pixels', 0), op.get('opacity', 1)
        if not finite(feather) or not 0 <= feather <= 64 or not finite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('MASK_EDIT_COVERAGE_INVALID')
        keys = op['keyframes']
        if not isinstance(keys, list) or not 1 <= len(keys) <= 256:
            raise ValueError('MASK_EDIT_KEYFRAMES_INVALID')
        previous, points_count = -1, None
        for key in keys:
            fields = {'frame', 'box'} if op['type'] in {'rectangle', 'ellipse'} else {'frame', 'points'}
            if op['type'] == 'brush':
                fields.add('radius_pixels')
            if (not isinstance(key, dict) or set(key) != fields or type(key['frame']) is not int
                    or not start <= key['frame'] < end or key['frame'] <= previous):
                raise ValueError('MASK_EDIT_KEYFRAMES_INVALID')
            previous = key['frame']
            if 'box' in fields:
                box = key['box']
                if (not isinstance(box, list) or len(box) != 4 or any(not finite(v) or not 0 <= v <= 1 for v in box)
                        or not box[0] < box[2] or not box[1] < box[3]):
                    raise ValueError('MASK_EDIT_BOX_INVALID')
                total_points += 2
            else:
                points = key['points']
                if (not isinstance(points, list) or not (3 if op['type'] == 'polygon' else 1) <= len(points) <= 256
                        or any(not isinstance(p, list) or len(p) != 2 or any(not finite(v) or not 0 <= v <= 1 for v in p) for p in points)):
                    raise ValueError('MASK_EDIT_POINTS_INVALID')
                if op['type'] == 'polygon':
                    a = points[0]
                    b = max(points, key=lambda p: (p[0]-a[0])**2+(p[1]-a[1])**2)
                    if not any(abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])) > 1e-12 for c in points):
                        raise ValueError('MASK_EDIT_POLYGON_DEGENERATE')
                if op['interpolation'] == 'linear' and points_count is not None and len(points) != points_count:
                    raise ValueError('MASK_EDIT_LINEAR_TOPOLOGY_INVALID')
                points_count = len(points)
                total_points += len(points)
                if 'radius_pixels' in fields and (not finite(key['radius_pixels']) or not .5 <= key['radius_pixels'] <= 8192):
                    raise ValueError('MASK_EDIT_BRUSH_RADIUS_INVALID')
        if keys[0]['frame'] != start or any(cut not in {k['frame'] for k in keys} for cut in cuts if start < cut < end):
            raise ValueError('MASK_EDIT_RESET_KEYFRAME_REQUIRED')
        total_keys += len(keys)
    if total_keys > 1024 or total_points > 16384:
        raise ValueError('MASK_EDIT_GEOMETRY_BUDGET_EXCEEDED')
    result = copy.deepcopy(value)
    result['samples_per_axis'] = samples
    for op in result['operations']:
        op.setdefault('feather_pixels', 0)
        op.setdefault('opacity', 1)
    return result


def geometry_at(op, frame, cuts=()):
    keys = op['keyframes']
    left = bisect_right([k['frame'] for k in keys], frame) - 1
    a = keys[max(0, left)]
    if left == len(keys)-1 or op['interpolation'] == 'hold' or keys[left+1]['frame'] in cuts:
        return a
    b = keys[left+1]
    ratio = (frame-a['frame'])/(b['frame']-a['frame'])
    def mix(x, y):
        if isinstance(x, list):
            return [mix(v, w) for v, w in zip(x, y)]
        return x + (y-x)*ratio
    return {name: frame if name == 'frame' else mix(a[name], b[name]) for name in a}


def bounds(kind, geometry, width, height):
    if kind in {'rectangle', 'ellipse'}:
        l, t, r, b = geometry['box']
        return l*width, t*height, r*width, b*height
    points = geometry['points']
    radius = geometry.get('radius_pixels', 0)
    return (min(p[0] for p in points)*width-radius, min(p[1] for p in points)*height-radius,
            max(p[0] for p in points)*width+radius, max(p[1] for p in points)*height+radius)


def work_estimate(edits):
    binding = edits['mask']; width, height = binding['width'], binding['height']
    work = 0
    for op in edits['operations']:
        boxes = [bounds(op['type'], k, width, height) for k in op['keyframes']]
        l, t = max(0, math.floor(min(b[0] for b in boxes))), max(0, math.floor(min(b[1] for b in boxes)))
        r, b = min(width, math.ceil(max(b[2] for b in boxes))), min(height, math.ceil(max(b[3] for b in boxes)))
        edges = max((len(k.get('points', [])) for k in op['keyframes']), default=1) or 1
        if op['type'] == 'polygon' and op.get('feather_pixels', 0):
            edges *= 2
        work += max(0, r-l)*max(0, b-t)*(op['end_frame']-op['start_frame'])*edges*edits['samples_per_axis']**2
        # Full-buffer comparisons/composition for every operation are also work.
        work += width*height*(op['end_frame']-op['start_frame'])
    return work


def segment_distance(x, y, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    denominator = dx*dx + dy*dy
    fraction = max(0., min(1., ((x-a[0])*dx+(y-a[1])*dy)/denominator)) if denominator else 0.
    return math.hypot(x-a[0]-fraction*dx, y-a[1]-fraction*dy)


def raster(op, geometry, width, height, samples, checkpoint=None):
    out = bytearray(width*height)
    l, t, r, b = bounds(op['type'], geometry, width, height)
    x0, y0, x1, y1 = max(0, math.floor(l)), max(0, math.floor(t)), min(width, math.ceil(r)), min(height, math.ceil(b))
    feather, opacity, kind = op.get('feather_pixels', 0), op.get('opacity', 1), op['type']
    if kind in {'polygon', 'brush'}:
        points = [(p[0]*width, p[1]*height) for p in geometry['points']]
        segments = list(zip(points, points[1:]+points[:1])) if kind == 'polygon' else list(zip(points, points[1:])) or [(points[0], points[0])]
    def coverage(x, y):
        if kind == 'rectangle':
            if not l <= x < r or not t <= y < b:
                return 0.
            distance = min(x-l, r-x, y-t, b-y)
        elif kind == 'ellipse':
            radius = math.hypot((x-(l+r)/2)/((r-l)/2), (y-(t+b)/2)/((b-t)/2))
            if radius > 1:
                return 0.
            distance = min(r-l, b-t)/2*(1-radius)
        elif kind == 'polygon':
            inside = False
            for a, z in segments:
                if (a[1] > y) != (z[1] > y) and x < (z[0]-a[0])*(y-a[1])/(z[1]-a[1])+a[0]:
                    inside = not inside
            if not inside:
                return 0.
            distance = min(segment_distance(x, y, a, z) for a, z in segments) if feather else 1.
        else:
            distance = geometry['radius_pixels'] - min(segment_distance(x, y, a, z) for a, z in segments)
            if distance < 0:
                return 0.
        return min(1., distance/feather) if feather else 1.
    for y in range(y0, y1):
        if checkpoint and (y-y0) % 8 == 0:
            checkpoint()
        for x in range(x0, x1):
            value = sum(coverage(x+(sx+.5)/samples, y+(sy+.5)/samples)
                        for sy in range(samples) for sx in range(samples))/(samples*samples)
            out[y*width+x] = int(value*opacity*255+.5)
    return out


def edit_frame(base, edits, frame, checkpoint=None):
    width, height = edits['mask']['width'], edits['mask']['height']
    if len(base) != width*height:
        raise ValueError('MASK_EDIT_FRAME_SIZE_INVALID')
    out = bytearray(base)
    active = []
    for op in edits['operations']:
        if not op['start_frame'] <= frame < op['end_frame']:
            continue
        if checkpoint:
            checkpoint()
        shape = raster(op, geometry_at(op, frame, edits['scene_cut_frames']), width, height,
                       edits['samples_per_axis'], checkpoint)
        mode = op['mode']
        if mode == 'replace':
            out = shape
        else:
            for index, value in enumerate(shape):
                if checkpoint and index % 8192 == 0:
                    checkpoint()
                if mode == 'add':
                    out[index] = max(out[index], value)
                elif mode == 'subtract':
                    out[index] = min(out[index], 255-value)
                else:
                    out[index] = min(out[index], value)
        active.append(op['id'])
    return out, {'frame': frame, 'active_operations': active,
                 'changed_pixels': sum(a != b for a, b in zip(out, base)),
                 'selected_pixels_gt127': sum(a > 127 for a in out)}
