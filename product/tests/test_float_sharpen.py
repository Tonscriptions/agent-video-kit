"""Independent dense convolution, actual native YUV and real public render paths."""
import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_sharpen import (ALIASES, AXES, BOUNDS, SIZE_ALIASES, apply_sharpen,
    compile_sharpen, state_at, validate_sharpen)
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
from test_float_tone import from_codes, to_codes
import test_float_timeline as fixture
import test_float_preview as preview_fixture

LINEAR = {'primaries': 'bt709', 'transfer': 'linear'}
SRGB = {'primaries': 'bt709', 'transfer': 'srgb'}
WORKING = ColorSignal(**LINEAR)
NATIVE_CALLS = []


def effect(kind='sharpen', **parameters):
    return {'type': kind, 'parameters': {'input_signal': dict(LINEAR), 'output_signal': dict(LINEAR),
        'matrix': 'bt709', 'range': 'full', **parameters}}


def track(name, a, b, mode='linear', stop=100):
    key = {'at_tick': 0, 'value': a, 'interpolation': mode}
    if mode == 'bezier':
        key['control_points'] = [1/3, 0., 2/3, 1.]
    return {'property': name, 'keyframes': [key, {'at_tick': stop, 'value': b, 'interpolation': 'linear'}]}


def pattern(shape=(11, 17), seed=109):
    value = np.random.default_rng(seed).uniform(-.3, 1.6, (*shape, 4)).astype(np.float32)
    value[..., 3] = np.random.default_rng(seed+1).uniform(.1, 1., shape).astype(np.float32)
    return value


def dense(size, radius):
    """A row of a Bernoulli sum, built by polynomial products, then explicit endpoint indices."""
    def integer(n):
        weights = np.ones(1, np.float64)
        for _ in range(2*n):
            weights = np.convolve(weights, [.5, .5])
        result = np.zeros((size, size), np.float64)
        for offset, weight in enumerate(weights):
            target = np.clip(np.arange(size)+offset-n, 0, size-1)
            result[np.arange(size), target] += weight
        return result
    n = math.floor(radius)
    f = radius-n
    return integer(n)*(1-f)+integer(n+1)*f


def oracle(value, p):
    """Independent colour matrix and dense left/right products; no production kernel or state sampler."""
    matrix, ranges, bits = p.get('matrix', 'bt709'), p.get('range', 'full'), p.get('reference_bits', 8)
    planes = np.empty(value.shape, np.float64)
    planes[..., :3] = to_codes(value[..., :3], matrix, ranges, bits)
    planes[..., 3] = value[..., 3]
    alpha_active = False
    maximum = (1 << bits)-1
    for channel, name in enumerate(('luma', 'chroma', 'chroma', 'alpha')):
        amount = p.get(name+'_amount', p.get('amount', 1.) if name == 'luma' else 0.)
        rx, ry = (p.get(name+'_radius_'+axis, p.get('radius_'+axis, p.get('radius', 2.))
                         if name == 'luma' else p.get('radius', 2.)) for axis in ('x', 'y'))
        if amount == 0 or rx == ry == 0:
            continue
        if p.get('arithmetic') == 'native_coefficients':
            amount = math.trunc(float(np.float32(amount))*65536) / (65536 if bits == 8 else 16777216)
        blurred = dense(value.shape[0], ry) @ planes[..., channel] @ dense(value.shape[1], rx).T
        planes[..., channel] += amount*(planes[..., channel]-blurred)
        if channel == 3:
            alpha_active = True
            planes[..., channel] = np.clip(planes[..., channel], 0, 1)
        elif p.get('code_gamut') == 'clip':
            planes[..., channel] = np.clip(planes[..., channel], 0, maximum)
    graded = value.copy()
    graded[..., :3] = from_codes(planes[..., :3], matrix, ranges, bits)
    if alpha_active:
        graded[..., 3] = planes[..., 3]
    if p.get('output_gamut') == 'clip':
        graded[..., :3] = np.clip(graded[..., :3], 0, 1)
    strength = p.get('intensity', 1.)
    result = (value.astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength).astype(np.float32)
    if not alpha_active:
        result[..., 3] = value[..., 3]
    return result


