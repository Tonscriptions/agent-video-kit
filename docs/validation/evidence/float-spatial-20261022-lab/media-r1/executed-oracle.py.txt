"""Original mean-filter recipe and explicit dense tap/index mathematics.

No product color, automation, filter, padding or sum implementation is imported.
"""
from functools import lru_cache
import math
import numpy as np

METHODS = ('average', 'box', 'horizontal', 'RGB_only', 'premult_headroom')
SIGNAL = {'primaries': 'bt709', 'transfer': 'bt709-oetf'}


def key(prop, left, right, mode='linear', controls=None):
    first = {'at_tick': 0, 'value': left, 'interpolation': mode}
    if controls is not None: first['control_points'] = controls
    return {'property': prop, 'keyframes': [first, {'at_tick': 36000, 'value': right, 'interpolation': 'linear'}]}


def effects(method):
    p = {'input_signal': dict(SIGNAL), 'output_signal': dict(SIGNAL), 'intensity': .2}
    tracks = [key('intensity', .2, .85, 'ease_in_out')]
    kind = 'avgblur'
    if method == 'average':
        p.update(radius=2); tracks.append(key('radius', 2, 10, 'ease_in'))
    elif method == 'box':
        kind = 'boxblur'; p.update(radius=3, power=3)
        tracks.append(key('radius', 3, 9, 'bezier', [.2, .05, .8, .95]))
    elif method == 'horizontal':
        p.update(radius_x=4, radius_y=0); tracks.append(key('radius_x', 4, 16, 'ease_out'))
    elif method == 'RGB_only':
        kind = 'boxblur'; p.update(radius=6, power=2, planes=7); tracks.append(key('radius', 6, 12, 'hold'))
    else: p.update(radius=8, alpha_mode='premultiplied')
    blur = {'type': kind, 'parameters': p, 'keyframes': tracks}
    left, right = (2.7, 3.) if method == 'premult_headroom' else (.15, .45)
    exposure = {'type': 'exposure', 'parameters': {'amount': left, 'black': 0}, 'keyframes': [key('amount', left, right, 'ease_in')]}
    return [exposure, blur] if method == 'premult_headroom' else [blur, exposure]


def decode(rgb):
    a = np.abs(rgb)
    return np.where(a < .081, rgb/4.5, np.sign(rgb)*((a+.099)/1.099)**(1/.45)).astype(np.float32)


def encode(rgb):
    a = np.abs(rgb)
    return np.where(a < .018, rgb*4.5, np.sign(rgb)*(1.099*a**.45-.099)).astype(np.float32)


def timing(p):
    roots = np.roots([-.8, 1.2, .6, -p])
    u = next(float(v.real) for v in roots if abs(v.imag) < 1e-10 and -1e-12 <= v.real <= 1+1e-12)
    return .15*(1-u)**2*u+2.85*(1-u)*u*u+u**3


@lru_cache(maxsize=64)
def axis_matrix(length, radius, boundary, power):
    whole = math.floor(radius); fraction = radius-whole
    taps = [(offset, 1.) for offset in range(-whole, whole+1)]
    if fraction: taps.extend([(-whole-1, fraction), (whole+1, fraction)])
    matrix = np.zeros((length, length), np.float64)
    for target in range(length):
        for offset, weight in taps:
            source = target+offset
            if boundary == 'edge': source = min(length-1, max(0, source))
            else:
                source %= 2*length
                if source >= length: source = 2*length-1-source
            matrix[target, source] += weight/(2*radius+1)
    return np.linalg.matrix_power(matrix, power)


def grade(encoded, alpha, method, p):
    rx = 2+8*p*p if method == 'average' else 3+6*timing(p) if method == 'box' else 4+12*(2*p-p*p) if method == 'horizontal' else 6 if method == 'RGB_only' else 8
    ry = 0 if method == 'horizontal' else rx
    box = method in ('box', 'RGB_only'); boundary = 'symmetric' if box else 'edge'
    power = 3 if method == 'box' else 2 if method == 'RGB_only' else 1
    data = np.concatenate((encoded, alpha), axis=2).astype(np.float64)
    if method == 'premult_headroom': data[..., :3] *= data[..., 3:4]
    y = axis_matrix(data.shape[0], float(ry), boundary, power)
    x = axis_matrix(data.shape[1], float(rx), boundary, power)
    result = np.einsum('ij,jkc,lk->ilc', y, data, x, optimize=True)
    if method == 'premult_headroom':
        positive = result[..., 3] > 0
        np.divide(result[..., :3], result[..., 3:4], out=result[..., :3], where=positive[..., None])
        result[..., :3][~positive] = 0
    if method == 'RGB_only': result[..., 3:4] = alpha
    return result.astype(np.float32)


def expected_rgb(planes, indices):
    results = []
    q = (np.array([16, 32, 64], np.float64)/255).astype(np.float32).astype(np.float64)
    background = np.where(q <= .04045, q/12.92, ((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method = METHODS[index//4]; p = (index % 4)/4
        eased = 2*p*p if p < .5 else 1-(-2*p+2)**2/2
        strength = .2+.65*eased
        left, right = (2.7, 3.) if method == 'premult_headroom' else (.15, .45)
        amount = np.float32(left+(right-left)*p*p)
        inverse = np.float32(2.**(-float(amount))); gain = np.float32(1/float(inverse))
        expose = lambda v: (v*gain).astype(np.float32)
        values = np.moveaxis(planes[index, [2, 0, 1]], 0, -1).astype(np.float32)/np.float32(65535)
        alpha = planes[index, 3].astype(np.float32)[..., None]/np.float32(65535)
        linear = decode(values.astype(np.float64)); before = expose(linear) if method == 'premult_headroom' else linear
        mapped = grade(encode(before.astype(np.float64)), alpha, method, p)
        recovered = decode(mapped[..., :3].astype(np.float64))
        mixed = (before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        coverage = (alpha.astype(np.float64)*(1-strength)+mapped[..., 3:4].astype(np.float64)*strength).astype(np.float32).astype(np.float64)
        if method != 'premult_headroom': mixed = expose(mixed)
        results.append((mixed.astype(np.float64)*coverage+background*(1-coverage)).astype(np.float32))
    return np.stack(results)
