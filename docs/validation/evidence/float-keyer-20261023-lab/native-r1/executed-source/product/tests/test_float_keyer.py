"""Independent scalar/dense mattes, real native filters and actual delivery."""
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
from ai_ad_editor.float_color_signal import ColorSignal, convert_rgba
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_keyer import (ALIASES, BOUNDS, KeyerPlan, apply_keyer,
    compile_keyer, state_at, validate_keyer)
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
import test_float_preview as preview_fixture
import test_float_timeline as fixture
from test_float_tone import from_codes

LINEAR = {'primaries':'bt709', 'transfer':'linear'}
WORKING = ColorSignal(**LINEAR)
NATIVE_CALLS = []


def effect(kind='chroma_key', **parameters):
    return {'type':kind, 'parameters':{'input_signal':dict(LINEAR), **parameters}}


def track(name, a, b, mode='linear', stop=100):
    key = {'at_tick':0, 'value':a, 'interpolation':mode}
    if mode == 'bezier':
        key['control_points'] = [1/3, 0., 2/3, 1.]
    return {'property':name, 'keyframes':[key, {'at_tick':stop, 'value':b, 'interpolation':'linear'}]}


def pattern(shape=(9, 13), seed=110):
    rng = np.random.default_rng(seed)
    value = rng.uniform(-.1, 1.15, (*shape, 4)).astype(np.float32)
    value[..., 3] = rng.uniform(.02, 1., shape).astype(np.float32)
    value[0, 0, :3] = [0., 1., 0.]
    return value


def dense_mean(size, radius):
    """Direct weights and endpoint indices; no production prefix sums."""
    result = np.zeros((size, size), np.float64)
    n = math.floor(radius)
    for r, fraction in ((n, 1-(radius-n)), (n+1, radius-n)):
        if fraction == 0:
            continue
        for position in range(size):
            for offset in range(-r, r+1):
                result[position, min(size-1, max(0, position+offset))] += fraction/(2*r+1)
    return result


def oracle(value, *, key=(0., 1., 0.), similarity=.1, blend=0., feather=0., intensity=1.,
           metric='rgb', matrix='bt709', ranges='full', radius=1, invert=False,
           despill=0., spill_axis='auto', despill_edges=False, input_gamut='preserve', output_gamut='preserve'):
    """Scalar color algebra followed by independent dense neighbourhood products."""
    rgb = value[..., :3].astype(np.float64)
    distance_rgb = np.clip(rgb, 0, 1) if input_gamut == 'clip' else rgb
    key = np.asarray(key, np.float64)
    distances = np.empty(value.shape[:2], np.float64)
    coefficients = {'bt709':(.2126, .0722), 'smpte170m':(.299, .114),
                    'bt470bg':(.299, .114), 'bt2020nc':(.2627, .0593)}
    for y in range(len(value)):
        for x in range(value.shape[1]):
            r, g, b = distance_rgb[y, x]-key
            if metric == 'rgb':
                distances[y, x] = math.sqrt((r*r+g*g+b*b)/3)
            else:
                kr, kb = coefficients[matrix]
                luma = kr*r+(1-kr-kb)*g+kb*b
                cb, cr = (b-luma)/(2-2*kb), (r-luma)/(2-2*kr)
                distances[y, x] = math.hypot(cb, cr)/math.sqrt(2)*(1 if ranges == 'full' else 224/255)
    if metric == 'chroma':
        distances = dense_mean(value.shape[0], radius) @ distances @ dense_mean(value.shape[1], radius).T
    matte = np.clip((distances-similarity)/blend, 0, 1) if blend else (distances > similarity).astype(np.float64)
    if invert:
        matte = 1-matte
    matte = np.clip(dense_mean(value.shape[0], feather) @ matte @ dense_mean(value.shape[1], feather).T, 0, 1)
    changed = rgb.copy()
    axis = {'red':0, 'green':1, 'blue':2}.get(spill_axis)
    if spill_axis == 'auto' and max(key)-min(key) > 1e-12:
        axis = int(np.argmax(key))
    if axis is not None:
        for y in range(len(value)):
            for x in range(value.shape[1]):
                neighbors = [rgb[y, x, i] for i in range(3) if i != axis]
                amount = max(0., rgb[y, x, axis]-max(neighbors))*despill
                changed[y, x, axis] -= amount*(1-matte[y, x] if despill_edges else 1)
    if output_gamut == 'clip':
        changed = np.clip(changed, 0, 1)
    result = value.copy()
    if intensity:
        result[..., :3] = rgb*(1-intensity)+changed*intensity
        result[..., 3] = value[..., 3].astype(np.float64)*(1-intensity+intensity*matte)
    return result