def native(codes, kernel, bits=8, cpu=False):
    fmt = 'yuva444p' if bits == 8 else f'yuva444p{bits}le'
    dtype = np.uint8 if bits == 8 else '<u2'
    h, w = codes.shape[:2]
    payload = np.moveaxis(codes.astype(dtype), -1, 0).tobytes()
    command = [ffmpeg_path(), '-nostdin', '-v', 'error']
    if cpu:
        command += ['-cpuflags', '0']
    command += ['-filter_threads', '1', '-f', 'rawvideo', '-pixel_format', fmt, '-video_size', f'{w}x{h}',
        '-i', 'pipe:0', '-vf', kernel, '-frames:v', '1', '-threads', '1', '-pix_fmt', fmt, '-f', 'rawvideo', 'pipe:1']
    result = subprocess.run(command, input=payload, capture_output=True, timeout=30)
    NATIVE_CALLS.append({'kernel': kernel, 'bits': bits, 'cpu_reference': cpu, 'pixels': h*w,
        'exit_code': result.returncode, 'input_sha256': hashlib.sha256(payload).hexdigest(),
        'output_sha256': hashlib.sha256(result.stdout).hexdigest()})
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors='replace'))
    return np.moveaxis(np.frombuffer(result.stdout, dtype).reshape(4, h, w), 0, -1).copy()


