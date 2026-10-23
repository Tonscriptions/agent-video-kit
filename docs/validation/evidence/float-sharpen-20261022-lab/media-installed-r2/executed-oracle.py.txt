"""Original five-scene recipe and independent dense binomial/YUV mathematics.

No production colour, automation, convolution, kernel or padding function is imported.
"""
from functools import lru_cache
import math
import numpy as np

METHODS = ('luma', 'chroma', 'horizontal', 'coverage', 'headroom')
SIGNAL = {'primaries': 'bt709', 'transfer': 'bt709-oetf'}


def key(prop, left, right, mode='linear', controls=None):
    first = {'at_tick': 0, 'value': left, 'interpolation': mode}
    if controls is not None:
        first['control_points'] = controls
    return {'property': prop, 'keyframes': [first,
        {'at_tick': 36000, 'value': right, 'interpolation': 'linear'}]}


def effects(method):
    p = {'input_signal': dict(SIGNAL), 'output_signal': dict(SIGNAL), 'matrix': 'bt709',
         'range': 'full', 'reference_bits': 8, 'intensity': .2, 'radius': 2.}
    tracks = [key('intensity', .2, .85, 'ease_in_out')]
    if method == 'luma':
        p.update(luma_amount=1.5)
        tracks += [key('luma_amount', 1.5, 2.7), key('radius', 1.25, 3.5, 'ease_in')]
    elif method == 'chroma':
        p.update(luma_amount=0, chroma_amount=-.8)
        tracks += [key('chroma_amount', -.8, 1.2, 'ease_out')]
    elif method == 'horizontal':
        p.update(luma_amount=2., luma_radius_x=5., luma_radius_y=0.)
        tracks += [key('luma_radius_x', 5., 11., 'bezier', [.2, .05, .8, .95])]
    elif method == 'coverage':
        p.update(luma_amount=0., alpha_amount=-1., alpha_radius_x=5., alpha_radius_y=2.)
        tracks += [key('alpha_amount', -1., 1.5, 'hold')]
    else:
        p.update(luma_amount=1.5, chroma_amount=.3, radius=2.25)
    sharpen = {'type': 'sharpen', 'parameters': p, 'keyframes': tracks}
    left, right = (2.7, 3.) if method == 'headroom' else (.15, .45)
    exposure = {'type': 'exposure', 'parameters': {'amount': left, 'black': 0},
                'keyframes': [key('amount', left, right, 'ease_in')]}
    return [exposure, sharpen] if method == 'headroom' else [sharpen, exposure]


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


@lru_cache(maxsize=128)
def axis_matrix(length, radius):
    """Bernoulli polynomial products and explicit replicated endpoint indices."""
    def integer(n):
        row = np.ones(1, np.float64)
        for _ in range(2*n):
            row = np.convolve(row, [.5, .5])
        matrix = np.zeros((length, length), np.float64)
        for offset, weight in enumerate(row):
            column = np.clip(np.arange(length)+offset-n, 0, length-1)
            matrix[np.arange(length), column] += weight
        return matrix
    whole = math.floor(radius); f = radius-whole
    return integer(whole)*(1-f)+integer(whole+1)*f


def grade(encoded, alpha, method, progress):
    rgb = encoded.astype(np.float64)
    # Explicit independent BT.709 full-range 8-bit code axes; no integer raster.
    y = .2126*rgb[..., 0]+.7152*rgb[..., 1]+.0722*rgb[..., 2]
    planes = np.stack((255*y, 128+255*(rgb[..., 2]-y)/(2*(1-.0722)),
                       128+255*(rgb[..., 0]-y)/(2*(1-.2126)), alpha[..., 0]), axis=2)
    radius = 1.25+2.25*progress**2 if method == 'luma' else 2.25 if method == 'headroom' else 2.
    luma = 1.5+1.2*progress if method == 'luma' else 0. if method in ('chroma', 'coverage') else 2. if method == 'horizontal' else 1.5
    chroma = -.8+2*(2*progress-progress**2) if method == 'chroma' else .3 if method == 'headroom' else 0.
    for c, amount in enumerate((luma, chroma, chroma, -1. if method == 'coverage' else 0.)):
        if amount == 0:
            continue
        rx, ry = radius, radius
        if c == 0 and method == 'horizontal':
            rx, ry = 5+6*timing(progress), 0.
        if c == 3:
            rx, ry = 5., 2.
        blurred = axis_matrix(planes.shape[0], float(ry)) @ planes[..., c] @ axis_matrix(planes.shape[1], float(rx)).T
        planes[..., c] += amount*(planes[..., c]-blurred)
        if c == 3:
            planes[..., c] = np.clip(planes[..., c], 0, 1)
    yy, cb, cr = planes[..., 0]/255, (planes[..., 1]-128)/255, (planes[..., 2]-128)/255
    result = np.empty_like(encoded, dtype=np.float32)
    result[..., 0] = yy+2*(1-.2126)*cr
    result[..., 1] = yy-2*.0722*(1-.0722)*cb/.7152-2*.2126*(1-.2126)*cr/.7152
    result[..., 2] = yy+2*(1-.0722)*cb
    if method == 'coverage':
        # The independent coverage-only path must retain hidden RGB exactly.
        result[:] = encoded
    return result, planes[..., 3:4].astype(np.float32)


def expected_rgb(planes, indices):
    results = []
    q = (np.array([16, 32, 64], np.float64)/255).astype(np.float32).astype(np.float64)
    background = np.where(q <= .04045, q/12.92, ((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method = METHODS[index//4]; progress = (index % 4)/4
        eased = 2*progress**2 if progress < .5 else 1-(-2*progress+2)**2/2
        strength = .2+.65*eased
        left, right = (2.7, 3.) if method == 'headroom' else (.15, .45)
        amount = np.float32(left+(right-left)*progress**2)
        inverse = np.float32(2.**(-float(amount))); gain = np.float32(1/float(inverse))
        expose = lambda v: (v*gain).astype(np.float32)
        values = np.moveaxis(planes[index, [2, 0, 1]], 0, -1).astype(np.float32)/np.float32(65535)
        alpha = planes[index, 3].astype(np.float32)[..., None]/np.float32(65535)
        linear = decode(values.astype(np.float64)); before = expose(linear) if method == 'headroom' else linear
        mapped, coverage = grade(encode(before.astype(np.float64)), alpha, method, progress)
        recovered = decode(mapped.astype(np.float64))
        mixed = (before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        coverage = (alpha.astype(np.float64)*(1-strength)+coverage.astype(np.float64)*strength).astype(np.float32).astype(np.float64)
        if method != 'headroom':
            mixed = expose(mixed)
        results.append((mixed.astype(np.float64)*coverage+background*(1-coverage)).astype(np.float32))
    return np.stack(results)