def native(value, filter_text, *, bits=8, yuv=False, scalar=False):
    fmt = ('yuva444p' if bits == 8 else f'yuva444p{bits}le') if yuv else ('rgba' if bits == 8 else 'rgba64le')
    dtype = np.uint8 if bits == 8 else '<u2'
    h, w = value.shape[:2]
    codes = value.astype(dtype)
    payload = (np.moveaxis(codes, -1, 0) if yuv else codes).tobytes()
    command = [ffmpeg_path(), '-nostdin', '-v', 'error']
    if scalar:
        command += ['-cpuflags', '0']
    command += ['-filter_threads', '1', '-f', 'rawvideo', '-pixel_format', fmt, '-video_size', f'{w}x{h}',
        '-i', 'pipe:0', '-vf', filter_text, '-frames:v', '1', '-threads', '1', '-pix_fmt', fmt, '-f', 'rawvideo', 'pipe:1']
    p = subprocess.run(command, input=payload, capture_output=True, timeout=30)
    NATIVE_CALLS.append({'command':command, 'bits':bits, 'pixel_format':fmt, 'exit_code':p.returncode,
        'input_sha256':hashlib.sha256(payload).hexdigest(), 'output_sha256':hashlib.sha256(p.stdout).hexdigest()})
    if p.returncode:
        raise AssertionError(p.stderr.decode(errors='replace'))
    result = np.frombuffer(p.stdout, dtype).reshape((4, h, w) if yuv else (h, w, 4))
    return np.moveaxis(result, 0, -1).copy() if yuv else result.copy()