class FloatSharpenTests(unittest.TestCase):
    def apply(self, value, e=None, tick=0, **options):
        return apply_sharpen(value, compile_sharpen(e or effect()), tick, working_signal=WORKING, **options)

    def bad(self, fn, code=None):
        with self.assertRaises(AppError) as caught:
            fn()
        if code:
            self.assertEqual(caught.exception.code, code)

    def compare(self, **p):
        a = pattern()
        expected = oracle(a, p)
        actual, _ = self.apply(a, effect(**p))
        np.testing.assert_allclose(actual, expected, atol=2e-6, rtol=0)

    def compare_native(self, bits=8, amounts=(1.25, 0., 0.), sizes=(5, 5, 5, 5, 5, 5), cpu=False, ranges='full'):
        maximum = (1 << bits)-1
        codes = np.random.default_rng(109).integers(maximum*2//5, maximum*3//5, (13, 19, 4), dtype=np.uint16)
        a = np.empty(codes.shape, np.float32)
        a[..., :3] = from_codes(codes[..., :3], range_value=ranges, bits=bits)
        a[..., 3] = codes[..., 3]/maximum
        p = dict(reference_bits=bits, arithmetic='native_coefficients', code_gamut='clip', range=ranges,
            luma_amount=amounts[0], chroma_amount=amounts[1], alpha_amount=amounts[2])
        for name, size in zip(('luma_msize_x', 'luma_msize_y', 'chroma_msize_x', 'chroma_msize_y', 'alpha_msize_x', 'alpha_msize_y'), sizes):
            p[name] = size
        # Rounded native blur contributes <= .5*|a|, its output floor <1;
        # .05 covers Float32 colour/code transport at the largest reference axis.
        effective = max(abs(v) for v in amounts)/(1 if bits == 8 else 256)
        limit = 1.05+.5*effective
        out, _ = self.apply(a, effect(**p))
        args = [str(v) for plane in range(3) for v in (*sizes[2*plane:2*plane+2], amounts[plane])]
        target = native(codes, 'unsharp='+':'.join(args), bits, cpu)
        actual = np.empty_like(target, dtype=np.float64)
        actual[..., :3] = to_codes(out[..., :3], range_value=ranges, bits=bits)
        actual[..., 3] = out[..., 3].astype(np.float64)*maximum
        delta = float(np.max(np.abs(actual-target)))
        NATIVE_CALLS[-1].update(maximum_fractional_code_error=delta, predeclared_code_limit=limit,
            amount_mode='native_coefficients', range=ranges)
        self.assertLessEqual(delta, limit)

    def test_aliases_and_default_luma_only_contract(self):
        a = pattern()
        for name in ALIASES:
            plan = compile_sharpen(effect(name)); state = state_at(plan, 0)
            self.assertEqual(state['luma_amount'], 1)
            self.assertEqual(state['chroma_amount'], 0); self.assertEqual(state['alpha_amount'], 0)
            self.assertEqual({state[n] for n in AXES}, {2.})
            actual, m = self.apply(a, effect(name))
            self.assertEqual(m['operator_domain'], 'declared-signal-YCbCr')
            self.assertFalse(m['integer_intermediate']); self.assertFalse(m['native_bit_equivalence'])
            np.testing.assert_allclose(actual, oracle(a, {}), atol=2e-6, rtol=0)

    def test_default_is_continuous_not_native_uint16_strength(self):
        a = pattern()
        continuous, m = self.apply(a, effect(reference_bits=16))
        native_scalar, n = self.apply(a, effect(reference_bits=16, arithmetic='native_coefficients'))
        self.assertEqual(m['effective_amounts']['luma'], 1.)
        self.assertEqual(n['effective_amounts']['luma'], 1/256)
        self.assertFalse(np.array_equal(continuous, native_scalar))

    def test_independent_default_binomial_convolution(self): self.compare()
    def test_independent_all_three_plane_groups(self): self.compare(amount=1.7, chroma_amount=-.8, alpha_amount=.6)
    def test_independent_fractional_master_radius(self): self.compare(radius=2.375, amount=-.75)
    def test_independent_zero_horizontal_axis(self): self.compare(luma_radius_x=0, luma_radius_y=3.5)
    def test_independent_zero_vertical_axis(self): self.compare(luma_radius_x=4.25, luma_radius_y=0)
    def test_independent_every_plane_uses_its_own_axes(self):
        self.compare(luma_amount=1.2, chroma_amount=.6, alpha_amount=-1,
            luma_radius_x=1.5, luma_radius_y=2.25, chroma_radius_x=4.75,
            chroma_radius_y=.5, alpha_radius_x=0, alpha_radius_y=1.25)

    def test_independent_both_code_and_output_clipping(self):
        self.compare(amount=5, chroma_amount=3, alpha_amount=4, code_gamut='clip', output_gamut='clip')

    def test_independent_all_matrices_and_both_ranges(self):
        for matrix in ('bt709', 'smpte170m', 'bt470bg', 'bt2020nc'):
            for ranges in ('full', 'limited'):
                self.compare(matrix=matrix, range=ranges, amount=-.8, chroma_amount=1.3, radius=1.25)

    def test_independent_all_fractional_code_axes(self):
        for bits in (8, 9, 10, 12, 14, 16):
            self.compare(reference_bits=bits, code_gamut='clip', amount=1.5, chroma_amount=.7)

    def test_native_8bit_positive_and_negative_amounts(self):
        for value in (-2., -1., .37, 1.25, 5.): self.compare_native(amounts=(value, 0., 0.))

    def test_native_9_10_12_16bit_storage_coefficients(self):
        for bits in (9, 10, 12, 16): self.compare_native(bits=bits)

    def test_native_independent_luma_chroma_and_anisotropy(self):
        # Native 8.1 crashes for nonzero alpha_amount (retained native-r1).
        # Alpha correctness uses the independent dense oracle above.
        self.compare_native(amounts=(1.2, -.6, 0.), sizes=(3, 7, 7, 3, 3, 3))

    def test_native_16bit_luma_chroma_and_software_reference(self):
        for cpu in (False, True): self.compare_native(bits=16, amounts=(1.5, -.8, 0.), cpu=cpu)

    def test_native_limited_range_keeps_declared_axes(self):
        for bits in (8, 10, 16): self.compare_native(bits=bits, ranges='limited')

    def test_native_all_zero_amounts_preserve_all_planes(self):
        self.compare_native(amounts=(0., 0., 0.))

    def test_native_widest_axis_with_minimal_other_axis(self):
        self.compare_native(amounts=(1., 0., 0.), sizes=(23, 3, 5, 5, 5, 5))

    def test_large_float_kernel_is_explicit_non_native_extension(self):
        self.compare(radius=11., amount=1.7)
        _, m = self.apply(pattern(), effect(radius=11.))
        self.assertFalse(m['native_kernel_and_amount_option_eligible']['luma'])
        self.assertFalse(m['native_accumulator_safe_at_reference_max']['luma'])

    def test_14bit_is_explicit_extension_not_an_accepted_native_format(self):
        _, m = self.apply(pattern(), effect(reference_bits=14))
        self.assertFalse(m['reference_bits_native_format_supported'])

    def test_legacy_amount_above_five_has_declared_float_extension(self):
        self.compare(amount=10.)
        _, m = self.apply(pattern(), effect(amount=10.))
        self.assertFalse(m['native_kernel_and_amount_option_eligible']['luma'])

    def test_all_native_static_size_aliases_and_duplicate_rejection(self):
        for alias, canonical in SIZE_ALIASES.items():
            p = compile_sharpen(effect(**{alias: 7}))
            self.assertEqual(state_at(p, 0)[canonical], 3)
            self.bad(lambda: compile_sharpen(effect(**{alias: 7, canonical: 3})))
        for size in (2, 4, 24, True, 5.):
            self.bad(lambda size=size: compile_sharpen(effect(lx=size)))

    def test_kernel_size_alias_cannot_be_interpolated_as_an_integer(self):
        e = effect(); e['keyframes'] = [track('lx', 3, 7)]
        self.bad(lambda: compile_sharpen(e))

    def test_master_axis_override_and_dynamic_override_are_distinct(self):
        e = effect(radius=4, luma_radius_x=1)
        e['keyframes'] = [track('radius', 2, 6), track('alpha_radius_y', 0, 2)]
        s = state_at(compile_sharpen(e), 50)
        self.assertEqual(s['luma_radius_x'], 1); self.assertEqual(s['luma_radius_y'], 4)
        self.assertEqual(s['chroma_radius_x'], 4); self.assertEqual(s['alpha_radius_y'], 1)

    def test_amount_aliases_and_duplicate_aliases_are_checked(self):
        for alias, canonical in (('amount', 'luma_amount'), ('la', 'luma_amount'), ('ca', 'chroma_amount'), ('aa', 'alpha_amount')):
            self.assertEqual(state_at(compile_sharpen(effect(**{alias: .75})), 0)[canonical], .75)
            self.bad(lambda: compile_sharpen(effect(**{alias: 1, canonical: 1})))

    def test_negative_and_superwhite_RGB_stay_finite_without_implicit_clip(self):
        a = pattern(); out, m = self.apply(a)
        self.assertTrue(np.any(out[..., :3] < 0)); self.assertTrue(np.any(out[..., :3] > 1))
        self.assertEqual(m['clipped_code_components'], 0); self.assertEqual(m['output_clipped_components'], 0)

    def test_default_alpha_is_bit_preserved_including_negative_zero(self):
        a = pattern(); a[0, 0, 3] = -0.; a[0, 1, 3] = np.float32(1e-30)
        out, m = self.apply(a)
        self.assertEqual(out[..., 3].tobytes(), a[..., 3].tobytes())
        self.assertEqual(m['alpha'], 'input-bits-preserved')

    def test_alpha_only_bypasses_RGB_conversion_and_preserves_hidden_RGB(self):
        a = pattern(); a[0, 0] = [-0., -.5, 3., 0.]
        out, m = self.apply(a, effect(amount=0, alpha_amount=-1))
        self.assertEqual(out[..., :3].tobytes(), a[..., :3].tobytes())
        self.assertTrue(m['alpha_only_RGB_conversion_bypassed'])
        self.assertGreater(float(out[0, 0, 3]), 0.)

    def test_alpha_sharpen_clips_coverage_and_reports_clipped_pixels(self):
        a = np.ones((7, 9, 4), np.float32)*.5
        a[..., 3] = np.indices((7, 9)).sum(axis=0) % 2
        out, m = self.apply(a, effect(amount=0, alpha_amount=3))
        self.assertTrue(np.all((out[..., 3] >= 0) & (out[..., 3] <= 1)))
        self.assertGreater(m['clipped_alpha_pixels'], 0)

    def test_zero_amount_zero_radius_and_zero_intensity_are_exact_identities(self):
        a = pattern(); a[0, 0] = [-0., -.3, 1.7, -0.]
        for p in ({'amount': 0}, {'radius': 0}, {'intensity': 0, 'output_gamut': 'clip'}):
            out, _ = self.apply(a, effect(**p)); self.assertEqual(out.tobytes(), a.tobytes())

    def test_native_scalar_rounding_to_zero_is_an_identity(self):
        a = pattern(); out, m = self.apply(a, effect(amount=1e-9, arithmetic='native_coefficients'))
        self.assertEqual(out.tobytes(), a.tobytes()); self.assertEqual(m['effective_amounts']['luma'], 0.)

    def test_constant_fields_and_one_pixel_axes_preserve_DC(self):
        for shape in ((1, 1), (1, 13), (9, 1), (9, 13)):
            a = np.broadcast_to(np.array([.4, .3, 1.3, .25], np.float32), (*shape, 4)).copy()
            out, _ = self.apply(a, effect(radius=10.25, amount=7, chroma_amount=-1, alpha_amount=3))
            np.testing.assert_allclose(out, a, atol=2e-7, rtol=0)

    def test_singleton_pixels_compare_to_independent_dense_extensions(self):
        for shape in ((1, 9), (7, 1), (1, 1)):
            a = pattern(shape); p = {'radius': 2.75, 'amount': 1.3, 'chroma_amount': -.4}
            out, _ = self.apply(a, effect(**p)); np.testing.assert_allclose(out, oracle(a, p), atol=2e-6, rtol=0)

    def test_float32_ramp_keeps_more_than_integer_code_levels(self):
        ramp = np.linspace(.3, .7, 100000, dtype=np.float32)
        a = np.ones((1, len(ramp), 4), np.float32); a[..., :3] = ramp[None, :, None]
        # Dimensions are intentionally bounded by the public surface contract.
        a = a.reshape(10, 10000, 4).copy()
        out, _ = self.apply(a, effect(luma_radius_x=1, luma_radius_y=0, amount=.37))
        self.assertGreater(len(np.unique(out[..., 0])), 65536)

    def test_fractional_kernel_does_not_round_radius_to_an_integer(self):
        a = pattern()
        half, _ = self.apply(a, effect(radius=2.5))
        lo, _ = self.apply(a, effect(radius=2.)); hi, _ = self.apply(a, effect(radius=3.))
        self.assertFalse(np.array_equal(half, lo)); self.assertFalse(np.array_equal(half, hi))
        np.testing.assert_allclose(half, oracle(a, {'radius': 2.5}), atol=2e-6, rtol=0)

    def test_all_six_easings_preserve_endpoints_and_parameter_bounds(self):
        for mode in ('linear', 'hold', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'):
            e = effect(); e['keyframes'] = [track('amount', -1, 3, mode)]
            plan = compile_sharpen(e)
            self.assertEqual(state_at(plan, 0)['luma_amount'], -1)
            self.assertEqual(state_at(plan, 100)['luma_amount'], 3)
            self.assertTrue(-1 <= state_at(plan, Fraction(25, 1))['luma_amount'] <= 3)

    def test_four_control_Bezier_matches_independent_cubic(self):
        e = effect(); e['keyframes'] = [track('radius', 0, 8, 'bezier')]
        expected = 8*(3*.25**2-2*.25**3)
        self.assertAlmostEqual(state_at(compile_sharpen(e), 25)['radius'], expected, places=10)

    def test_rational_author_ticks_above_double_integer_precision(self):
        base = 2**54
        e = effect(); t = track('amount', 0, 4, stop=base+1)
        t['keyframes'][0]['at_tick'] = base; e['keyframes'] = [t]
        self.assertEqual(state_at(compile_sharpen(e), Fraction(2*base+1, 2))['luma_amount'], 2.)

    def test_dynamic_radii_and_intensity_match_independent_pixels(self):
        a = pattern(); e = effect(chroma_amount=.7)
        e['keyframes'] = [track('radius', 0, 4), track('intensity', .2, .8)]
        out, _ = self.apply(a, e, 25)
        np.testing.assert_allclose(out, oracle(a, {'radius': 1., 'intensity': .35, 'chroma_amount': .7}), atol=2e-6, rtol=0)

    def test_intensity_uses_linear_working_RGB_and_independent_coverage(self):
        a = pattern(); e = effect(amount=1.3, alpha_amount=-.8, intensity=.3)
        actual, _ = self.apply(a, e)
        np.testing.assert_allclose(actual, oracle(a, e['parameters']), atol=2e-6, rtol=0)

    def test_declared_srgb_operator_uses_transfer_before_spatial_filter(self):
        a = np.random.default_rng(109).uniform(.1, .8, (9, 13, 4)).astype(np.float32)
        encoded = a.copy(); encoded[..., :3] = 1.055*a[..., :3].astype(np.float64)**(1/2.4)-.055
        graded = oracle(encoded, {'amount': .6, 'code_gamut': 'clip'})
        rgb = graded[..., :3].astype(np.float64)
        expected = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4).astype(np.float32)
        actual, _ = self.apply(a, effect(input_signal=SRGB, output_signal=SRGB, amount=.6, code_gamut='clip'))
        np.testing.assert_allclose(actual[..., :3], expected, atol=3e-7, rtol=0)
        self.assertEqual(actual[..., 3].tobytes(), a[..., 3].tobytes())

    def test_unknown_signals_matrix_range_and_options_are_rejected(self):
        for p in ({'input_signal': None}, {'output_signal': None}, {'matrix': 'guess'}, {'matrix': []},
                  {'range': 'auto'}, {'reference_bits': True}, {'reference_bits': 11},
                  {'arithmetic': 'pixels'}, {'code_gamut': 'guess'}, {'output_gamut': 'guess'}, {'oops': 1}):
            self.bad(lambda p=p: compile_sharpen(effect(**p)))

    def test_invalid_numeric_values_and_amount_bounds_are_rejected(self):
        for p in ({'amount': True}, {'amount': float('nan')}, {'amount': 10.1}, {'amount': -2.1},
                  {'radius': 11.1}, {'radius': -1}, {'intensity': 1.1}, {'alpha_amount': '1'}):
            self.bad(lambda p=p: compile_sharpen(effect(**p)))

    def test_effect_shape_and_keyframe_schema_are_strict(self):
        for e in (None, [], {'type': 'sharpen', 'amount': 1}, {'type': 'sharpen', 'enabled': 1}, effect('unknown')):
            self.bad(lambda e=e: compile_sharpen(e))
        e = effect(); e['keyframes'] = [track('amount', 0, 1), track('la', 0, 1)]
        self.bad(lambda: compile_sharpen(e))

    def test_keyframes_beyond_original_duration_are_rejected(self):
        e = effect(); e['keyframes'] = [track('amount', 0, 1, stop=200)]
        self.assertTrue(validate_sharpen(e, duration_tick=100))
        self.assertEqual(validate_sharpen(e, duration_tick=200), [])

    def test_forged_mutable_and_incomplete_plans_are_rejected(self):
        a = pattern(); p = compile_sharpen(effect())
        for bad in (replace(p, author_name=[]), replace(p, values=list(p.values)), replace(p, values=p.values[:-1]),
                    replace(p, tracks_json='[ ]'), replace(p, axis_overrides=('oops',)), replace(p, matrix='auto')):
            self.bad(lambda bad=bad: apply_sharpen(a, bad, 0, working_signal=WORKING))

    def test_late_invalid_input_is_rejected_without_mutating_caller(self):
        a = pattern(); a[-1, -1, 3] = 1.1; before = a.tobytes()
        self.bad(lambda: self.apply(a, tile_pixels=1)); self.assertEqual(a.tobytes(), before)
        a[-1, -1, 3] = .5; a[-1, -1, 0] = np.inf
        self.bad(lambda: self.apply(a))

    def test_surface_dtype_shape_contiguity_and_working_signal_are_strict(self):
        a = pattern()
        for bad in (a.astype(np.float64), a[:, ::2], np.zeros((2, 3, 3), np.float32), np.zeros((0, 2, 4), np.float32)):
            self.bad(lambda bad=bad: self.apply(bad))
        self.bad(lambda: apply_sharpen(a, compile_sharpen(effect()), 0, working_signal=ColorSignal(**SRGB)))

    def test_readonly_input_and_conversion_tile_sizes_are_identical(self):
        a = pattern((29, 31)); a.flags.writeable = False
        e = effect(input_signal=SRGB, output_signal=SRGB, amount=.7, radius=2.25, intensity=.4)
        expected, _ = self.apply(a, e, tile_pixels=1)
        for tile in (7, 16384, 262144):
            out, _ = self.apply(a, e, tile_pixels=tile); self.assertEqual(out.tobytes(), expected.tobytes())

    def test_budget_retained_tables_and_invalid_tiles_reject_before_output(self):
        a = pattern(); before = a.tobytes()
        for option in ({'max_working_bytes': 1}, {'retained_table_bytes': 768*1024*1024},
                       {'tile_pixels': 0}, {'tile_pixels': True}, {'tile_pixels': 262145}):
            self.bad(lambda option=option: self.apply(a, **option)); self.assertEqual(a.tobytes(), before)

    def test_small_admitted_conversion_tile_does_not_change_spatial_results(self):
        a = pattern((65, 71)); e = effect(radius=4.25, chroma_amount=.8, alpha_amount=-.7)
        expected, _ = self.apply(a, e)
        out, m = self.apply(a, e, max_working_bytes=2*1024*1024)
        self.assertEqual(out.tobytes(), expected.tobytes())
        self.assertTrue(m['workspace_admission']['adaptive_tile_reduction'])
        self.assertFalse(m['estimated_bytes_are_peak_RSS'])

    def test_cancellation_during_convolution_and_callback_errors_are_transactional(self):
        a = pattern((51, 71)); before = a.tobytes(); count = [0]
        def cancel():
            count[0] += 1
            return count[0] > 9
        self.bad(lambda: self.apply(a, cancel=cancel), 'RENDER_CANCELLED')
        self.assertEqual(a.tobytes(), before)
        def crash(): raise RuntimeError('callback failed')
        with self.assertRaises(RuntimeError): self.apply(a, cancel=crash)
        self.bad(lambda: self.apply(a, cancel=True))

    def test_unbounded_output_overflow_is_explicit_and_transactional(self):
        a = np.zeros((5, 5, 4), np.float32); a[..., 3] = .5; a[2, 2, :3] = 3e38
        before = a.tobytes(); self.bad(lambda: self.apply(a, effect(amount=10)))
        self.assertEqual(a.tobytes(), before)

    def test_effect_chain_preserves_order_with_spatial_and_tone(self):
        a = pattern(); compiler = EffectCompiler(resource_root=None, working_signal=WORKING)
        rows = [effect(amount=.7), {'type': 'exposure', 'parameters': {'amount': .3}},
            {'type': 'avgblur', 'parameters': {'input_signal': LINEAR, 'output_signal': LINEAR, 'radius': 1.25}}]
        out, m = compiler.apply(a, compiler.compile(rows), 50); expected = a
        for row in rows: expected, _ = compiler.apply(expected, compiler.compile([row]), 50)
        self.assertEqual(out.tobytes(), expected.tobytes()); self.assertEqual(m['ordered_effects'][0]['type'], 'sharpen')
        backward, _ = compiler.apply(a, compiler.compile(list(reversed(rows))), 50)
        self.assertFalse(np.array_equal(out, backward))

    def test_presentation_window_keeps_original_sharpen_author_ticks(self):
        a = pattern((4, 8)); p, sources = fixture.image_project(a, duration=200)
        e = effect(); e['keyframes'] = [track('amount', -.5, 2, stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200, source_out_tick=200, effects=[e])
        host = FloatTimeline(p, 'main', sources, working_signal=WORKING)
        original = [host.render_frame(i)[0] for i in range(20)]
        selected = copy.deepcopy(p)
        selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,
            presentation_window={'version': 1, 'authored_start_tick': 0, 'authored_duration_tick': 200, 'offset_tick': 70})
        host = FloatTimeline(selected, 'main', sources, working_signal=WORKING)
        for i in range(6): self.assertEqual(host.render_frame(i)[0].tobytes(), original[i+7].tobytes())

    def test_nested_reverse_keeps_independent_child_and_parent_author_ticks(self):
        a = pattern((4, 8)); p, sources = fixture.image_project(a, duration=200)
        child = copy.deepcopy(p['sequences'][0]); child['id'] = 'child'
        e = effect(); e['keyframes'] = [track('amount', -1, 2, 'hold', stop=160)]
        child['tracks'][0]['clips'][0].update(duration_tick=200, source_out_tick=200, effects=[e])
        parent = p['sequences'][0]['tracks'][0]['clips'][0]; parent.pop('asset_id')
        parent.update(sequence_id='child', duration_tick=200, source_out_tick=200, reverse=True, effects=[effect(amount=.2)])
        p['sequences'].append(child)
        out, _ = FloatTimeline(p, 'main', sources, working_signal=WORKING).render_frame(4)
        expected, _ = self.apply(a, e, np.nextafter(160., -np.inf))
        expected, _ = self.apply(expected, parent['effects'][0], 40)
        np.testing.assert_allclose(out, expected, atol=2e-6, rtol=0)

    def test_validator_routes_native_sharpen_and_preserves_legacy_engine(self):
        from ai_ad_editor.validator import validate_project
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.visual(); case.s['duration_tick'] = 18000
            e = effect(); e['keyframes'] = [track('radius', 0, 4, stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e]
            result = validate_project(case.root, case.p); self.assertTrue(result['ok'], result)
            e['parameters'].pop('matrix'); self.assertFalse(validate_project(case.root, case.p)['ok'])
            case.p['settings'].pop('pixel_pipeline')
            case.s['tracks'][0]['clips'][0]['effects'] = [{'type': 'sharpen', 'parameters': {'amount': 1}}]
            self.assertTrue(validate_project(case.root, case.p)['ok'])
        finally: case.doCleanups()

    def test_real_preview_PCM_and_PNG16_match_independent_spatial_oracle(self):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            case.p['settings']['pixel_pipeline']['range_policy'] = 'clip'
            pixels = case.visual(np.stack([np.clip(pattern((16, 32)), 0, 1)]*2))
            audio = case.audio(); e = effect(amount=.7, chroma_amount=.2)
            e['keyframes'] = [track('radius', 1.25, 2.5, stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e]
            result = case.execute(end=2); actual = case.reference(result)
            source = np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535)
            expected = source.copy()
            for i, radius in enumerate((1.25, 2.5)):
                graded = oracle(source[i], {'amount': .7, 'chroma_amount': .2, 'radius': radius})
                expected[i, ..., :3] = graded[..., :3]*source[i, ..., 3:4]
            expected[..., 3] = 1
            expected[..., :3] = np.clip(expected[..., :3], 0, 1)
            np.testing.assert_allclose(actual, expected, atol=2e-6, rtol=0)
            self.assertEqual(case.pcm(result), audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),
                np.rint(np.clip(actual[0].astype(np.float64), 0, 1)*65535), atol=1, rtol=0)
            case.assert_clean()
        finally: case.doCleanups()

    def test_real_formal_transport_matches_float_preview(self):
        from ai_ad_editor.render import render_project
        from ai_ad_editor.project import project_write_lock
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            case.visual(np.stack([np.clip(pattern((16, 32)), 0, 1)]*2)); case.audio()
            case.s['tracks'][0]['clips'][0]['effects'] = [effect(amount=1.2, code_gamut='clip', output_gamut='clip')]
            actual = case.reference(case.execute(end=2))
            with project_write_lock(case.root):
                formal = render_project(case.root, case.p, case.s, case.root/'renders/sharpen.mkv')
            manifest = json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload = np.moveaxis(np.rint(np.clip(actual[..., [1, 2, 0, 3]].astype(np.float64), 0, 1)*65535).astype('<u2'), 3, 1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],
                'sha256:'+hashlib.sha256(payload).hexdigest()); case.assert_clean()
        finally: case.doCleanups()

    def test_real_cache_hit_and_kernel_change_invalidate_cache(self):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            case.p['settings']['pixel_pipeline']['range_policy'] = 'clip'
            case.visual(np.stack([np.clip(pattern((16, 32)), 0, 1)]*2)); case.audio()
            e = effect(amount=.4, radius=1); case.s['tracks'][0]['clips'][0]['effects'] = [e]
            one = case.execute(end=2); self.assertTrue(case.execute(end=2)['cache_hit'])
            e['parameters']['radius'] = 2.5; two = case.execute(end=2)
            self.assertNotEqual(one['cache_key'], two['cache_key']); self.assertFalse(two['cache_hit']); case.assert_clean()
        finally: case.doCleanups()

    def test_real_preview_rejects_unaccepted_headroom_without_explicit_delivery_clip(self):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            case.visual(np.stack([np.clip(pattern((16, 32)), 0, 1)]*2)); case.audio()
            case.s['tracks'][0]['clips'][0]['effects'] = [effect(amount=2)]
            with self.assertRaises(AppError) as caught:
                case.execute(end=2)
            self.assertEqual(caught.exception.code, 'FLOAT_RENDER_RANGE'); case.assert_clean()
        finally: case.doCleanups()

    def test_capabilities_disabled_effects_and_unimplemented_temporal_filter(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        row = build_capability_manifest()['capabilities']['timeline_native_float_sharpen']
        self.assertIn('native_integer_accumulator_or_signed_multiply_overflow_not_reproduced', row['limits'])
        compiler = EffectCompiler(resource_root=None, working_signal=WORKING)
        self.assertEqual(compiler.compile([{'type': 'sharpen', 'enabled': False, 'parameters': {'bad': True}}]), ())
        self.bad(lambda: compiler.compile([{'type': 'hqdn3d'}]), 'FLOAT_TIMELINE_UNSUPPORTED')
