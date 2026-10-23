"""Independent finite-window mathematics, real integer FFmpeg and public paths."""
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
from ai_ad_editor.float_gaussian import apply_gaussian, compile_gaussian
from ai_ad_editor.float_spatial import (ALIASES, SpatialPlan, apply_spatial, compile_spatial,
    state_at, validate_spatial)
from ai_ad_editor.float_spatial_budget import admit_spatial, MAX_WORKING_BYTES
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
from test_float_levels import track
import test_float_timeline as fixture
import test_float_preview as preview_fixture

LINEAR = {'primaries': 'bt709', 'transfer': 'linear'}
SRGB = {'primaries': 'bt709', 'transfer': 'srgb'}
WORKING = ColorSignal(**LINEAR)
NATIVE_CALLS = []
AVERAGE_NATIVE_CODE_LIMIT = 1.02  # One final floor plus Float32 normalization.


def effect(kind='avgblur', **parameters):
    return {'type': kind, 'parameters': {'input_signal': dict(LINEAR), 'output_signal': dict(LINEAR), **parameters}}


def pattern(shape=(11, 17), seed=108):
    value = np.random.default_rng(seed).uniform(-.3, 1.5, (*shape, 4)).astype(np.float32)
    value[..., 3] = np.random.default_rng(seed+1).uniform(.03, .97, shape).astype(np.float32)
    return value


def dense_axis(length, radius, boundary):
    """Explicit taps and mapped indices; no production sums/padding code."""
    matrix = np.zeros((length, length), np.float64)
    whole = math.floor(radius); fraction = radius-whole
    taps = [(offset, 1.) for offset in range(-whole, whole+1)]
    if fraction: taps += [(-whole-1, fraction), (whole+1, fraction)]
    for target in range(length):
        for offset, weight in taps:
            source = target+offset
            if boundary == 'edge': source = min(length-1, max(0, source))
            else:
                source %= 2*length
                if source >= length: source = 2*length-1-source
            matrix[target, source] += weight/(2*radius+1)
    return matrix


