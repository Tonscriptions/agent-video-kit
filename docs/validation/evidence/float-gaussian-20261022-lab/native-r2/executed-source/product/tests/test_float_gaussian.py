"""Actual float FFmpeg references, independent dense systems and public paths."""
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
from ai_ad_editor.float_gaussian import compile_gaussian,apply_gaussian,state_at,validate_gaussian,ALIASES
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
from test_float_levels import track
import test_float_timeline as fixture
import test_float_preview as preview_fixture

LINEAR={'primaries':'bt709','transfer':'linear'}
SRGB={'primaries':'bt709','transfer':'srgb'}
WORKING=ColorSignal(**LINEAR)
NATIVE_CALLS=[]
NATIVE_ABSOLUTE_LIMIT=8e-5  # Declared before executing either implementation.


def effect(kind='blur',**parameters):
    return {'type':kind,'parameters':{'input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}


def pattern(shape=(11,17),seed=107):
    a=np.random.default_rng(seed).uniform(-.3,1.5,(*shape,4)).astype(np.float32)
    a[...,3]=np.random.default_rng(seed+1).uniform(.03,.97,shape).astype(np.float32)
    return a


def dense_axis(length,radius,steps):
    """Solve two boundary-value linear systems, then raise their operator to steps.

    This reference never executes the production forward/backward recurrence.
    The coefficient uses a different, rationalized algebraic expression.
    """
    if radius==0:return np.eye(length)
    variance=float(radius)**2/(2*steps)
    q=4*variance/(math.sqrt(1+4*variance)+1)**2
    lower=np.eye(length)-np.diag(np.full(max(0,length-1),q),-1)
    upper=np.eye(length)-np.diag(np.full(max(0,length-1),q),1)
    left=np.full(length,1-q);left[0]=1
    right=np.full(length,1-q);right[-1]=1
    stage=np.linalg.solve(upper,np.diag(right))@np.linalg.solve(lower,np.diag(left))
    return np.linalg.matrix_power(stage,steps)


def dense(value,rx,ry=None,steps=1,planes=15,premultiplied=False):
    ry=rx if ry is None else ry
    x=dense_axis(value.shape[1],rx,steps);y=dense_axis(value.shape[0],ry,steps)
    data=value.astype(np.float64).copy()
    if premultiplied:data[...,:3]*=data[...,3:4]
    blurred=np.einsum('ij,jkc,lk->ilc',y,data,x,optimize=True)
    if premultiplied:
        positive=blurred[...,3]>0
        np.divide(blurred[...,:3],blurred[...,3:4],out=blurred[...,:3],where=positive[...,None])
        blurred[...,:3][~positive]=0
    out=value.astype(np.float64).copy()
    for channel,bit in enumerate((4,1,2,8)):
        if planes&bit:out[...,channel]=blurred[...,channel]
    return out


def native(value,rx,ry=None,steps=1,planes=15,cpu_reference=False):
    ry=rx if ry is None else ry;h,w=value.shape[:2]
    kernel=f'gblur=sigma={rx}:sigmaV={ry}:steps={steps}:planes={planes}'
    payload=np.moveaxis(value[...,[1,2,0,3]],2,0).astype('<f4').tobytes()
    args=[ffmpeg_path(),'-nostdin','-v','error']
    if cpu_reference:args+=['-cpuflags','0']
    args+=['-filter_threads','1','-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{w}x{h}',
        '-i','pipe:0','-vf',kernel,'-frames:v','1','-threads','1','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1']
    result=subprocess.run(args,input=payload,capture_output=True,check=True)
    assert len(result.stdout)==value.nbytes
    NATIVE_CALLS.append({'kernel':kernel,'cpu_reference':cpu_reference,'width':w,'height':h,
        'pixel_format':'gbrapf32le','exit_code':result.returncode,
        'input_sha256':hashlib.sha256(payload).hexdigest(),'output_sha256':hashlib.sha256(result.stdout).hexdigest()})
    return np.moveaxis(np.frombuffer(result.stdout,'<f4').reshape(4,h,w)[[2,0,1,3]],0,2).copy()


class FloatGaussianTests(unittest.TestCase):
    def apply(self,value,e=None,tick=0,**kwargs):
        return apply_gaussian(value,compile_gaussian(e or effect()),tick,working_signal=WORKING,**kwargs)

    def bad(self,fn,code=None):
        with self.assertRaises(AppError) as caught:fn()
        if code:self.assertEqual(caught.exception.code,code)

    def compare_native(self,rx,ry=None,steps=1,planes=15,shape=(19,43),cpu=False):
        value=pattern(shape);ry=rx if ry is None else ry
        out,_=self.apply(value,effect(radius_x=rx,radius_y=ry,steps=steps,planes=planes))
        expected=native(value,rx,ry,steps,planes,cpu)
        maximum=float(np.max(np.abs(out.astype(np.float64)-expected)))
        NATIVE_CALLS[-1].update(maximum_absolute_error=maximum,predeclared_absolute_limit=NATIVE_ABSOLUTE_LIMIT)
        self.assertTrue(np.isfinite(expected).all());self.assertLessEqual(maximum,NATIVE_ABSOLUTE_LIMIT)

    def test_alias_defaults_and_zero_radius_preserve_signed_zero_and_headroom(self):
        value=pattern();value[0,0]=[-0.,-.2,1.4,-0.]
        for name in ALIASES:
            plan=compile_gaussian(effect(name));self.assertEqual(state_at(plan,0)['radius_x'],4)
            out,m=self.apply(value,effect(name,radius=0));self.assertEqual(value.tobytes(),out.tobytes())
            self.assertFalse(m['integer_intermediate']);self.assertFalse(m['native_bit_equivalence'])

    def test_native_linked_radius_including_legacy_default(self):
        for radius in (.1,.7,2.,4.,7.):self.compare_native(radius)

    def test_native_aligned_surfaces_all_six_step_counts(self):
        for steps in range(1,7):self.compare_native(2.,steps=steps,shape=(16,48))

    def test_native_odd_anisotropic_surfaces(self):
        for steps in (1,3,6):self.compare_native(.7,3.,steps=steps)

    def test_native_horizontal_only_zero_vertical_radius(self):
        for steps in (1,6):self.compare_native(2.,0.,steps=steps)

    def test_native_vertical_only_zero_horizontal_radius(self):
        for steps in (1,6):self.compare_native(0.,2.,steps=steps)

    def test_native_all_GBRA_plane_bit_combinations(self):
        for planes in range(16):self.compare_native(.7,1.3,planes=planes,shape=(9,23))

    def test_native_pure_C_and_default_CPU_paths(self):
        for cpu in (False,True):self.compare_native(3.,.8,steps=3,cpu=cpu)

    def test_independent_dense_systems_for_steps_and_axis_orders(self):
        value=pattern((7,9))
        for rx,ry,steps in ((.1,.7,1),(.7,3.,2),(2.,.2,6),(0.,1.4,3),(1.7,0.,4)):
            out,_=self.apply(value,effect(radius_x=rx,radius_y=ry,steps=steps))
            np.testing.assert_allclose(out,dense(value,rx,ry,steps),atol=2e-7,rtol=0)

    def test_maximum_radius_and_steps_keep_constant_DC_and_signed_headroom(self):
        value=fixture.rgba((-.3,.4,1.7,.37),shape=(17,29))
        out,_=self.apply(value,effect(radius=128,steps=6))
        self.assertEqual(out.tobytes(),value.tobytes());self.assertTrue(np.isfinite(out).all())

    def test_singleton_axes_match_dense_reference(self):
        for shape in ((1,1),(1,13),(11,1)):
            value=pattern(shape);out,_=self.apply(value,effect(radius_x=7,radius_y=2,steps=6))
            np.testing.assert_allclose(out,dense(value,7,2,6),atol=2e-7,rtol=0)

    def test_impulse_and_endpoint_extension_match_boundary_value_reference(self):
        value=np.zeros((5,13,4),np.float32);value[...,3]=1;value[0,0,0]=1;value[-1,-1,1]=1
        out,_=self.apply(value,effect(radius_x=2,radius_y=.7,steps=3))
        np.testing.assert_allclose(out,dense(value,2,.7,3),atol=3e-8,rtol=0)
        self.assertGreater(out[0,0,0],out[0,1,0]);self.assertGreater(out[0,1,0],0)

    def test_near_zero_radius_keeps_nonzero_fractional_spread(self):
        value=np.zeros((1,7,4),np.float32);value[...,3]=1;value[0,3,0]=1
        out,_=self.apply(value,effect(radius_x=1e-5,radius_y=0))
        self.assertGreater(out[0,2,0],0);np.testing.assert_allclose(out,dense(value,1e-5,0),atol=1e-17,rtol=2e-7)

    def test_float_ramp_is_not_posterized_to_integer_raster(self):
        value=np.ones((14,10000,4),np.float32)
        value[...,:3]=np.linspace(0,1,140000,dtype=np.float32).reshape(14,10000,1)
        value[...,3]=.5;out,_=self.apply(value,effect(radius_x=.2,radius_y=0))
        self.assertGreater(len(np.unique(out[...,0])),130000)

    def test_RGB_plane_selection_preserves_all_original_alpha_bits(self):
        value=pattern();value[0,0,3]=-0.;value[0,1,3]=np.nextafter(np.float32(0),np.float32(1))
        out,m=self.apply(value,effect(planes=7));self.assertEqual(out[...,3].tobytes(),value[...,3].tobytes())
        self.assertEqual(m['selected_RGBA_indices'],[0,1,2]);self.assertEqual(m['alpha'],'input-bits-preserved')

    def test_alpha_only_blur_preserves_RGB_bits_and_bypasses_signal_roundtrip(self):
        value=pattern();value[0,0,:3]=[-0.,-.3,1.7]
        out,m=self.apply(value,effect(planes=8,input_signal=SRGB,output_signal=SRGB))
        self.assertEqual(out[...,:3].tobytes(),value[...,:3].tobytes());self.assertTrue(m['alpha_only_RGB_conversion_bypassed'])
        np.testing.assert_allclose(out[...,3],dense(value,4)[...,3],atol=6e-8,rtol=0)

    def test_premultiplied_mode_removes_hidden_RGB_transparent_halo(self):
        value=np.zeros((3,17,4),np.float32);value[...,:3]=[1,0,0];value[:,8:]=[.4,.4,.4,1]
        straight,_=self.apply(value,effect(radius=2));out,m=self.apply(value,effect(radius=2,alpha_mode='premultiplied'))
        np.testing.assert_allclose(out,dense(value,2,premultiplied=True),atol=8e-8,rtol=0)
        np.testing.assert_allclose(out[...,:3],.4,atol=4e-8,rtol=0)
        self.assertGreater(straight[1,7,0]-straight[1,7,1],.1);self.assertEqual(m['alpha'],'explicit-Gaussian-coverage-mapping')

    def test_all_zero_coverage_has_explicit_zero_hidden_RGB(self):
        value=pattern();value[...,3]=0;out,m=self.apply(value,effect(alpha_mode='premultiplied'))
        self.assertTrue(np.all(out==0));self.assertEqual(m['zero_blurred_coverage_pixels'],value.shape[0]*value.shape[1])

    def test_tiny_positive_coverage_uses_no_arbitrary_epsilon_floor(self):
        value=fixture.rgba((.2,.5,.9,1e-30),shape=(7,13));out,_=self.apply(value,effect(alpha_mode='premultiplied',radius=128,steps=6))
        np.testing.assert_array_equal(out,value)

    def test_premultiplied_mode_matches_native_blurred_density_and_colour(self):
        value=pattern((13,23));payload=value.copy();payload[...,:3]*=payload[...,3:4]
        reference=native(payload,2.,.7,steps=3);reference[...,:3]/=reference[...,3:4]
        out,_=self.apply(value,effect(radius_x=2,radius_y=.7,steps=3,alpha_mode='premultiplied'))
        maximum=float(np.max(np.abs(out.astype(np.float64)-reference)))
        NATIVE_CALLS[-1].update(maximum_absolute_error=maximum,predeclared_absolute_limit=NATIVE_ABSOLUTE_LIMIT,premultiplied_density=True)
        self.assertLessEqual(maximum,NATIVE_ABSOLUTE_LIMIT)

    def test_intensity_mixes_linear_RGB_and_coverage_independently(self):
        value=pattern();e=effect(radius_x=2,radius_y=.7,alpha_mode='premultiplied',intensity=.37)
        out,m=self.apply(value,e);expected=value.astype(np.float64)*.63+dense(value,2,.7,premultiplied=True).astype(np.float32).astype(np.float64)*.37
        np.testing.assert_allclose(out,expected,atol=2e-7,rtol=0);self.assertEqual(m['alpha_mix'],'linear-coverage')

    def test_output_RGB_clip_is_explicit_and_separate_from_coverage(self):
        value=fixture.rgba((-.2,.3,1.7,.4));preserved,_=self.apply(value);out,m=self.apply(value,effect(output_gamut='clip'))
        np.testing.assert_array_equal(preserved,value);np.testing.assert_array_equal(out[...,:3],np.clip(value[...,:3],0,1))
        self.assertEqual(m['output_clipped_components'],value.shape[0]*value.shape[1]*2)

    def test_srgb_blur_and_intensity_use_declared_signal_then_linear_mix(self):
        value=pattern();value[...,:3]=np.clip(value[...,:3],0,1)
        encoded=np.where(value[...,:3]<=.0031308,value[...,:3]*12.92,1.055*value[...,:3].astype(np.float64)**(1/2.4)-.055).astype(np.float32)
        data=value.copy();data[...,:3]=encoded;blurred=dense(data,1.3).astype(np.float32)
        rgb=blurred[...,:3].astype(np.float64);decoded=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4).astype(np.float32)
        out,_=self.apply(value,effect(radius=1.3,input_signal=SRGB,output_signal=SRGB,intensity=.4))
        np.testing.assert_allclose(out[...,:3],value[...,:3].astype(np.float64)*.6+decoded.astype(np.float64)*.4,atol=1.5e-7,rtol=0)

    def test_distinct_input_and_output_signals_are_interpreted_explicitly(self):
        value=pattern();value[...,:3]=np.clip(value[...,:3],0,1);data=dense(value,1.3).astype(np.float32)
        expected=np.where(data[...,:3]<=.04045,data[...,:3]/12.92,((data[...,:3].astype(np.float64)+.055)/1.055)**2.4)
        out,_=self.apply(value,effect(radius=1.3,output_signal=SRGB));np.testing.assert_allclose(out[...,:3],expected,atol=1.5e-7,rtol=0)

    def test_zero_intensity_and_plane_zero_keep_identity_after_full_validation(self):
        value=pattern();value[0,0,0]=-0.
        for options in ({'intensity':0,'output_gamut':'clip'},{'planes':0}):
            out,_=self.apply(value,effect(**options));self.assertEqual(out.tobytes(),value.tobytes())
        value[-1,-1,3]=np.nan;self.bad(lambda:self.apply(value,effect(intensity=0)))

    def test_master_radius_animation_remains_linked_to_both_axes(self):
        e=effect();e['keyframes']=[track('sigma',0,8)];p=compile_gaussian(e)
        self.assertEqual(state_at(p,25),{'radius':2.,'radius_x':2.,'radius_y':2.,'intensity':1.})

    def test_static_and_animated_axis_overrides_are_independent(self):
        e=effect(radius_y=0);e['keyframes']=[track('blur.radius',0,8),track('sigma_x',1,3)]
        p=compile_gaussian(e);self.assertEqual(p.axis_overrides,('radius_x','radius_y'))
        self.assertEqual(state_at(p,50),{'radius':4.,'radius_x':2.,'radius_y':0.,'intensity':1.})

    def test_all_six_easings_and_Bezier_overshoot_are_bounded(self):
        values={'linear':.25,'hold':0,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.25}
        for mode,want in values.items():
            e=effect();e['keyframes']=[track('intensity',0,1,mode,controls=[1/3,2/3] if mode=='bezier' else None)]
            self.assertAlmostEqual(state_at(compile_gaussian(e),25)['intensity'],want)
        e=effect();e['keyframes']=[track('radius',0,128,'bezier',controls=[10,10])]
        self.assertEqual(state_at(compile_gaussian(e),50)['radius_x'],128)

    def test_large_rational_clock_and_hold_left_edge_are_precise(self):
        n=10**20;e=effect();e['keyframes']=[track('radius',0,100,start=n,stop=n+100)];p=compile_gaussian(e)
        self.assertEqual(state_at(p,Fraction(n*2+1,2))['radius_y'],.5)
        e['keyframes'][0]['keyframes'][0]['interpolation']='hold';p=compile_gaussian(e)
        self.assertEqual(state_at(p,Fraction(n+100)-Fraction(1,1000))['radius_x'],0)
        self.assertEqual(state_at(p,n+100)['radius_x'],100)

    def test_four_control_Bezier_uses_author_time_root(self):
        e=effect();e['keyframes']=[track('radius_y',0,100,'bezier',controls=[.25,0,.75,1])]
        self.assertAlmostEqual(state_at(compile_gaussian(e),50)['radius_y'],50,places=8)

    def test_compiled_plan_does_not_retain_mutable_author_data(self):
        e=effect();e['keyframes']=[track('radius',0,8)];p=compile_gaussian(e)
        e['parameters']['radius']=128;e['parameters']['input_signal']['transfer']='bad';e['keyframes'][0]['keyframes'][1]['value']=128
        self.assertEqual(state_at(p,25)['radius_x'],2.)

    def test_duplicate_aliases_and_keyframe_locations_reject(self):
        self.bad(lambda:compile_gaussian(effect(radius=1,sigma=1)))
        self.bad(lambda:compile_gaussian(effect(radius_y=1,sigmaV=1)))
        for rows in ([track('radius',0,1),track('sigma',0,1)],[track('steps',1,6)]):
            e=effect();e['keyframes']=rows;self.bad(lambda e=e:compile_gaussian(e))
        e=effect(keyframes=[]);e['keyframes']=[];self.bad(lambda:compile_gaussian(e))

    def test_invalid_signals_modes_fields_and_parameters_reject(self):
        for p in ({'steps':0},{'steps':7},{'steps':True},{'planes':-1},{'planes':16},{'planes':1.},
                  {'alpha_mode':'auto'},{'alpha_mode':'premultiplied','planes':7},{'output_gamut':'auto'},
                  {'radius':float('nan')},{'radius':129},{'radius':True},{'intensity':-1},{'unknown':0},
                  {'input_signal':None},{'output_signal':LINEAR|{'guess':True}}):
            self.bad(lambda p=p:compile_gaussian(effect(**p)))
        self.bad(lambda:compile_gaussian(effect()|{'radius':1}));self.bad(lambda:compile_gaussian(effect()|{'enabled':1}))

    def test_keyframe_budget_duration_and_disabled_validation(self):
        e=effect();e['keyframes']=[{'property':'radius','keyframes':[{'at_tick':i,'value':0} for i in range(1025)]}]
        self.bad(lambda:compile_gaussian(e));e=effect();e['keyframes']=[track('radius',0,8)]
        self.assertEqual(validate_gaussian(e,duration_tick=100),[]);self.assertTrue(validate_gaussian(e,duration_tick=99))
        self.assertEqual(validate_gaussian({'type':'blur','enabled':False,'parameters':{'bad':0}}),[])

    def test_forged_plans_and_invalid_clocks_reject(self):
        p=compile_gaussian(effect())
        for forged in (replace(p,values=p.values[:-1]),replace(p,steps=True),replace(p,axis_overrides=('radius_y','radius_x')),
                       replace(p,tracks_json=' []'),replace(p,input_signal=None)):
            self.bad(lambda forged=forged:state_at(forged,0))
        for tick in (True,-1,float('nan'),'0'):self.bad(lambda tick=tick:state_at(p,tick))

    def test_surface_layout_late_alpha_and_finite_values_are_transactional(self):
        value=pattern();value[-1,-1,3]=1.1;before=value.tobytes();self.bad(lambda:self.apply(value,tile_pixels=1));self.assertEqual(value.tobytes(),before)
        for bad in (value.astype(np.float64),value[:,::2],np.zeros((2,3,3),np.float32)):
            self.bad(lambda bad=bad:self.apply(bad))
        value[-1,-1,3]=.5;value[-1,-1,0]=np.inf;self.bad(lambda:self.apply(value))

    def test_readonly_inputs_and_all_tile_sizes_produce_identical_pixels(self):
        value=pattern();value.flags.writeable=False;e=effect(radius_x=2,radius_y=.7,steps=3,alpha_mode='premultiplied')
        expected,_=self.apply(value,e,tile_pixels=1)
        for tile in (7,16384,262144):
            out,_=self.apply(value,e,tile_pixels=tile);self.assertEqual(expected.tobytes(),out.tobytes())

    def test_surface_and_retained_table_budgets_are_admitted_before_allocation(self):
        value=pattern();before=value.tobytes()
        for options in ({'max_working_bytes':1},{'retained_table_bytes':768*1024*1024},{'tile_pixels':0},{'tile_pixels':True},
                        {'retained_table_bytes':-1},{'max_working_bytes':True}):
            self.bad(lambda options=options:self.apply(value,**options));self.assertEqual(value.tobytes(),before)
        self.bad(lambda:self.apply(np.zeros((1,16385,4),np.float32)))

    def test_mid_sweep_cancel_and_callback_exception_preserve_caller(self):
        value=pattern((65,71));before=value.tobytes();count=[0]
        def cancel():count[0]+=1;return count[0]>12
        self.bad(lambda:self.apply(value,cancel=cancel),'RENDER_CANCELLED');self.assertEqual(value.tobytes(),before)
        def crash():raise RuntimeError('callback failed')
        with self.assertRaises(RuntimeError):self.apply(value,cancel=crash)
        self.assertEqual(value.tobytes(),before)

    def test_signal_overflow_rejects_without_partial_caller_mutation(self):
        value=fixture.rgba((3e38,3e38,3e38,.5));before=value.tobytes()
        self.bad(lambda:self.apply(value,effect(output_signal=SRGB)));self.assertEqual(before,value.tobytes())
        self.bad(lambda:apply_gaussian(value,compile_gaussian(effect()),0,working_signal=ColorSignal(**SRGB)))

    def test_ordered_tone_exposure_and_gaussian_are_not_reordered(self):
        from test_float_tone import effect as tone
        compiler=EffectCompiler(resource_root=None,working_signal=WORKING);value=pattern()
        rows=[tone('gamma',gamma=1.3),effect(radius=.7,alpha_mode='premultiplied'),{'type':'exposure','parameters':{'amount':.3}},tone('hue',degrees=20)]
        actual,m=compiler.apply(value,compiler.compile(rows),50);expected=value
        for row in rows:expected,_=compiler.apply(expected,compiler.compile([row]),50)
        self.assertEqual(actual.tobytes(),expected.tobytes());self.assertEqual(m['alpha'],'explicit-per-effect-alpha-mapping')
        reverse,_=compiler.apply(value,compiler.compile(list(reversed(rows))),50);self.assertFalse(np.array_equal(actual,reverse))

    def test_presentation_window_preserves_original_radius_author_clock(self):
        value=pattern((4,8));p,s=fixture.image_project(value,duration=200);e=effect();e['keyframes']=[track('radius',0,6,stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);host=FloatTimeline(p,'main',s,working_signal=WORKING)
        full=[host.render_frame(i)[0] for i in range(20)];selected=copy.deepcopy(p)
        selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':200,'offset_tick':70})
        host=FloatTimeline(selected,'main',s,working_signal=WORKING)
        for i in range(6):self.assertEqual(host.render_frame(i)[0].tobytes(),full[i+7].tobytes())

    def test_nested_reverse_keeps_child_and_parent_effect_author_clocks(self):
        value=pattern((4,8));p,s=fixture.image_project(value,duration=200);child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        e=effect();e['keyframes']=[track('radius',0,6,'hold',stop=160)];child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e])
        parent=p['sequences'][0]['tracks'][0]['clips'][0];parent.pop('asset_id');parent.update(sequence_id='child',duration_tick=200,source_out_tick=200,reverse=True,effects=[effect(radius_x=.3,radius_y=0)])
        p['sequences'].append(child);out,_=FloatTimeline(p,'main',s,working_signal=WORKING).render_frame(4)
        expected,_=self.apply(value,e,tick=np.nextafter(160.,-np.inf));expected,_=self.apply(expected,parent['effects'][0],tick=40)
        np.testing.assert_allclose(out,expected,atol=3e-7,rtol=0)

    def test_validator_routes_native_gaussian_and_preserves_legacy_engine(self):
        from ai_ad_editor.validator import validate_project
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick']=18000
            e=effect();e['keyframes']=[track('radius',0,6,stop=9000)];case.s['tracks'][0]['clips'][0]['effects']=[e]
            result=validate_project(case.root,case.p);self.assertTrue(result['ok'],result)
            e['parameters'].pop('input_signal');self.assertFalse(validate_project(case.root,case.p)['ok'])
            case.p['settings'].pop('pixel_pipeline');case.s['tracks'][0]['clips'][0]['effects']=[{'type':'blur','parameters':{'radius':3}}]
            self.assertTrue(validate_project(case.root,case.p)['ok'])
        finally:case.doCleanups()

    def test_real_preview_PCM_and_PNG16_share_independent_blurred_alpha_pixels(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;value=pattern((16,32));value[...,:3]=np.clip(value[...,:3],0,1)
            pixels=case.visual(np.stack((value,value)));audio=case.audio()
            e=effect(radius_x=2,radius_y=.7,steps=3,alpha_mode='premultiplied');case.s['tracks'][0]['clips'][0]['effects']=[e]
            result=case.execute(end=2);actual=case.reference(result);source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535)
            expected=np.stack([dense(v,2,.7,3,premultiplied=True).astype(np.float32) for v in source]);expected[...,:3]*=expected[...,3:4];expected[...,3]=1
            np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=0);self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),np.rint(actual[0].astype(np.float64)*65535),atol=1,rtol=0);case.assert_clean()
        finally:case.doCleanups()

    def test_real_formal_render_and_preview_share_blur_transport(self):
        from ai_ad_editor.render import render_project
        from ai_ad_editor.project import project_write_lock
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;value=np.clip(pattern((16,32)),0,1);case.visual(np.stack((value,value)));case.audio()
            case.s['tracks'][0]['clips'][0]['effects']=[effect(radius_x=2,radius_y=.7,alpha_mode='premultiplied')];actual=case.reference(case.execute(end=2))
            with project_write_lock(case.root):formal=render_project(case.root,case.p,case.s,case.root/'renders/gaussian.mkv')
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload=np.moveaxis(np.rint(actual[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest());case.assert_clean()
        finally:case.doCleanups()

    def test_real_cache_hit_and_radius_or_alpha_mode_changes_invalidate(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;value=np.clip(pattern((16,32)),0,1);case.visual(np.stack((value,value)));case.audio();e=effect(radius=1)
            case.s['tracks'][0]['clips'][0]['effects']=[e];one=case.execute(end=2);self.assertTrue(case.execute(end=2)['cache_hit'])
            e['parameters']['radius']=2;two=case.execute(end=2);self.assertNotEqual(one['cache_key'],two['cache_key'])
            e['parameters']['alpha_mode']='premultiplied';three=case.execute(end=2);self.assertNotEqual(two['cache_key'],three['cache_key']);self.assertFalse(three['cache_hit']);case.assert_clean()
        finally:case.doCleanups()

    def test_capabilities_and_disabled_effects_report_actual_limits(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        row=build_capability_manifest()['capabilities']['timeline_native_float_gaussian']
        self.assertIn('normalized_binary64_recursion_is_not_bit_exact_native_float32',row['limits'])
        self.assertEqual(EffectCompiler(resource_root=None,working_signal=WORKING).compile([{'type':'blur','enabled':False,'parameters':{'bad':True}}]),())
