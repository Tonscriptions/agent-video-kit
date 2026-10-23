"""Real legacy backends, independent colorsys oracle and public rendering paths."""
import bisect
import colorsys
import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_selective_hsl import compile_hsl,apply_hsl,state_at,validate_hsl,ALIASES,BOUNDS
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
from test_float_levels import track
from test_float_lut import write_cube
import test_float_timeline as fixture
import test_float_preview as preview_fixture

LINEAR={'primaries':'bt709','transfer':'linear'}
WORKING=ColorSignal(**LINEAR)
NATIVE_CALLS=[]
CENTERS=(0,30,60,120,180,240,270,300)
NAMES=('red','orange','yellow','green','cyan','blue','purple','magenta')


def effect(**parameters):
    return {'type':'selective_hsl','parameters':{'input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}


def scalar(rgb,p):
    """Scalar stdlib HLS and neighboring knots, not product vector equations."""
    original=list(map(float,rgb));base=[min(1.,max(0.,v)) for v in original]
    h,l,s=colorsys.rgb_to_hls(*base)
    if s:
        degrees=h*360;i=bisect.bisect_right(CENTERS,degrees)-1;j=(i+1)%8
        right=CENTERS[j] if j else 360
        u=(degrees-CENTERS[i])/(right-CENTERS[i])
        shifts=[(1-u)*p.get(NAMES[i]+'_'+a,0)+u*p.get(NAMES[j]+'_'+a,0) for a in ('hue','saturation','lightness')]
        h=(h+shifts[0]/360)%1
        s=s+(1-s)*shifts[1] if shifts[1]>=0 else s*(1+shifts[1])
        l=l+(1-l)*shifts[2] if shifts[2]>=0 else l*(1+shifts[2])
        result=list(colorsys.hls_to_rgb(h,min(1,max(0,l)),min(1,max(0,s))))
    else:result=base
    if p.get('input_gamut')=='preserve_residual':result=[v+o-b for v,o,b in zip(result,original,base)]
    if p.get('output_gamut')=='clip':result=[min(1.,max(0.,v)) for v in result]
    return result


def native(q,p,backend='expression'):
    from ai_ad_editor.selective_hsl import compile_filter
    from ai_ad_editor.hsl_native import compile_native
    declaration={'type':'selective_hsl','parameters':p}
    expression=lambda aliases,default:str(default)
    kernel,metadata=compile_filter(declaration,expression)
    if backend=='native':
        with patch.dict('os.environ',{'AI_AD_EDITOR_HSL_BACKEND':'native'}):
            kernel,metadata=compile_native(declaration,expression,kernel,metadata)
        assert metadata['backend']=='ffmpeg:frei0r'
    h,w=q.shape[:2];payload=q.tobytes()
    args=[ffmpeg_path(),'-nostdin','-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
        '-video_size',f'{w}x{h}','-i','pipe:0','-vf',kernel,'-frames:v','1','-threads','1','-pix_fmt','rgba','-f','rawvideo','pipe:1']
    result=subprocess.run(args,input=payload,capture_output=True,check=True)
    NATIVE_CALLS.append({'backend':backend,'parameters':p,'pixels':h*w,'exit_code':result.returncode,
        'input_sha256':hashlib.sha256(payload).hexdigest(),'output_sha256':hashlib.sha256(result.stdout).hexdigest()})
    return np.frombuffer(result.stdout,np.uint8).reshape(h,w,4).copy()


class FloatSelectiveHSLTests(unittest.TestCase):
    def apply(self,value,e=None,tick=0,**kwargs):
        return apply_hsl(value,compile_hsl(e or effect()),tick,working_signal=WORKING,**kwargs)

    def bad(self,fn,code=None):
        with self.assertRaises(AppError) as caught:fn()
        if code:self.assertEqual(caught.exception.code,code)

    def test_zero_controls_are_byte_identity_with_signed_zero_and_alpha(self):
        a=np.random.default_rng(105).uniform(0,1,(13,29,4)).astype(np.float32)
        a[0,0]=[-0.,0.,0.,-0.];a[0,1,3]=np.nextafter(np.float32(0),np.float32(1))
        out,m=self.apply(a);self.assertEqual(out.tobytes(),a.tobytes());self.assertFalse(m['integer_intermediate'])

    def test_all_existing_selective_aliases_compile(self):
        for name in ALIASES:
            e=effect(red_hue=30);e['type']=name;e['keyframes']=[track(name+'.red_hue',0,30)]
            self.assertEqual(state_at(compile_hsl(e),50)['red_hue'],15)

    def test_explicit_signals_are_required(self):
        for p in ({},{'input_signal':LINEAR},{'input_signal':LINEAR,'output_signal':{'primaries':'bt709','transfer':'bt709'}}):
            self.bad(lambda:compile_hsl({'type':'selective_hsl','parameters':p}))

    def test_each_of_24_controls_matches_real_geq_eight_bit_kernel(self):
        q=np.random.default_rng(106).integers(0,256,(13,29,4),dtype=np.uint8)
        for band in NAMES:
            for axis,value in (('hue',37),('saturation',-.37),('lightness',.23)):
                p={band+'_'+axis:value};out,_=self.apply(q.astype(np.float32)/255,effect(**p))
                expected=native(q,p);actual=np.rint(out.astype(np.float64)*255).astype(np.int32)
                difference=int(np.abs(actual-expected.astype(np.int32)).max())
                NATIVE_CALLS[-1]['maximum_8bit_code_error']=difference
                self.assertLessEqual(difference,1);np.testing.assert_array_equal(actual[...,3],q[...,3])

    def test_mixed_bands_match_real_bundled_native_plugin(self):
        q=np.random.default_rng(107).integers(0,256,(17,43,4),dtype=np.uint8)
        p={'red_hue':31,'orange_saturation':.3,'yellow_lightness':-.2,'green_hue':-27,
           'cyan_saturation':-.4,'blue_lightness':.25,'purple_hue':41,'magenta_saturation':.2}
        out,_=self.apply(q.astype(np.float32)/255,effect(**p));expected=native(q,p,'native')
        diff=int(np.abs(np.rint(out.astype(np.float64)*255).astype(np.int32)-expected.astype(np.int32)).max())
        NATIVE_CALLS[-1]['maximum_8bit_code_error']=diff;self.assertLessEqual(diff,1)

    def test_random_continuous_values_match_independent_colorsys(self):
        a=np.random.default_rng(108).uniform(0,1,(17,43,4)).astype(np.float32)
        p={band+'_'+axis:(i-3)*scale for i,band in enumerate(NAMES) for axis,scale in (('hue',11),('saturation',.07),('lightness',-.04))}
        out,_=self.apply(a,effect(**p));expected=np.array([scalar(v,p) for v in a[...,:3].reshape(-1,3)]).reshape(17,43,3)
        np.testing.assert_allclose(out[...,:3],expected,atol=8e-8,rtol=0)

    def test_unequal_orange_and_purple_sectors_and_red_wrap(self):
        degrees=(0,15,30,45,60,90,120,180,240,255,270,285,300,330,359.9)
        a=np.array([[(*colorsys.hls_to_rgb(h/360,.4,.7),.63) for h in degrees]],np.float32)
        p={'red_hue':70,'orange_hue':-20,'yellow_saturation':-.4,'purple_lightness':.35,'magenta_hue':-40}
        out,_=self.apply(a,effect(**p))
        np.testing.assert_allclose(out[0,:,:3],[scalar(v,p) for v in a[0,:,:3]],atol=8e-8,rtol=0)

    def test_all_band_weights_use_original_hue_simultaneously(self):
        a=fixture.rgba((*colorsys.hls_to_rgb(20/360,.4,.7),.6))
        p={'red_hue':150,'orange_hue':-70,'yellow_saturation':-1,'blue_lightness':.8}
        out,_=self.apply(a,effect(**p));np.testing.assert_allclose(out[0,0,:3],scalar(a[0,0,:3],p),atol=8e-8,rtol=0)

    def test_achromatic_RGB_and_alpha_remain_bit_exact(self):
        a=np.ones((1,9,4),np.float32);a[0,:,:3]=np.linspace(0,1,9,dtype=np.float32)[:,None];a[...,3]=.2
        p={n:(120 if n.endswith('hue') else .7) for n in BOUNDS if n!='intensity'}
        out,_=self.apply(a,effect(**p,input_signal={'primaries':'bt709','transfer':'srgb'},output_signal={'primaries':'bt709','transfer':'srgb'}))
        self.assertEqual(out.tobytes(),a.tobytes())

    def test_negative_and_positive_saturation_lightness_sliders(self):
        a=fixture.rgba((.6,.2,.1,.4))
        for axis in ('saturation','lightness'):
            for value in (-1,-.3,.3,1):
                p={band+'_'+axis:value for band in NAMES};out,_=self.apply(a,effect(**p))
                np.testing.assert_allclose(out[0,0,:3],scalar(a[0,0,:3],p),atol=8e-8,rtol=0)

    def test_131073_distinct_values_survive_without_integer_grid(self):
        a=np.ones((257*512,4),np.float32);a[:131073,0]=np.linspace(.2,.8,131073,dtype=np.float32);a[:,:3][:,1:]=[.1,.05]
        p={band+'_hue':15 for band in NAMES};out,_=self.apply(a.reshape(257,512,4),effect(**p))
        self.assertGreater(len(np.unique(out.reshape(-1,4)[:131073,0])),65536)

    def test_near_black_chroma_is_not_erased_by_an_epsilon_floor(self):
        a=fixture.rgba((1e-30,4e-31,2e-31,.3));p={band+'_hue':120 for band in NAMES}
        out,_=self.apply(a,effect(**p));np.testing.assert_allclose(out[0,0,:3],scalar(a[0,0,:3],p),atol=1e-37,rtol=2e-7)
        self.assertGreater(float(out[0,0,1]),float(out[0,0,0]))

    def test_default_input_gamut_rejects_headroom_without_mutation(self):
        for colour in ((-.1,.2,.4,.5),(.2,.4,1.2,.5)):
            a=fixture.rgba(colour);old=a.tobytes()
            self.bad(lambda:self.apply(a,effect(red_hue=20)),'FLOAT_SELECTIVE_HSL_INPUT_GAMUT');self.assertEqual(a.tobytes(),old)

    def test_explicit_input_clip_reports_actual_component_loss(self):
        a=np.array([[[-.2,.3,1.2,.6],[.2,.4,.7,.8]]],np.float32);p={'input_gamut':'clip','blue_hue':30}
        out,m=self.apply(a,effect(**p));np.testing.assert_allclose(out[0,:,:3],[scalar(v,p) for v in a[0,:,:3]],atol=8e-8,rtol=0)
        self.assertEqual(m['clipped_input_components'],2);self.assertEqual(m['preserved_residual_components'],0)

    def test_explicit_residual_retains_negative_and_superwhite_RGB(self):
        a=np.array([[[-.2,.1,.4,.2],[.3,.6,1.4,.8]]],np.float32);p={'input_gamut':'preserve_residual','blue_hue':-40,'magenta_lightness':.3}
        out,m=self.apply(a,effect(**p));np.testing.assert_allclose(out[0,:,:3],[scalar(v,p) for v in a[0,:,:3]],atol=1e-7,rtol=0)
        self.assertLess(float(out[0,0,:3].min()),0);self.assertGreater(float(out[0,1,:3].max()),1)
        self.assertEqual(m['preserved_residual_components'],2);self.assertEqual(m['clipped_input_components'],0)

    def test_output_clip_is_separate_from_input_residual_policy(self):
        a=fixture.rgba((-.2,.1,1.4,.5));p={'input_gamut':'preserve_residual','output_gamut':'clip','blue_hue':-20}
        out,m=self.apply(a,effect(**p));np.testing.assert_allclose(out[0,0,:3],scalar(a[0,0,:3],p),atol=8e-8,rtol=0)
        self.assertGreater(m['output_clipped_components'],0)

    def test_zero_controls_residual_is_identity_and_clip_is_explicit(self):
        a=fixture.rgba((-.2,.3,1.4,.6));out,_=self.apply(a,effect(input_gamut='preserve_residual'))
        self.assertEqual(out.tobytes(),a.tobytes());out,_=self.apply(a,effect(input_gamut='clip'))
        np.testing.assert_array_equal(out[0,0],np.array([0,.3,1,.6],np.float32))

    def test_zero_intensity_bypasses_gamut_policy_after_validation(self):
        a=fixture.rgba((-.2,.3,1.4,-0.));out,m=self.apply(a,effect(blue_hue=40,intensity=0,output_gamut='clip'))
        self.assertEqual(out.tobytes(),a.tobytes());self.assertFalse(m['gamut_policy_evaluated'])

    def test_srgb_operator_and_intensity_are_mixed_in_linear_working_RGB(self):
        a=fixture.rgba((.07,.17,.27,.4));p={'blue_hue':30,'cyan_saturation':-.2};srgb={'primaries':'bt709','transfer':'srgb'}
        out,_=self.apply(a,effect(**p,input_signal=srgb,output_signal=srgb,intensity=.35))
        encode=lambda v:12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055
        decode=lambda v:v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        mapped=scalar([encode(float(v)) for v in a[0,0,:3]],p)
        expected=[float(v)*.65+decode(g)*.35 for v,g in zip(a[0,0,:3],mapped)]
        np.testing.assert_allclose(out[0,0,:3],expected,atol=8e-8,rtol=0)

    def test_distinct_input_output_signals_are_honored(self):
        a=fixture.rgba((.2,.3,.4,.5));out,_=self.apply(a,effect(output_signal={'primaries':'bt709','transfer':'gamma22'}))
        np.testing.assert_allclose(out[0,0,:3],a[0,0,:3].astype(np.float64)**2.2,atol=3e-8,rtol=0)

    def test_all_six_easings_sample_original_author_time(self):
        expected={'linear':.25,'hold':0,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.15625}
        for mode,t in expected.items():
            e=effect();e['keyframes']=[track('orange_hue',-80,80,mode,controls=[0,1] if mode=='bezier' else None)]
            self.assertAlmostEqual(state_at(compile_hsl(e),25)['orange_hue'],-80+160*t,places=12)

    def test_large_rational_author_ticks_do_not_lose_fractional_position(self):
        n=2**60;e=effect();e['keyframes']=[track('parameters.blue_hue',-80,80,start=n,stop=n+8)]
        self.assertAlmostEqual(state_at(compile_hsl(e),Fraction(2*n+3,2))['blue_hue'],-50,places=12)

    def test_four_control_Bezier_solves_authored_time_root(self):
        e=effect();e['keyframes']=[track('green_lightness',-.4,.4,'bezier',controls=[.1,.8,.7,.2])]
        lo,hi=0.,1.
        for _ in range(80):
            u=(lo+hi)*.5;x=3*(1-u)**2*u*.1+3*(1-u)*u*u*.7+u**3
            if x<.25:lo=u
            else:hi=u
        u=(lo+hi)*.5;y=3*(1-u)**2*u*.8+3*(1-u)*u*u*.2+u**3
        self.assertAlmostEqual(state_at(compile_hsl(e),25)['green_lightness'],-.4+.8*y,places=12)

    def test_hold_boundaries_remain_half_open(self):
        e=effect();e['keyframes']=[track('red_hue',-80,80,'hold')];p=compile_hsl(e)
        self.assertEqual(state_at(p,np.nextafter(100.,-np.inf))['red_hue'],-80)
        self.assertEqual(state_at(p,100)['red_hue'],80)

    def test_each_parameter_and_intensity_can_animate_with_bounded_overshoot(self):
        e=effect();e['keyframes']=[track(n,0,1 if n=='intensity' else BOUNDS[n][1],'bezier',controls=[10,10]) for n in BOUNDS]
        sampled=state_at(compile_hsl(e),50)
        for name,bounds in BOUNDS.items():self.assertEqual(sampled[name],bounds[1])

    def test_later_author_mutation_cannot_change_compiled_plan(self):
        e=effect(red_hue=30);e['keyframes']=[track('blue_hue',0,60)];p=compile_hsl(e)
        e['parameters']['red_hue']=180;e['parameters']['input_signal']['transfer']='srgb';e['keyframes'][0]['keyframes'][0]['value']=99
        self.assertEqual(state_at(p,0)['red_hue'],30);self.assertEqual(state_at(p,0)['blue_hue'],0);self.assertEqual(p.input_signal,WORKING)

    def test_unknown_fields_wrong_types_and_parameter_bounds_reject(self):
        for p in ({'red_hue':True},{'red_hue':'30'},{'red_hue':math.inf},{'red_hue':181},{'blue_saturation':-1.1},{'intensity':-.1},{'unknown':1},{'input_gamut':'auto'},{'output_gamut':'auto'}):
            self.bad(lambda:compile_hsl(effect(**p)))
        self.bad(lambda:compile_hsl({**effect(),'red_hue':30}))

    def test_duplicate_unknown_and_invalid_keyframes_reject(self):
        for rows in ([track('red_hue',0,1),track('effect.red_hue',0,1)],[track('unknown',0,1)],
                     [track('red_hue',0,1,start=-1)],[track('red_hue',0,1,start=1,stop=1)],
                     [track('red_hue',0,1,'bezier',controls=[-1,0,2,1])]):
            e=effect();e['keyframes']=rows;self.bad(lambda:compile_hsl(e))

    def test_keyframe_counts_total_budget_and_double_locations_reject(self):
        e=effect();e['keyframes']=[{'property':'red_hue','keyframes':[{'at_tick':i,'value':0} for i in range(1025)]}];self.bad(lambda:compile_hsl(e))
        e['keyframes']=[{'property':name,'keyframes':[{'at_tick':i,'value':0} for i in range(1000)]} for name in list(BOUNDS)[:17]];self.bad(lambda:compile_hsl(e))
        e=effect(keyframes=[track('red_hue',0,1)]);e['keyframes']=[track('blue_hue',0,1)];self.bad(lambda:compile_hsl(e))

    def test_forged_plans_and_invalid_sample_clocks_reject(self):
        p=compile_hsl(effect());a=fixture.rgba((.2,.3,.4,.5))
        for bad in (replace(p,values=[]),replace(p,values=()),replace(p,values=p.values+(p.values[0],)),replace(p,input_gamut='guess'),replace(p,output_gamut='guess'),replace(p,input_signal={}),replace(p,tracks_json='[] ')):
            self.bad(lambda:apply_hsl(a,bad,0,working_signal=WORKING))
        for t in (-1,True,math.inf,'25'):self.bad(lambda:self.apply(a,tick=t))

    def test_surface_layout_and_late_bad_alpha_preserve_caller_pixels(self):
        for a in (np.ones((2,3,4),np.float64),np.ones((2,3,3),np.float32),np.ones((2,3,4),np.float32)[:,::-1]):self.bad(lambda:self.apply(a))
        for value in (math.nan,-.1,1.1):
            a=fixture.rgba((.2,.3,.4,.5),(7,11));a[-1,-1,3]=value;old=a.tobytes()
            self.bad(lambda:self.apply(a,effect(blue_hue=30),tile_pixels=1));self.assertEqual(a.tobytes(),old)

    def test_tile_size_and_readonly_input_have_exactly_equal_results(self):
        a=np.random.default_rng(109).uniform(-.2,1.4,(19,37,4)).astype(np.float32);a[...,3]=.5;a[0,0,3]=-0.;old=a.tobytes();a.setflags(write=False)
        e=effect(blue_hue=30,red_lightness=.3,green_saturation=-.4,input_gamut='preserve_residual')
        outputs=[self.apply(a,e,tile_pixels=t)[0] for t in (1,7,16384,262144)]
        for out in outputs:self.assertEqual(out.tobytes(),outputs[0].tobytes());self.assertEqual(out[...,3].tobytes(),a[...,3].tobytes())
        self.assertEqual(a.tobytes(),old)

    def test_workspace_and_retained_LUT_are_admitted_before_output(self):
        a=fixture.rgba((.2,.3,.4,.5));e=effect(blue_hue=30)
        with patch('ai_ad_editor.float_selective_hsl.np.empty_like',side_effect=AssertionError('allocated')):
            self.bad(lambda:self.apply(a,e,max_working_bytes=1),'FLOAT_SELECTIVE_HSL_BUDGET')
            self.bad(lambda:self.apply(a,e,retained_table_bytes=768*1024*1024),'FLOAT_SELECTIVE_HSL_BUDGET')
        for n in (0,True,262145):self.bad(lambda:self.apply(a,tile_pixels=n))

    def test_boolean_cancellation_inside_conversion_propagates(self):
        a=fixture.rgba((.2,.3,.4,.5),(20,30));old=a.tobytes();polls=[]
        def cancel():polls.append(1);return len(polls)>4
        self.bad(lambda:self.apply(a,effect(blue_hue=30),tile_pixels=100,cancel=cancel),'RENDER_CANCELLED');self.assertEqual(a.tobytes(),old)

    def test_callback_exception_preserves_input(self):
        a=fixture.rgba((.2,.3,.4,.5));old=a.tobytes()
        def cancel():raise RuntimeError('caller stop')
        with self.assertRaisesRegex(RuntimeError,'caller stop'):self.apply(a,effect(blue_hue=30),cancel=cancel)
        self.assertEqual(a.tobytes(),old)

    def test_transfer_overflow_is_explicit_and_preserves_input(self):
        a=fixture.rgba((3e38,2e38,1e38,.5));old=a.tobytes()
        self.bad(lambda:self.apply(a,effect(input_gamut='preserve_residual',output_signal={'primaries':'bt709','transfer':'gamma24'})))
        self.assertEqual(a.tobytes(),old)

    def test_ordered_exposure_LUT_curves_levels_balance_and_HSL(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_cube(root/'look.cube',2,transform=lambda r,g,b:(r*.7,g*.8,b*.9))
            compiler=EffectCompiler(resource_root=root,working_signal=WORKING);a=fixture.rgba((.2,.4,.6,.5))
            rows=[{'type':'exposure','keyframes':[track('amount',0,.5)]},
                {'type':'color_levels','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'alpha_output_white':.8}},
                {'type':'rgb_curves','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'all':'0/.1 1/.9'}},
                {'type':'lut3d','parameters':{'path':'look.cube','input_signal':LINEAR,'output_signal':LINEAR}},
                {'type':'color_wheel','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'gm':.1}},effect(blue_hue=30)]
            out,m=compiler.apply(a,compiler.compile(rows),50);expected=a
            for row in rows:expected,_=compiler.apply(expected,compiler.compile([row]),50)
            self.assertEqual(out.tobytes(),expected.tobytes());self.assertEqual(m['alpha'],'explicit-per-effect-alpha-mapping')
            reverse,_=compiler.apply(a,compiler.compile(list(reversed(rows))),50);self.assertFalse(np.array_equal(out,reverse))

    def test_presentation_window_keeps_original_HSL_keyframe_positions(self):
        p,s=fixture.image_project(fixture.rgba((.1,.2,.3,.5)),duration=200);e=effect();e['keyframes']=[track('blue_hue',-60,60,stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);host=FloatTimeline(p,'main',s,working_signal=WORKING)
        full=[host.render_frame(i)[0] for i in range(20)];selected=copy.deepcopy(p)
        selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':200,'offset_tick':70})
        host=FloatTimeline(selected,'main',s,working_signal=WORKING)
        for i in range(6):self.assertEqual(host.render_frame(i)[0].tobytes(),full[i+7].tobytes())

    def test_nested_reverse_child_and_parent_use_distinct_author_clocks(self):
        p,s=fixture.image_project(fixture.rgba((.1,.2,.3,.5)),duration=200);child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        e=effect();e['keyframes']=[track('blue_hue',-60,60,'hold',stop=160)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);parent=p['sequences'][0]['tracks'][0]['clips'][0]
        parent.pop('asset_id');parent.update(sequence_id='child',duration_tick=200,source_out_tick=200,reverse=True,effects=[effect(red_hue=10)])
        p['sequences'].append(child);out,_=FloatTimeline(p,'main',s,working_signal=WORKING).render_frame(4)
        expected,_=self.apply(fixture.rgba((.1,.2,.3,.5)),e,tick=np.nextafter(160.,-np.inf));expected,_=self.apply(expected,parent['effects'][0],tick=40)
        np.testing.assert_allclose(out,expected,atol=2e-7,rtol=0)

    def test_native_project_validator_accepts_HSL_and_duration_bounds(self):
        from ai_ad_editor.validator import validate_project
        e=effect();e['keyframes']=[track('effect.blue_hue',-60,60,stop=9000)]
        self.assertEqual(validate_hsl(e,duration_tick=9000),[]);self.assertTrue(validate_hsl(e,duration_tick=8999))
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick']=18000;case.s['tracks'][0]['clips'][0]['effects']=[e]
            result=validate_project(case.root,case.p);self.assertTrue(result['ok'],result)
        finally:case.doCleanups()

    def test_legacy_HSL_validation_keeps_its_existing_contract(self):
        from ai_ad_editor.validator import validate_project
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick']=18000
            case.s['tracks'][0]['clips'][0]['effects']=[{'type':'selective_hsl','parameters':{'red_hue':30}}]
            native=case.p['settings'].pop('pixel_pipeline');self.assertTrue(validate_project(case.root,case.p)['ok'])
            case.p['settings']['pixel_pipeline']=native;self.assertFalse(validate_project(case.root,case.p)['ok'])
        finally:case.doCleanups()

    def test_real_formal_preview_PCM_and_PNG16_share_HSL(self):
        import json
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;pixels=case.visual(np.broadcast_to(np.array([.2,.1,.05,.5],np.float32),(2,16,32,4)).copy());audio=case.audio()
            e=effect(red_hue=50,orange_saturation=-.3);e['keyframes']=[track('intensity',.25,.75,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects']=[e];result=case.execute(end=2);actual=case.reference(result)
            source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535);expected=source.copy()
            for i,strength in enumerate((.25,.75)):
                graded=np.array(scalar(source[i,0,0,:3],e['parameters']),np.float64)
                expected[i,...,:3]=((source[i,...,:3].astype(np.float64)*(1-strength)+graded*strength)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3]=1;np.testing.assert_allclose(actual,expected,atol=1e-7,rtol=0);self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),np.rint(actual[0].astype(np.float64)*65535),atol=1,rtol=0)
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal=render_project(case.root,case.p,case.s,case.root/'renders/hsl.mkv')
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload=np.moveaxis(np.rint(actual[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest());case.assert_clean()
        finally:case.doCleanups()

    def test_real_cache_hit_and_changed_band_invalidate_cache(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;case.visual(np.broadcast_to(np.array([.1,.2,.3,.5],np.float32),(2,16,32,4)).copy());case.audio();e=effect(blue_hue=20)
            case.s['tracks'][0]['clips'][0]['effects']=[e];one=case.execute(end=2);self.assertTrue(case.execute(end=2)['cache_hit'])
            e['parameters']['blue_hue']=30;two=case.execute(end=2);self.assertNotEqual(one['cache_key'],two['cache_key']);self.assertFalse(two['cache_hit']);case.assert_clean()
        finally:case.doCleanups()

    def test_capabilities_and_disabled_effects_are_explicit(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        row=build_capability_manifest()['capabilities']['timeline_native_float_selective_hsl']
        self.assertIn('preserve_residual_is_a_declared_creative_extension_not_HDR_appearance',row['limits'])
        compiler=EffectCompiler(resource_root=None,working_signal=WORKING)
        self.assertEqual(compiler.compile([{'type':'selective_hsl','enabled':False,'parameters':{'unknown':'bad'}}]),())