class FloatKeyerTests(unittest.TestCase):
    def apply(self, value, e=None, tick=0, **kw):
        return apply_keyer(value, compile_keyer(e or effect()), tick, working_signal=WORKING, **kw)

    def bad(self, fn, code=None):
        with self.assertRaises(AppError) as caught:
            fn()
        if code:
            self.assertEqual(caught.exception.code, code)

    def compare(self, **p):
        value = pattern()
        parameters = dict(p)
        if 'key' in p:
            parameters['color'] = list(parameters.pop('key'))
        if 'ranges' in p:
            parameters['range'] = parameters.pop('ranges')
        if 'radius' in p:
            parameters['chroma_radius'] = parameters.pop('radius')
        actual, _ = self.apply(value, effect(**parameters))
        np.testing.assert_allclose(actual, oracle(value, **p), rtol=0, atol=2e-6)

    def test_aliases_use_same_RGB_distance_and_incoming_coverage(self):
        value = pattern()
        for name in ALIASES:
            out, meta = self.apply(value, effect(name))
            np.testing.assert_allclose(out, oracle(value), rtol=0, atol=1e-7)
            self.assertEqual(meta['metric'], 'rgb'); self.assertTrue(meta['incoming_coverage_preserved'])

    def test_explicit_color_tokens_and_named_green_is_half_intensity(self):
        for color, rgb in [('0x00ff00',(0,1,0)),('#123456',(18/255,52/255,86/255)),
                           ('blue',(0,0,1)),('green',(0,128/255,0)),('lime',(0,1,0)),([.1,.3,.2],(.1,.3,.2))]:
            plan = compile_keyer(effect(color=color)); values = state_at(plan, 0)
            self.assertEqual(tuple(values['key_'+n] for n in ('red','green','blue')), rgb)

    def test_primary_colors_have_analytic_normalized_distance(self):
        value = np.array([[[0,1,0,.5],[1,0,0,.7],[0,0,1,.2],[0,.5,0,1]]], np.float32)
        out, _ = self.apply(value, effect(similarity=0, blend=1))
        expected = [0, math.sqrt(2/3)*float(value[0,1,3]), math.sqrt(2/3)*float(value[0,2,3]), .5/math.sqrt(3)]
        np.testing.assert_allclose(out[0,:,3], expected, atol=5e-8, rtol=0)

    def test_soft_matte_independent_scalar_formula(self): self.compare(similarity=.12, blend=.7)
    def test_partial_intensity_independent_coverage_mix(self): self.compare(similarity=.2, blend=.45, intensity=.375)
    def test_feather_fractional_dense_reference(self): self.compare(similarity=.25, blend=.6, feather=2.375)
    def test_feather_larger_than_image_replicates_endpoints(self): self.compare(similarity=.3, feather=17.25)
    def test_inversion_precedes_feather_and_input_alpha(self): self.compare(similarity=.4, blend=.3, invert=True, feather=1.6)
    def test_declared_distance_input_clip_leaves_original_RGB(self): self.compare(similarity=.3, blend=.5, input_gamut='clip')
    def test_explicit_output_clip_changes_RGB_only_as_requested(self): self.compare(similarity=.1, output_gamut='clip')
    def test_green_axis_despill(self): self.compare(despill=.8, spill_axis='green', blend=.7)
    def test_blue_axis_despill(self): self.compare(key=(0,0,1), despill=.65, spill_axis='blue', feather=.5)
    def test_red_axis_despill(self): self.compare(key=(1,0,0), despill=1., spill_axis='red', intensity=.7)
    def test_auto_axis_and_edge_only_despill(self): self.compare(despill=.9, blend=.8, despill_edges=True, feather=1.5)

    def test_neutral_key_has_no_automatic_despill_axis(self):
        value = pattern()
        out, meta = self.apply(value, effect(color=[.3,.3,.3], despill=1))
        self.assertIsNone(meta['despill_axis']); self.assertTrue(meta['RGB_bits_preserved'])
        self.assertEqual(out[...,:3].tobytes(), value[...,:3].tobytes())

    def test_RGB_hidden_values_and_signed_zero_bits_preserved_without_despill(self):
        value = pattern(); value[0,1] = [-0.,-0.,1.,-0.]
        out, meta = self.apply(value, effect(blend=.6, feather=1.5))
        self.assertEqual(out[...,:3].tobytes(), value[...,:3].tobytes()); self.assertTrue(meta['RGB_bits_preserved'])
        self.assertEqual(out[0,1,3].tobytes(), value[0,1,3].tobytes())

    def test_zero_alpha_is_never_resurrected_by_feather_or_inversion(self):
        value = pattern(); value[...,3] = 0
        out, _ = self.apply(value, effect(invert=True, feather=3.5, despill=.6))
        self.assertEqual(np.count_nonzero(out[...,3]), 0)

    def test_incoming_partial_alpha_is_never_increased(self):
        value = pattern()
        for intensity in (1e-12,.2,1):
            out, _ = self.apply(value, effect(blend=.9, feather=2.5, intensity=intensity))
            self.assertTrue(np.all(out[...,3] <= value[...,3])); self.assertTrue(np.all(out[...,3] >= 0))

    def test_zero_intensity_is_bit_exact_and_owned(self):
        value = pattern(); value[0,1,0] = -0.
        out, _ = self.apply(value, effect(intensity=0, despill=1, output_gamut='clip'))
        self.assertEqual(out.tobytes(), value.tobytes()); self.assertFalse(np.shares_memory(value,out))

    def test_continuous_tiny_blend_is_not_silently_native_hard_threshold(self):
        value = np.array([[[0,1-.2*math.sqrt(3),0,.7]]], np.float32)
        out, _ = self.apply(value, effect(similarity=.2-2e-6, blend=5e-6))
        hard, _ = self.apply(value, effect(similarity=.2-2e-6, blend=5e-6, arithmetic='native_coefficients'))
        self.assertGreater(out[0,0,3],0); self.assertLess(out[0,0,3],hard[0,0,3])

    def test_independent_chroma_all_matrices_and_both_ranges(self):
        for matrix in ('bt709','smpte170m','bt470bg','bt2020nc'):
            for ranges in ('full','limited'):
                self.compare(metric='chroma', matrix=matrix, ranges=ranges, similarity=.08, blend=.5, radius=1)

    def test_chroma_zero_and_four_pixel_neighbourhoods(self):
        for radius in (0,4):
            self.compare(metric='chroma', matrix='bt709', ranges='full', radius=radius, similarity=.2, blend=.4)

    def test_chroma_mean_of_distances_and_deterministic_corners(self):
        self.compare(metric='chroma', matrix='bt2020nc', ranges='limited', radius=2, similarity=.17, blend=.25, feather=.75)

    def test_single_row_single_column_and_single_pixel(self):
        for shape in ((1,13),(11,1),(1,1)):
            value = pattern(shape)
            out, _ = self.apply(value, effect(feather=2.4, blend=.5))
            np.testing.assert_allclose(out,oracle(value,feather=2.4,blend=.5),atol=1e-6,rtol=0)

    def test_float32_more_than_65536_distinct_alpha_levels(self):
        value = np.zeros((257,513,4),np.float32)
        value[...,0] = np.linspace(.001,.999,value.shape[0]*value.shape[1],dtype=np.float32).reshape(value.shape[:2])
        value[...,3] = 1
        out, _ = self.apply(value,effect(color='black',similarity=0,blend=1))
        self.assertGreater(len(np.unique(out[...,3])),65536)

    def test_key_RGB_channels_override_static_color_and_animate(self):
        e = effect(color='blue', key_green=.7); e['keyframes'] = [track('key_red',0,1)]
        values = state_at(compile_keyer(e),25)
        self.assertEqual((values['key_red'],values['key_green'],values['key_blue']),(.25,.7,1.))

    def test_all_six_author_easings_sample_original_clock(self):
        values = {'linear':.25,'hold':0.,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.15625}
        for mode, fraction in values.items():
            e = effect(); e['keyframes'] = [track('blend',.1,.9,mode)]
            self.assertAlmostEqual(state_at(compile_keyer(e),25)['blend'],.1+.8*fraction,places=10)

    def test_large_integer_and_fraction_author_clock_retains_offset(self):
        start = 2**53+11
        e = effect(); e['keyframes'] = [{'property':'similarity','keyframes':[
            {'at_tick':start,'value':.2,'interpolation':'linear'},
            {'at_tick':start+3,'value':.8,'interpolation':'linear'}]}]
        self.assertAlmostEqual(state_at(compile_keyer(e),Fraction(2*start+3,2))['similarity'],.5)

    def test_author_plan_does_not_retain_mutable_input(self):
        e = effect(color=[0,1,0]); e['keyframes'] = [track('feather',0,3)]
        original = copy.deepcopy(e); plan = compile_keyer(e)
        e['parameters']['color'][1] = 0; e['keyframes'][0]['keyframes'][1]['value'] = 9
        self.assertEqual(state_at(plan,100)['feather'],3)
        self.assertEqual(state_at(plan,100)['key_green'],1); self.assertNotEqual(e,original)

    def test_unknown_fields_and_unsupported_color_alpha_are_rejected(self):
        for parameters in ({'unknown':1},{'color':'green@0.5'},{'color':'#00ff00ff'},
                           {'color':'https://example.com/key'},{'color':[0,True,0]},
                           {'key_red':.3,'red':.4},{'similarity':float('nan')},{'blend':True}):
            self.bad(lambda p=parameters:compile_keyer(effect(**p)))

    def test_metric_matrix_neighbourhood_and_static_types_are_strict(self):
        for parameters in ({'metric':'hsv'},{'metric':'chroma'},{'matrix':'bt709'},
                           {'chroma_radius':1},{'invert':1},{'despill_edges':'yes'},
                           {'spill_axis':'cyan'},{'arithmetic':'integer'},{'input_gamut':'auto'}):
            self.bad(lambda p=parameters:compile_keyer(effect(**p)))

    def test_track_alias_duplicates_unknown_boolean_and_duration_reject(self):
        for tracks in ([track('green',0,1),track('key_green',0,1)],[track('invert',0,1)],
                       [track('color',0,1)],[track('metric',0,1)]):
            e = effect(); e['keyframes'] = tracks
            self.bad(lambda:compile_keyer(e))
        e = effect(); e['keyframes'] = [track('blend',0,1)]
        self.assertTrue(validate_keyer(e,duration_tick=50)); self.assertEqual(validate_keyer(e,duration_tick=100),[])

    def test_forged_immutable_plan_is_revalidated(self):
        plan = compile_keyer(effect())
        for broken in (replace(plan,values=()),replace(plan,values=plan.values+(plan.values[0],)),
                       replace(plan,invert=1),replace(plan,tracks_json='[]x'),replace(plan,metric='other')):
            self.bad(lambda p=broken:apply_keyer(pattern(),p,0,working_signal=WORKING))

    def test_surface_dtype_shape_layout_and_linear_working_signal_reject(self):
        for value in (pattern().astype(np.float64),pattern()[...,:3],pattern()[:,::2],np.zeros((0,1,4),np.float32)):
            self.bad(lambda a=value:self.apply(a))
        self.bad(lambda:apply_keyer(pattern(),compile_keyer(effect()),0,working_signal=ColorSignal('bt709','srgb')))

    def test_readonly_input_and_conversion_tiles_are_bit_identical(self):
        value = pattern((17,23)); value.flags.writeable = False
        e = effect(feather=2.375,despill=.4,blend=.7)
        one, _ = self.apply(value,e,tile_pixels=1)
        many, _ = self.apply(value,e,tile_pixels=16384)
        self.assertEqual(one.tobytes(),many.tobytes())

    def test_late_invalid_values_reject_before_changes(self):
        for channel, invalid in ((0,float('nan')),(2,float('inf')),(3,-.1),(3,1.1)):
            value = pattern((19,23)); value[-1,-1,channel] = invalid; before = value.tobytes()
            self.bad(lambda:self.apply(value,tile_pixels=7),'FLOAT_KEYER_VALUES')
            self.assertEqual(value.tobytes(),before)

    def test_budget_includes_retained_tables_and_minimum_conversion_tile(self):
        value = pattern((17,23)); before = value.tobytes()
        self.bad(lambda:self.apply(value,max_working_bytes=1024),'FLOAT_KEYER_BUDGET')
        self.bad(lambda:self.apply(value,retained_table_bytes=768*1024*1024),'FLOAT_KEYER_BUDGET')
        _, meta = self.apply(value,max_working_bytes=2*1024*1024)
        self.assertTrue(meta['workspace_admission']['adaptive_tile_reduction'])
        self.assertLessEqual(meta['estimated_working_bytes'],2*1024*1024)
        self.assertEqual(value.tobytes(),before)

    def test_cancel_at_entry_and_mid_spatial_pass_preserves_input(self):
        value = pattern((41,47)); before = value.tobytes()
        self.bad(lambda:self.apply(value,cancel=lambda:True),'RENDER_CANCELLED')
        count = [0]
        def cancel():
            count[0] += 1
            return count[0] >= 50
        self.bad(lambda:self.apply(value,effect(feather=4),cancel=cancel),'RENDER_CANCELLED')
        self.assertEqual(count[0],50); self.assertEqual(value.tobytes(),before)

    def test_gamma_encoded_key_uses_declared_signal_and_preserves_RGB_bits(self):
        value = np.clip(pattern(),0,1)
        srgb = ColorSignal('bt709','srgb')
        encoded, _ = convert_rgba(value,WORKING,srgb)
        expected = oracle(encoded,blend=.7)
        actual, _ = self.apply(value,effect(input_signal=vars(srgb),blend=.7))
        self.assertEqual(actual[...,:3].tobytes(),value[...,:3].tobytes())
        np.testing.assert_allclose(actual[...,3],expected[...,3],atol=1e-7,rtol=0)

    def test_key_and_exposure_order_changes_matte(self):
        compiler = EffectCompiler(resource_root=None,working_signal=WORKING)
        value = np.clip(pattern(),0,1); key = effect(similarity=.3,blend=.6)
        exposure = {'type':'exposure','parameters':{'stops':-1}}
        a, _ = compiler.apply(value,compiler.compile([key,exposure]),0)
        b, _ = compiler.apply(value,compiler.compile([exposure,key]),0)
        self.assertFalse(np.array_equal(a[...,3],b[...,3]))

    def test_two_keys_multiply_existing_coverage_in_order(self):
        compiler = EffectCompiler(resource_root=None,working_signal=WORKING)
        value = pattern(); a, b = effect(blend=.8),effect(color='blue',blend=.7)
        out, meta = compiler.apply(value,compiler.compile([a,b]),0)
        expected = oracle(oracle(value,blend=.8),key=(0,0,1),blend=.7)
        np.testing.assert_allclose(out,expected,atol=1e-7,rtol=0)
        self.assertEqual([r['type'] for r in meta['ordered_effects']],['chroma_key','chroma_key'])

    def compare_native_RGB(self, bits=8, blend=.55, scalar=False):
        maximum = (1 << bits)-1
        codes = np.random.default_rng(110).integers(0,maximum+1,(11,19,4),dtype=np.uint16)
        value = codes.astype(np.float32)/maximum
        out, _ = self.apply(value,effect(color='#20c060',similarity=.07,blend=blend,arithmetic='native_coefficients'))
        target = native(codes,f'colorkey=0x20c060:0.07:{blend}',bits=bits,scalar=scalar)
        expected = target[...,3].astype(np.float64)*codes[...,3]/maximum
        delta = float(np.max(np.abs(out[...,3].astype(np.float64)*maximum-expected)))
        # Native truncates its matte to the output integer axis once; incoming
        # coverage then weights that difference. This comparison does not
        # invent a second integer quantization in the continuous operator.
        limit = 1.08
        NATIVE_CALLS[-1].update(maximum_fractional_alpha_code_error=delta,predeclared_code_limit=limit,
                              incoming_alpha_composition='continuous-multiply-after-native-key',compared_pixels=209)
        self.assertLessEqual(delta,limit)
        self.assertEqual(out[...,:3].tobytes(),value[...,:3].tobytes())

    def test_native_RGBA8_soft_matte_and_original_alpha(self): self.compare_native_RGB()
    def test_native_RGBA16_soft_matte_and_original_alpha(self): self.compare_native_RGB(16)
    def test_native_RGBA8_hard_threshold(self): self.compare_native_RGB(blend=0)
    def test_native_RGBA16_hard_threshold(self): self.compare_native_RGB(16,blend=0)
    def test_native_RGBA16_scalar_CPU_soft_matte(self): self.compare_native_RGB(16,scalar=True)

    def compare_native_chroma(self,bits):
        maximum = (1 << bits)-1
        codes = np.random.default_rng(111).integers(maximum//4,3*maximum//4,(13,17,4),dtype=np.uint16)
        value = np.empty(codes.shape,np.float32)
        value[...,:3] = from_codes(codes[...,:3],matrix='bt709',range_value='full',bits=bits)
        value[...,3] = codes[...,3]/maximum
        e = effect(color=[.5,.5,.5],metric='chroma',matrix='bt709',range='full',
                   similarity=.03,blend=.25,arithmetic='native_coefficients')
        out, _ = self.apply(value,e)
        target = native(codes,'chromakey=0x008080:0.03:0.25:yuv=1',bits=bits,yuv=True)
        expected = target[...,3].astype(np.float64)*codes[...,3]/maximum
        # Native borders retain earlier scanline scratch. Only the 3x3
        # interior is its defined local neighbourhood for this comparison.
        delta = float(np.max(np.abs(out[1:-1,1:-1,3].astype(np.float64)*maximum-expected[1:-1,1:-1])))
        NATIVE_CALLS[-1].update(maximum_fractional_alpha_code_error=delta,predeclared_code_limit=1.1,
                               compared_pixels=11*15,boundary_excluded=True,key_UV='128*(1<<(bits-8))')
        self.assertLessEqual(delta,1.1)
        self.assertEqual(out[...,:3].tobytes(),value[...,:3].tobytes())

    def test_native_YUVA8_chroma_neighbourhood_interior(self): self.compare_native_chroma(8)
    def test_native_YUVA16_chroma_neighbourhood_interior(self): self.compare_native_chroma(16)

    def test_presentation_window_retains_original_key_author_ticks(self):
        value = np.clip(pattern((4,8)),0,1)
        p, sources = fixture.image_project(value,duration=200)
        e = effect(blend=.5); e['keyframes'] = [track('similarity',.01,.7,stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e])
        host = FloatTimeline(p,'main',sources,working_signal=WORKING)
        original = [host.render_frame(i)[0] for i in range(20)]
        selected = copy.deepcopy(p)
        selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,
            presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':200,'offset_tick':70})
        host = FloatTimeline(selected,'main',sources,working_signal=WORKING)
        for i in range(6):
            self.assertEqual(host.render_frame(i)[0].tobytes(),original[i+7].tobytes())

    def test_nested_reverse_and_parent_keep_their_own_key_clocks(self):
        value = np.clip(pattern((4,8)),0,1)
        p, sources = fixture.image_project(value,duration=200)
        child = copy.deepcopy(p['sequences'][0]); child['id'] = 'child'
        e = effect(blend=.5); e['keyframes'] = [track('similarity',.01,.6,'hold',stop=160)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e])
        parent = p['sequences'][0]['tracks'][0]['clips'][0]; parent.pop('asset_id')
        parent.update(sequence_id='child',duration_tick=200,source_out_tick=200,reverse=True,
                      effects=[effect(color='blue',blend=.8)])
        p['sequences'].append(child)
        out, _ = FloatTimeline(p,'main',sources,working_signal=WORKING).render_frame(4)
        expected, _ = self.apply(value,e,np.nextafter(160.,-np.inf))
        expected, _ = self.apply(expected,parent['effects'][0],40)
        np.testing.assert_allclose(out,expected,atol=2e-6,rtol=0)

    def test_native_validator_routes_keyer_channels_and_retains_legacy_contract(self):
        from ai_ad_editor.validator import validate_project
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.visual(); case.s['duration_tick'] = 18000
            e = effect(); e['keyframes'] = [track('feather',0,2,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e]
            result = validate_project(case.root,case.p); self.assertTrue(result['ok'],result)
            e['parameters'].pop('input_signal'); self.assertFalse(validate_project(case.root,case.p)['ok'])
            case.p['settings'].pop('pixel_pipeline')
            case.s['tracks'][0]['clips'][0]['effects'] = [{'type':'chroma_key','parameters':{'color':'0x00ff00'}}]
            self.assertTrue(validate_project(case.root,case.p)['ok'])
        finally:
            case.doCleanups()

    def test_actual_preview_matte_PCM_and_PNG16_match_independent_reference(self):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            pixels = case.visual(np.stack([np.clip(pattern((16,32)),0,1)]*2)); audio = case.audio()
            e = effect(similarity=.2,blend=.5,despill=.6)
            e['keyframes'] = [track('feather',0,2.5,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e]
            result = case.execute(end=2); actual = case.reference(result)
            source = np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535)
            expected = source.copy()
            for i, radius in enumerate((0,2.5)):
                graded = oracle(source[i],similarity=.2,blend=.5,despill=.6,feather=radius)
                expected[i,...,:3] = graded[...,:3]*graded[...,3:4]
            expected[...,3] = 1
            np.testing.assert_allclose(actual,expected,atol=2e-6,rtol=0)
            self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),
                                       np.rint(np.clip(actual[0].astype(np.float64),0,1)*65535),atol=1,rtol=0)
            case.assert_clean()
        finally:
            case.doCleanups()

    def test_actual_formal_transport_matches_float_preview(self):
        from ai_ad_editor.render import render_project
        from ai_ad_editor.project import project_write_lock
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            case.visual(np.stack([np.clip(pattern((16,32)),0,1)]*2)); case.audio()
            case.s['tracks'][0]['clips'][0]['effects'] = [effect(similarity=.2,blend=.5,feather=1.5,despill=.6)]
            actual = case.reference(case.execute(end=2))
            with project_write_lock(case.root):
                formal = render_project(case.root,case.p,case.s,case.root/'renders/keyer.mkv')
            manifest = json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload = np.moveaxis(np.rint(np.clip(actual[...,[1,2,0,3]].astype(np.float64),0,1)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],
                             'sha256:'+hashlib.sha256(payload).hexdigest())
            case.assert_clean()
        finally:
            case.doCleanups()

    def test_actual_preview_cache_hit_and_key_parameter_change(self):
        case = preview_fixture.FloatPreviewTests('runTest'); case.setUp()
        try:
            case.s['duration_tick'] = 18000
            case.visual(np.stack([np.clip(pattern((16,32)),0,1)]*2)); case.audio()
            e = effect(blend=.5); case.s['tracks'][0]['clips'][0]['effects'] = [e]
            one = case.execute(end=2); self.assertTrue(case.execute(end=2)['cache_hit'])
            e['parameters']['similarity'] = .25
            two = case.execute(end=2)
            self.assertNotEqual(one['cache_key'],two['cache_key']); self.assertFalse(two['cache_hit']); case.assert_clean()
        finally:
            case.doCleanups()

    def test_capability_limits_disabled_effect_and_remaining_temporal_reject(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        cap = build_capability_manifest()['capabilities']['timeline_native_float_keyer']
        self.assertIn('native_scanline_boundary_history_not_reproduced',cap['limits'])
        compiler = EffectCompiler(resource_root=None,working_signal=WORKING)
        self.assertEqual(compiler.compile([{'type':'chroma_key','enabled':False,'parameters':{'bad':True}}]),())
        self.bad(lambda:compiler.compile([{'type':'hqdn3d'}]),'FLOAT_TIMELINE_UNSUPPORTED')