def dense(value, rx, ry=None, kind='average_blur', power=1, planes=15, premultiplied=False):
    ry = rx if ry is None else ry
    if kind == 'average_blur': rx, ry = min(rx, value.shape[1]//2), min(ry, value.shape[0]//2)
    boundary = 'edge' if kind == 'average_blur' else 'symmetric'
    x = np.linalg.matrix_power(dense_axis(value.shape[1], rx, boundary), power)
    y = np.linalg.matrix_power(dense_axis(value.shape[0], ry, boundary), power)
    data = value.astype(np.float64)
    if premultiplied: data[..., :3] *= data[..., 3:4]
    blurred = np.einsum('ij,jkc,lk->ilc', y, data, x, optimize=True)
    if premultiplied:
        positive = blurred[..., 3] > 0
        np.divide(blurred[..., :3], blurred[..., 3:4], out=blurred[..., :3], where=positive[..., None])
        blurred[..., :3][~positive] = 0
    out = value.astype(np.float64)
    for channel, bit in enumerate((4, 1, 2, 8)):
        if planes & bit: out[..., channel] = blurred[..., channel]
    return out


def native_codes(codes, kind, rx, ry=None, *, bits=8, power=1, planes=15, cpu=False):
    ry = rx if ry is None else ry; h, w = codes.shape[:2]
    pixel_format = 'gbrap' if bits == 8 else f'gbrap{bits}le'
    dtype = 'u1' if bits == 8 else '<u2'
    payload = np.moveaxis(codes[..., [1, 2, 0, 3]], 2, 0).astype(dtype).tobytes()
    kernel = (f'avgblur=sizeX={rx}:sizeY={ry}:planes={planes}' if kind == 'average_blur'
              else f'boxblur=luma_radius={rx}:luma_power={power}:chroma_radius={rx}:chroma_power={power}:alpha_radius={rx}:alpha_power={power}')
    args = [ffmpeg_path(), '-nostdin', '-v', 'error']
    if cpu: args += ['-cpuflags', '0']
    args += ['-filter_threads', '1', '-f', 'rawvideo', '-pixel_format', pixel_format, '-video_size', f'{w}x{h}',
             '-i', 'pipe:0', '-vf', kernel, '-frames:v', '1', '-threads', '1', '-pix_fmt', pixel_format, '-f', 'rawvideo', 'pipe:1']
    result = subprocess.run(args, input=payload, capture_output=True, check=True)
    expected_bytes = h*w*4*(1 if bits == 8 else 2)
    assert len(result.stdout) == expected_bytes
    NATIVE_CALLS.append({'kind': kind, 'kernel': kernel, 'pixel_format': pixel_format, 'bits': bits,
        'width': w, 'height': h, 'cpu_reference': cpu, 'exit_code': result.returncode,
        'input_sha256': hashlib.sha256(payload).hexdigest(), 'output_sha256': hashlib.sha256(result.stdout).hexdigest()})
    return np.moveaxis(np.frombuffer(result.stdout, dtype).reshape(4, h, w)[[2, 0, 1, 3]], 0, 2).copy()


def box_code_limit(bits, radius, power):
    """Predicted quantization/gain bound before native execution; not fitted."""
    length = 2*radius+1; reciprocal = (65536+length//2)//length
    gain_error = abs(reciprocal*length/65536-1)
    bound = 0.
    for _ in range(2*power): bound = (1+gain_error)*bound + .5 + ((1 << bits)-1)*gain_error
    return bound+.02


class FloatSpatialTests(unittest.TestCase):
    def apply(self, value, e=None, tick=0, **kwargs):
        return apply_spatial(value, compile_spatial(e or effect()), tick, working_signal=WORKING, **kwargs)

    def bad(self, fn, code=None):
        with self.assertRaises(AppError) as caught: fn()
        if code: self.assertEqual(caught.exception.code, code)

    def compare_native(self, kind='average_blur', rx=2, ry=None, bits=8, power=1, planes=15, shape=(13, 23), cpu=False):
        maximum = (1 << bits)-1
        codes = np.random.default_rng(108).integers(max(1, maximum//20), maximum*17//20, (*shape, 4), dtype=np.uint16)
        value = codes.astype(np.float32)/np.float32(maximum)
        ry = rx if ry is None else ry
        p = {'size_x': rx, 'size_y': ry, 'planes': planes} if kind == 'average_blur' else {'radius': rx, 'power': power}
        limit = AVERAGE_NATIVE_CODE_LIMIT if kind == 'average_blur' else box_code_limit(bits, rx, power)
        actual, _ = self.apply(value, effect('avgblur' if kind == 'average_blur' else 'boxblur', **p))
        expected = native_codes(codes, kind, rx, ry, bits=bits, power=power, planes=planes, cpu=cpu)
        error_code = float(np.max(np.abs(actual.astype(np.float64)*maximum-expected)))
        NATIVE_CALLS[-1].update(maximum_fractional_code_error=error_code, predeclared_code_limit=limit)
        self.assertLessEqual(error_code, limit)

    def test_aliases_default_radii_and_protocol(self):
        for name in ALIASES:
            p = compile_spatial(effect(name)); value = 2 if name in ('avgblur', 'average_blur') else 4
            self.assertEqual(state_at(p, 0)['radius_x'], value)
            out, m = self.apply(pattern(), effect(name)); self.assertEqual(out.dtype, np.float32)
            self.assertFalse(m['integer_intermediate']); self.assertFalse(m['native_bit_equivalence'])

    def test_zero_radius_and_zero_box_power_preserve_exact_signed_bits(self):
        value = pattern(); value[0, 0] = [-0., -.2, 1.4, -0.]
        for e in (effect(radius=0), effect('boxblur', radius=0), effect('boxblur', power=0)):
            out, _ = self.apply(value, e); self.assertEqual(out.tobytes(), value.tobytes())

    def test_native_average_8bit_legacy_default(self): self.compare_native()

    def test_native_average_16bit_anisotropic(self): self.compare_native(rx=3, ry=1, bits=16)

    def test_native_average_10_and_12bit(self):
        for bits in (10, 12): self.compare_native(rx=2, ry=4, bits=bits)

    def test_native_average_all_sixteen_GBRA_plane_masks(self):
        for planes in range(16): self.compare_native(rx=1, ry=2, planes=planes, shape=(9, 17))

    def test_native_average_large_radii_clamp_to_half_axis(self):
        self.compare_native(rx=1024, ry=1024, bits=16, shape=(7, 13))

    def test_native_average_sizeY_zero_inherits_X(self): self.compare_native(rx=3, ry=0)

    def test_native_box_8bit_all_four_powers(self):
        for power in range(1, 5): self.compare_native('box_blur', rx=2, power=power)

    def test_native_box_16bit_reciprocal_and_quantization_bounds(self):
        for radius, power in ((1, 1), (2, 2), (3, 3), (5, 4)):
            self.compare_native('box_blur', rx=radius, bits=16, power=power)

    def test_native_integer_CPU_reference_matches_declared_bounds(self):
        self.compare_native(rx=2, ry=3, cpu=True)
        self.compare_native('box_blur', rx=3, power=3, cpu=True)

    def test_independent_fractional_average_taps_and_anisotropic_axes(self):
        value = pattern((7, 9))
        for rx, ry in ((.1, .7), (.5, 1.4), (2.99, .2), (0., 1.3), (1.4, 0.)):
            out, _ = self.apply(value, effect(radius_x=rx, radius_y=ry))
            np.testing.assert_allclose(out, dense(value, rx, ry), atol=8e-8, rtol=0)

    def test_independent_fractional_box_taps_repeated_axis_order(self):
        value = pattern((7, 9))
        for rx, ry, power in ((.3, 1.7, 1), (1.7, .4, 2), (4.8, 2.1, 4)):
            out, _ = self.apply(value, effect('boxblur', radius_x=rx, radius_y=ry, power=power))
            np.testing.assert_allclose(out, dense(value, rx, ry, 'box_blur', power), atol=8e-8, rtol=0)

    def test_average_and_box_have_distinct_boundary_pixels(self):
        value = np.zeros((5, 13, 4), np.float32); value[..., 3] = 1; value[:, 0, 0] = 1
        a, am = self.apply(value, effect(radius_x=2, radius_y=0))
        b, bm = self.apply(value, effect('boxblur', radius_x=2, radius_y=0))
        self.assertAlmostEqual(float(a[0, 0, 0]), .6, places=7)
        self.assertAlmostEqual(float(b[0, 0, 0]), .4, places=7)
        self.assertEqual(am['boundary'], 'edge'); self.assertEqual(bm['boundary'], 'symmetric')

    def test_average_effective_radii_report_clamps_without_editing_plan(self):
        p = compile_spatial(effect(radius=1024)); value = pattern((3, 5))
        out, m = apply_spatial(value, p, 0, working_signal=WORKING)
        self.assertEqual(m['effective_radii'], {'radius_x': 2, 'radius_y': 1})
        self.assertEqual(state_at(p, 0)['radius'], 1024)
        np.testing.assert_allclose(out, dense(value, 1024), atol=8e-8, rtol=0)

    def test_box_large_radius_is_explicit_symmetric_extension(self):
        value = pattern((3, 5)); out, m = self.apply(value, effect('boxblur', radius=128, power=4))
        np.testing.assert_allclose(out, dense(value, 128, kind='box_blur', power=4), atol=8e-8, rtol=0)
        self.assertEqual(m['effective_radii']['radius_x'], 128)

    def test_singleton_axes_use_defined_edge_and_symmetric_mapping(self):
        for shape in ((1, 1), (1, 9), (7, 1)):
            value = pattern(shape)
            for kind in ('average_blur', 'box_blur'):
                out, _ = self.apply(value, effect(kind, radius=1.7))
                np.testing.assert_allclose(out, dense(value, 1.7, kind=kind), atol=8e-8, rtol=0)

    def test_constant_signed_headroom_survives_maximum_radius(self):
        value = fixture.rgba((-.25, .5, 1.75, .375), shape=(7, 13))
        for kind, radius, power in (('average_blur', 1024, 1), ('box_blur', 128, 4)):
            out, _ = self.apply(value, effect(kind, radius=radius, **({'power': power} if power != 1 else {})))
            self.assertEqual(out.tobytes(), value.tobytes())

    def test_float_ramp_is_not_posterized_to_integer_samples(self):
        value = np.ones((14, 10000, 4), np.float32)
        value[..., :3] = np.linspace(0, 1, 140000, dtype=np.float32).reshape(14, 10000, 1)
        value[..., 3] = .5; out, _ = self.apply(value, effect(radius_x=.2, radius_y=0))
        self.assertGreater(len(np.unique(out[..., 0])), 130000)

    def test_RGB_only_planes_preserve_original_alpha_bits(self):
        value = pattern(); value[0, 0, 3] = -0.; value[0, 1, 3] = np.nextafter(np.float32(0), np.float32(1))
        for kind in ('avgblur', 'boxblur'):
            out, m = self.apply(value, effect(kind, planes=7))
            self.assertEqual(out[..., 3].tobytes(), value[..., 3].tobytes())
            self.assertEqual(m['alpha'], 'input-bits-preserved')

    def test_alpha_only_preserves_RGB_bits_without_signal_roundtrip(self):
        value = pattern(); value[0, 0, :3] = [-0., -.3, 1.7]
        out, m = self.apply(value, effect(planes=8, input_signal=SRGB, output_signal=SRGB))
        self.assertEqual(out[..., :3].tobytes(), value[..., :3].tobytes())
        self.assertTrue(m['alpha_only_RGB_conversion_bypassed'])
        np.testing.assert_allclose(out[..., 3], dense(value, 2)[..., 3], atol=6e-8, rtol=0)

    def test_premultiplied_blur_removes_hidden_RGB_halo(self):
        value = np.zeros((5, 17, 4), np.float32); value[..., :3] = [1, 0, 0]; value[:, 8:] = [.4, .4, .4, 1]
        for name, kind in (('avgblur', 'average_blur'), ('boxblur', 'box_blur')):
            straight, _ = self.apply(value, effect(name, radius=2))
            out, _ = self.apply(value, effect(name, radius=2, alpha_mode='premultiplied'))
            np.testing.assert_allclose(out, dense(value, 2, kind=kind, premultiplied=True), atol=8e-8, rtol=0)
            self.assertGreater(straight[2, 7, 0]-straight[2, 7, 1], .1)

    def test_tiny_positive_coverage_has_no_epsilon_floor(self):
        value = fixture.rgba((.25, .5, .75, 1e-30), shape=(7, 13))
        out, _ = self.apply(value, effect('boxblur', radius=128, power=4, alpha_mode='premultiplied'))
        self.assertEqual(out.tobytes(), value.tobytes())

    def test_tiny_coverage_far_after_opaque_pixels_is_not_lost_to_prefix_cancellation(self):
        value = fixture.rgba((.25, .5, .75, 1e-30), shape=(3, 71)); value[:, :16, 3] = 1
        for kind in ('avgblur', 'boxblur'):
            out, m = self.apply(value, effect(kind, radius_x=2.5, radius_y=0, alpha_mode='premultiplied'))
            np.testing.assert_array_equal(out[:, 25:], value[:, 25:])
            self.assertEqual(m['window_sum'], 'subtraction-free-disjoint-power-of-two-ranges')

    def test_local_normal_RGB_after_huge_distant_sample_is_preserved(self):
        value = fixture.rgba((.25, .5, .75, .5), shape=(3, 71)); value[:, 0, 0] = 1e30
        out, _ = self.apply(value, effect(radius_x=2, radius_y=0))
        np.testing.assert_array_equal(out[:, 25:], value[:, 25:])

    def test_all_zero_coverage_clears_hidden_RGB_explicitly(self):
        value = pattern(); value[..., 3] = 0
        out, m = self.apply(value, effect(alpha_mode='premultiplied'))
        self.assertTrue(np.all(out == 0)); self.assertEqual(m['zero_blurred_coverage_pixels'], value.shape[0]*value.shape[1])

    def test_intensity_mixes_linear_RGB_and_coverage_independently(self):
        value = pattern(); out, m = self.apply(value, effect(radius_x=1.7, radius_y=.7, intensity=.37, alpha_mode='premultiplied'))
        expected = value.astype(np.float64)*.63 + dense(value, 1.7, .7, premultiplied=True).astype(np.float32).astype(np.float64)*.37
        np.testing.assert_allclose(out, expected, atol=2e-7, rtol=0); self.assertEqual(m['alpha_mix'], 'linear-coverage')

    def test_srgb_filter_domain_and_linear_intensity_are_explicit(self):
        value = pattern(); value[..., :3] = np.clip(value[..., :3], 0, 1)
        data = value.copy(); rgb = value[..., :3].astype(np.float64)
        data[..., :3] = np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1/2.4)-.055)
        filtered = dense(data, 1.3).astype(np.float32); rgb = filtered[..., :3].astype(np.float64)
        decoded = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4).astype(np.float32)
        out, _ = self.apply(value, effect(radius=1.3, input_signal=SRGB, output_signal=SRGB, intensity=.4))
        np.testing.assert_allclose(out[..., :3], value[..., :3].astype(np.float64)*.6+decoded.astype(np.float64)*.4, atol=1.5e-7, rtol=0)

    def test_output_gamut_clip_is_separate_from_alpha(self):
        value = fixture.rgba((-.25, .5, 1.75, .375)); out, m = self.apply(value, effect(output_gamut='clip'))
        np.testing.assert_array_equal(out[..., :3], np.clip(value[..., :3], 0, 1)); np.testing.assert_array_equal(out[..., 3], value[..., 3])
        self.assertEqual(m['output_clipped_components'], value.shape[0]*value.shape[1]*2)

    def test_distinct_signals_are_interpreted_after_filter(self):
        value = np.clip(pattern(), 0, 1); filtered = dense(value, 1.3).astype(np.float32)
        rgb = filtered[..., :3].astype(np.float64); expected = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
        out, _ = self.apply(value, effect(radius=1.3, output_signal=SRGB))
        np.testing.assert_allclose(out[..., :3], expected, atol=1.5e-7, rtol=0)

    def test_zero_intensity_validates_whole_surface_before_identity(self):
        value = pattern(); value[0, 0, 0] = -0.
        for options in ({'intensity': 0, 'output_gamut': 'clip'}, {'planes': 0}):
            out, _ = self.apply(value, effect(**options)); self.assertEqual(out.tobytes(), value.tobytes())
        value[-1, -1, 3] = np.nan; self.bad(lambda: self.apply(value, effect(intensity=0)))

    def test_all_six_easings_sample_original_fractional_author_tick(self):
        for mode, expected in (('linear', 1.), ('hold', 0.), ('ease_in', .25), ('ease_out', 1.75), ('ease_in_out', .5), ('bezier', 1.)):
            e = effect(); e['keyframes'] = [track('radius', 0, 4, mode)]
            if mode == 'bezier': e['keyframes'][0]['keyframes'][0]['control_points'] = [0., 0., 1., 1.]
            sampled = state_at(compile_spatial(e), Fraction(25, 1))
            self.assertAlmostEqual(sampled['radius_x'], expected, places=10)
            self.assertEqual(sampled['radius_x'], sampled['radius_y'])

    def test_independent_axis_tracks_override_linked_master(self):
        e = effect(radius_y=.7); e['keyframes'] = [track('radius', 0, 8), track('radius_x', 1, 3)]
        self.assertEqual(state_at(compile_spatial(e), 50), {'radius': 4., 'radius_x': 2., 'radius_y': .7, 'intensity': 1.})
        p = compile_spatial(e); e['parameters']['radius_y'] = 99; e['keyframes'][0]['keyframes'][0]['value'] = 99
        self.assertEqual(state_at(p, 50)['radius_y'], .7)

    def test_legacy_zero_Y_inherits_X_but_canonical_zero_disables_Y(self):
        legacy = compile_spatial(effect(sizeX=3, sizeY=0)); explicit = compile_spatial(effect(radius_x=3, radius_y=0))
        self.assertEqual(state_at(legacy, 0)['radius_y'], 3); self.assertEqual(state_at(explicit, 0)['radius_y'], 0)
        e = effect(size_x=3); e['keyframes'] = [track('parameters.sizeY', 0, 0)]
        self.assertEqual(state_at(compile_spatial(e), 50)['radius_y'], 3)

    def test_duplicate_aliases_and_keyframe_locations_reject(self):
        for p in ({'size_x': 1, 'radius_x': 1}, {'sizeY': 1, 'size_y': 1}): self.bad(lambda p=p: compile_spatial(effect(**p)))
        e = effect(); e['keyframes'] = [track('radius_x', 0, 1), track('sizeX', 0, 1)]; self.bad(lambda: compile_spatial(e))
        e = effect(keyframes=[]); e['keyframes'] = []; self.bad(lambda: compile_spatial(e))

    def test_parameter_bounds_types_and_unknown_fields_reject(self):
        for p in ({'radius': 1025}, {'radius': True}, {'radius': float('nan')}, {'intensity': -1}, {'unknown': 0},
                  {'input_signal': None}, {'output_signal': LINEAR | {'auto': True}}, {'planes': 16}, {'planes': 1.},
                  {'alpha_mode': 'auto'}, {'alpha_mode': 'premultiplied', 'planes': 7}, {'output_gamut': 'auto'}):
            self.bad(lambda p=p: compile_spatial(effect(**p)))
        self.bad(lambda: compile_spatial(effect('boxblur', radius=129)))
        self.bad(lambda: compile_spatial(effect() | {'radius': 1})); self.bad(lambda: compile_spatial(effect() | {'enabled': 1}))

    def test_power_is_static_bounded_and_only_valid_for_box(self):
        for p in (-1, 5, 1.5, True): self.bad(lambda p=p: compile_spatial(effect('boxblur', power=p)))
        self.bad(lambda: compile_spatial(effect(power=1)))
        e = effect('boxblur'); e['keyframes'] = [track('power', 1, 4)]; self.bad(lambda: compile_spatial(e))

    def test_forged_plans_are_revalidated(self):
        p = compile_spatial(effect())
        for forged in (replace(p, values=p.values[:-1]), replace(p, power=True), replace(p, input_signal=None),
                       replace(p, axis_overrides=('radius_y', 'radius_x')), replace(p, legacy_zero_y_inherits=1), replace(p, tracks_json=' []')):
            self.bad(lambda forged=forged: state_at(forged, 0))

    def test_invalid_author_clocks_reject(self):
        p = compile_spatial(effect())
        for tick in (True, -1, float('nan'), '0'): self.bad(lambda tick=tick: state_at(p, tick))

    def test_duration_keyframe_budget_and_disabled_effects(self):
        e = effect(); e['keyframes'] = [track('radius', 0, 8)]
        self.assertEqual(validate_spatial(e, duration_tick=100), []); self.assertTrue(validate_spatial(e, duration_tick=99))
        e['keyframes'][0]['keyframes'] = [{'at_tick': i, 'value': 0} for i in range(1025)]; self.bad(lambda: compile_spatial(e))
        self.assertEqual(validate_spatial({'type': 'avgblur', 'enabled': False, 'parameters': {'bad': 0}}), [])

    def test_readonly_inputs_and_tile_sizes_are_bit_identical(self):
        value = pattern(); value.flags.writeable = False
        for kind in ('avgblur', 'boxblur'):
            e = effect(kind, radius_x=1.7, radius_y=.7, alpha_mode='premultiplied')
            expected, _ = self.apply(value, e, tile_pixels=1)
            for tile in (7, 16384, 262144):
                out, _ = self.apply(value, e, tile_pixels=tile); self.assertEqual(out.tobytes(), expected.tobytes())

    def test_surface_layout_and_late_invalid_values_preserve_caller(self):
        value = pattern(); value[-1, -1, 3] = 1.1; before = value.tobytes()
        self.bad(lambda: self.apply(value, tile_pixels=1)); self.assertEqual(value.tobytes(), before)
        for bad in (value.astype(np.float64), value[:, ::2], np.zeros((2, 3, 3), np.float32)):
            self.bad(lambda bad=bad: self.apply(bad))
        value[-1, -1, 3] = .5; value[-1, -1, 0] = np.inf; self.bad(lambda: self.apply(value))

    def test_4K_admission_shrinks_conversion_tile_without_raising_memory_limit(self):
        pixels = 3840*2160
        tile, estimate, m = admit_spatial(surface_bytes=pixels*16, pixels=pixels, tile_pixels=65536, tracks_bytes=2,
            retained_table_bytes=0, max_working_bytes=MAX_WORKING_BYTES, error=lambda k, s: AppError(k, s))
        self.assertEqual(tile, 3903); self.assertLessEqual(estimate, 768*1024*1024)
        self.assertTrue(m['adaptive_tile_reduction']); self.assertEqual(m['fixed_spatial_working_bytes'], 6*pixels*16+1048576+8)

    def test_gaussian_adaptive_small_budget_matches_original_full_tile_pixels(self):
        value = pattern((65, 71)); e = effect('blur', radius_x=2, radius_y=.7, steps=3, alpha_mode='premultiplied')
        plan = compile_gaussian(e); expected, _ = apply_gaussian(value, plan, 0, working_signal=WORKING)
        actual, m = apply_gaussian(value, plan, 0, working_signal=WORKING, max_working_bytes=2*1024*1024)
        self.assertEqual(actual.tobytes(), expected.tobytes()); self.assertTrue(m['workspace_admission']['adaptive_tile_reduction'])

    def test_spatial_adaptive_small_budget_matches_normal_budget(self):
        value = pattern((65, 71))
        for kind in ('avgblur', 'boxblur'):
            e = effect(kind, radius_x=1.7, radius_y=.7, alpha_mode='premultiplied')
            expected, _ = self.apply(value, e); actual, m = self.apply(value, e, max_working_bytes=2*1024*1024)
            self.assertEqual(actual.tobytes(), expected.tobytes()); self.assertTrue(m['workspace_admission']['adaptive_tile_reduction'])

    def test_retained_tables_and_full_surface_budget_reject_transactionally(self):
        value = pattern(); before = value.tobytes()
        for options in ({'max_working_bytes': 1}, {'retained_table_bytes': MAX_WORKING_BYTES}, {'tile_pixels': 0}, {'tile_pixels': True},
                        {'retained_table_bytes': -1}, {'max_working_bytes': True}):
            self.bad(lambda options=options: self.apply(value, **options)); self.assertEqual(value.tobytes(), before)
        self.bad(lambda: self.apply(np.zeros((1, 16385, 4), np.float32)))

    def test_minimum_one_pixel_tile_budget_is_an_exact_admission_boundary(self):
        value = pattern(); plan = compile_spatial(effect())
        exact = 6*value.nbytes+4*len(plan.tracks_json.encode('utf8'))+1048576+2048
        out, m = self.apply(value, max_working_bytes=exact); self.assertEqual(m['actual_tile_pixels_limit'], 1)
        self.assertEqual(m['estimated_working_bytes'], exact); self.bad(lambda: self.apply(value, max_working_bytes=exact-1))

    def test_mid_line_cancel_preserves_caller(self):
        value = pattern((65, 71)); before = value.tobytes(); count = [0]
        def cancel(): count[0] += 1; return count[0] > 12
        self.bad(lambda: self.apply(value, effect('boxblur', radius=3, power=4), cancel=cancel), 'RENDER_CANCELLED')
        self.assertEqual(value.tobytes(), before)

    def test_callback_exception_is_preserved(self):
        value = pattern(); before = value.tobytes()
        def crash(): raise RuntimeError('callback failed')
        with self.assertRaisesRegex(RuntimeError, 'callback failed'): self.apply(value, cancel=crash)
        self.assertEqual(value.tobytes(), before)

    def test_signal_overflow_rejects_without_mutating_caller(self):
        value = fixture.rgba((3e38, 3e38, 3e38, .5)); before = value.tobytes()
        self.bad(lambda: self.apply(value, effect(output_signal=SRGB))); self.assertEqual(before, value.tobytes())
        self.bad(lambda: apply_spatial(value, compile_spatial(effect()), 0, working_signal=ColorSignal(**SRGB)))

    def test_ordered_tone_gaussian_and_spatial_filters_are_not_reordered(self):
        from test_float_tone import effect as tone
        compiler = EffectCompiler(resource_root=None, working_signal=WORKING); value = pattern()
        rows = [tone('gamma', gamma=1.3), effect('blur', radius=.7), effect('boxblur', radius=1.7, alpha_mode='premultiplied'), effect(radius=.7), tone('hue', degrees=20)]
        actual, m = compiler.apply(value, compiler.compile(rows), 50); expected = value
        for row in rows: expected, _ = compiler.apply(expected, compiler.compile([row]), 50)
        self.assertEqual(actual.tobytes(), expected.tobytes()); self.assertEqual(m['alpha'], 'explicit-per-effect-alpha-mapping')
        reverse, _ = compiler.apply(value, compiler.compile(list(reversed(rows))), 50); self.assertFalse(np.array_equal(actual, reverse))

    def test_presentation_window_preserves_original_radius_clock(self):
        value = pattern((4, 8)); p, s = fixture.image_project(value, duration=200); e = effect(); e['keyframes'] = [track('radius', 0, 3, stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200, source_out_tick=200, effects=[e])
        host = FloatTimeline(p, 'main', s, working_signal=WORKING); full = [host.render_frame(i)[0] for i in range(20)]
        selected = copy.deepcopy(p); selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,
            presentation_window={'version': 1, 'authored_start_tick': 0, 'authored_duration_tick': 200, 'offset_tick': 70})
        host = FloatTimeline(selected, 'main', s, working_signal=WORKING)
        for i in range(6): self.assertEqual(host.render_frame(i)[0].tobytes(), full[i+7].tobytes())

    def test_nested_reverse_preserves_parent_and_child_author_clocks(self):
        value = pattern((4, 8)); p, s = fixture.image_project(value, duration=200)
        child = copy.deepcopy(p['sequences'][0]); child['id'] = 'child'; e = effect(); e['keyframes'] = [track('radius', 0, 2, 'hold', stop=160)]
        child['tracks'][0]['clips'][0].update(duration_tick=200, source_out_tick=200, effects=[e])
        parent = p['sequences'][0]['tracks'][0]['clips'][0]; parent.pop('asset_id')
        parent.update(sequence_id='child', duration_tick=200, source_out_tick=200, reverse=True, effects=[effect('boxblur', radius_x=.3, radius_y=0)])
        p['sequences'].append(child); out, _ = FloatTimeline(p, 'main', s, working_signal=WORKING).render_frame(4)
        expected, _ = self.apply(value, e, tick=np.nextafter(160., -np.inf)); expected, _ = self.apply(expected, parent['effects'][0], tick=40)
        np.testing.assert_allclose(out, expected, atol=3e-7, rtol=0)

    def test_validator_routes_both_native_means_and_preserves_legacy_engine(self):
        from ai_ad_editor.validator import validate_project
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.visual(np.ones((2, 16, 32, 4), np.float32)*.5); case.s['duration_tick'] = 18000
            for kind in ('avgblur', 'boxblur'):
                e = effect(kind); e['keyframes'] = [track('radius', 0, 6, stop=9000)]; case.s['tracks'][0]['clips'][0]['effects'] = [e]
                result = validate_project(case.root, case.p); self.assertTrue(result['ok'], result)
                e['parameters'].pop('input_signal'); self.assertFalse(validate_project(case.root, case.p)['ok'])
            case.p['settings'].pop('pixel_pipeline'); case.s['tracks'][0]['clips'][0]['effects'] = [{'type': 'avgblur', 'parameters': {'size_x': 3}}]
            self.assertTrue(validate_project(case.root, case.p)['ok'])
        finally: case.doCleanups()

    def preview_pixels(self, kind):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000; value = np.clip(pattern((16, 32)), 0, 1)
            pixels = case.visual(np.stack((value, value))); audio = case.audio()
            parameters = {'radius_x': 1.7, 'radius_y': .7, 'alpha_mode': 'premultiplied'}
            if kind == 'box_blur': parameters['power'] = 3
            case.s['tracks'][0]['clips'][0]['effects'] = [effect(kind, **parameters)]
            result = case.execute(end=2); actual = case.reference(result)
            source = np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535)
            expected = np.stack([dense(v, 1.7, .7, kind, parameters.get('power', 1), premultiplied=True).astype(np.float32) for v in source])
            expected[..., :3] *= expected[..., 3:4]; expected[..., 3] = 1
            np.testing.assert_allclose(actual, expected, atol=2e-7, rtol=0); self.assertEqual(case.pcm(result), audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')), np.rint(actual[0].astype(np.float64)*65535), atol=1, rtol=0)
            case.assert_clean()
        finally: case.doCleanups()

    def test_real_average_preview_PCM_and_PNG16_match_independent_pixels(self): self.preview_pixels('average_blur')

    def test_real_box_preview_PCM_and_PNG16_match_independent_pixels(self): self.preview_pixels('box_blur')

    def test_real_formal_render_and_preview_share_spatial_transport(self):
        from ai_ad_editor.render import render_project
        from ai_ad_editor.project import project_write_lock
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000; value = np.clip(pattern((16, 32)), 0, 1)
            case.visual(np.stack((value, value))); case.audio(); case.s['tracks'][0]['clips'][0]['effects'] = [effect('boxblur', radius=1.7)]
            actual = case.reference(case.execute(end=2))
            with project_write_lock(case.root): formal = render_project(case.root, case.p, case.s, case.root/'renders/spatial.mkv')
            manifest = json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload = np.moveaxis(np.rint(actual[..., [1, 2, 0, 3]].astype(np.float64)*65535).astype('<u2'), 3, 1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'], 'sha256:'+hashlib.sha256(payload).hexdigest())
            case.assert_clean()
        finally: case.doCleanups()

    def test_real_cache_hit_and_type_power_radius_changes_invalidate(self):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000; value = np.clip(pattern((16, 32)), 0, 1); case.visual(np.stack((value, value))); case.audio()
            e = effect('boxblur', radius=1); case.s['tracks'][0]['clips'][0]['effects'] = [e]
            one = case.execute(end=2); self.assertTrue(case.execute(end=2)['cache_hit'])
            e['parameters']['power'] = 2; two = case.execute(end=2); self.assertNotEqual(one['cache_key'], two['cache_key'])
            e['parameters'].pop('power'); e['type'] = 'avgblur'; three = case.execute(end=2); self.assertNotEqual(two['cache_key'], three['cache_key'])
            e['parameters']['radius'] = 2; four = case.execute(end=2); self.assertNotEqual(three['cache_key'], four['cache_key']); case.assert_clean()
        finally: case.doCleanups()

    def test_capabilities_disabled_effects_and_unsupported_guard(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        manifest = build_capability_manifest()['capabilities']; row = manifest['timeline_native_float_spatial_means']
        self.assertIn('native_integer_quantization_and_fixed_reciprocals_not_reproduced', row['limits'])
        self.assertIn('full_spatial_scratch_with_adaptive_conversion_tiles', manifest['timeline_native_float_gaussian']['features'])
        compiler = EffectCompiler(resource_root=None, working_signal=WORKING)
        self.assertEqual(compiler.compile([{'type': 'avgblur', 'enabled': False, 'parameters': {'bad': True}}]), ())
        self.bad(lambda: compiler.compile([{'type': 'hqdn3d'}]), 'FLOAT_TIMELINE_UNSUPPORTED')
