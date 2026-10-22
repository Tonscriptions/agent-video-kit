"""Independent exposure precision, native oracle, and shared CLI-host boundaries."""
import copy
from dataclasses import replace
from decimal import Decimal, localcontext
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_exposure import apply_exposure, compile_effects
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as timeline_fixture
import test_float_preview as preview_fixture


def effect(amount=0, black=0, **values):
    return {'type':'exposure', 'parameters':{'amount':amount, 'black':black}, **values}


def apply(value, *effects, **options):
    return apply_exposure(value, compile_effects(list(effects)), **options)


class FloatExposureTests(unittest.TestCase):
    def test_all_65536_codes_and_alpha_bits_preserved_without_integer_edge(self):
        a = np.empty((256,256,4), np.float32)
        a[:,:,:3] = (np.arange(65536,dtype=np.float32)/65535).reshape(256,256,1)
        a[:,:,3] = a[:,:,0]
        out,meta = apply(a, effect(1), tile_pixels=997)
        np.testing.assert_array_equal(out[:,:,:3], a[:,:,:3]*2)
        np.testing.assert_array_equal(out[:,:,3].view('u4'), a[:,:,3].view('u4'))
        self.assertEqual(len(np.unique(out[:,:,0])),65536)
        self.assertFalse(meta['integer_quantization']); self.assertEqual(meta['clipping'],'none')

    def test_decimal_oracle_after_declared_binary32_coefficients(self):
        a = np.array([[[.003, .177, .81, .713]]],np.float32)
        plan = compile_effects([effect(.73,.041)])[0]
        out,_ = apply_exposure(a,(plan,))
        with localcontext() as ctx:
            ctx.prec = 60
            for i in range(3):
                diff = np.float32(float(Decimal(float(a[0,0,i]))-Decimal(plan.black)))
                expected = np.float32(float(Decimal(float(diff))*Decimal(plan.scale)))
                self.assertEqual(out[0,0,i].view('u4'),expected.view('u4'))

    def test_extended_RGB_hidden_RGB_and_adjacent_float32_values(self):
        a = np.array([[[-.25,1.5,np.nextafter(np.float32(.25),np.float32(1)),0],
            [.25,.125,.0625,1]]],np.float32)
        original = a.copy();out,_ = apply(a,effect(1))
        np.testing.assert_array_equal(out[:,:,:3],a[:,:,:3]*2)
        self.assertEqual(out[0,0,0],-.5);self.assertEqual(out[0,0,1],3)
        self.assertNotEqual(out[0,0,2],np.float32(.5))
        np.testing.assert_array_equal(a,original)

    def test_native_FFmpeg_float_oracle_including_singular_and_negative_denominator(self):
        width=1024
        a=np.zeros((1,width,4),np.float32)
        values=np.linspace(-.2,1.2,width,dtype=np.float32)
        a[:,:,:3]=values.reshape(1,width,1);a[:,:,3]=np.linspace(0,1,width,dtype=np.float32)
        raw=np.moveaxis(a[:,:,[1,2,0,3]],2,0).astype('<f4').tobytes()
        cases=[(0,0),(1,0),(-3,-1),(1,.1),(-1,.1),(.73,.041),(0,1),(3,1),
            (0,.9999999),(0,.999),(1,.5000001),(2,.25)]
        for amount,black in cases:
            with self.subTest(amount=amount,black=black):
                cmd=[ffmpeg_path(),'-nostdin','-v','error','-filter_threads','1','-f','rawvideo',
                    '-pixel_format','gbrapf32le','-video_size',f'{width}x1','-i','pipe:0',
                    '-vf',f'exposure=exposure={amount}:black={black}','-frames:v','1','-f','rawvideo','-pix_fmt','gbrapf32le','pipe:1']
                native=subprocess.run(cmd,input=raw,capture_output=True)
                self.assertEqual(native.returncode,0,native.stderr.decode('utf8','replace'))
                expected=np.moveaxis(np.frombuffer(native.stdout,'<f4').reshape(4,1,width),0,2)[:,:,[2,0,1,3]]
                actual,meta=apply(a,effect(amount,black))
                np.testing.assert_allclose(actual[:,:,:3],expected[:,:,:3],rtol=3e-7,atol=3e-8)
                np.testing.assert_array_equal(actual[:,:,3].view('u4'),expected[:,:,3].view('u4'))
                if black==1 and amount==0:self.assertTrue(meta['effects'][0]['singular_gain_1024'])

    def test_chain_order_and_disabled_unported_effect(self):
        a=timeline_fixture.rgba((.25,.5,.75,.4))
        one,_=apply(a,effect(1),effect(-1,.1))
        two,_=apply(a,effect(-1,.1),effect(1))
        self.assertFalse(np.array_equal(one,two))
        out,_=apply(a,{'type':'unknown','enabled':False},effect())
        np.testing.assert_array_equal(out,a)

    def test_identity_is_owned_and_bit_exact_including_negative_zero(self):
        a=timeline_fixture.rgba((-.0,.5,1,.3));out,_=apply(a,effect())
        self.assertFalse(np.shares_memory(a,out));np.testing.assert_array_equal(out.view('u4'),a.view('u4'))

    def test_argument_aliases_and_malformed_effects_reject(self):
        good=compile_effects([{'type':'exposure','parameters':{'exposure':1,'black':0}}])
        self.assertEqual(good,compile_effects([effect(1)]))
        bad=[None,{},[{'type':'exposure','parameters':None}],[effect(True)], [effect(float('nan'))],
            [effect(4)],[effect(0,2)],[effect(enabled=1)],
            [{'type':'exposure','parameters':{'amount':1,'exposure':2}}],
            [{'type':'exposure','amount':1,'parameters':{}}],
            [{'type':'exposure','parameters':{'gain':1}}],
            [{'type':'exposure','keyframes':[]}], [effect()]*129]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(AppError):compile_effects(value)
        with self.assertRaises(AppError) as caught:compile_effects([{'type':'brightness'}])
        self.assertEqual(caught.exception.code,'FLOAT_TIMELINE_UNSUPPORTED')

    def test_invalid_surface_late_tile_and_alpha_fail_without_input_mutation(self):
        for channel,value in [(0,np.inf),(1,np.nan),(3,-.1),(3,1.1)]:
            a=timeline_fixture.rgba(shape=(4,8));a[-1,-1,channel]=value;before=a.tobytes()
            with self.assertRaises(AppError):apply(a,effect(1),tile_pixels=3)
            self.assertEqual(a.tobytes(),before)
        for a in [np.zeros((2,2,4),np.float64),np.zeros((2,2,4),np.float32)[:,::-1],np.zeros((0,2,4),np.float32)]:
            with self.assertRaises(AppError):apply(a,effect())

    def test_budget_and_tampered_plan_reject_before_output(self):
        a=timeline_fixture.rgba()
        with self.assertRaises(AppError):apply(a,effect(),max_working_bytes=1)
        with self.assertRaises(AppError):apply(a,effect(),tile_pixels=True)
        plan=compile_effects([effect(1)])[0]
        with self.assertRaises(AppError):apply_exposure(a,(replace(plan,scale=3),))

    def test_mid_tile_cancel_and_overflow_leave_source_intact(self):
        a=timeline_fixture.rgba(shape=(64,64));before=a.tobytes();calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==5:raise RuntimeError('explicit cancel')
        with self.assertRaisesRegex(RuntimeError,'explicit cancel'):apply(a,effect(1),tile_pixels=32,cancel=cancel)
        self.assertEqual(a.tobytes(),before)
        a[0,0,0]=np.finfo(np.float32).max
        with self.assertRaises(AppError):apply(a,effect(3))

    def test_timeline_source_exposure_precedes_mask_affine_and_alpha_composition(self):
        p,s=timeline_fixture.image_project(timeline_fixture.rgba((.125,.25,.375,.5)))
        p['sequences'][0]['tracks'][0]['clips'][0]['effects']=[effect(1)]
        before=copy.deepcopy(p)
        host=FloatTimeline(p,'main',s,working_signal=timeline_fixture.LINEAR)
        out,meta=host.render_frame(0)
        np.testing.assert_array_equal(out,timeline_fixture.rgba((.25,.5,.75,.5)))
        self.assertEqual(p,before);self.assertEqual(meta['layers'][0]['effects']['effects'][0]['scale'],2)

    def test_nested_group_exposure_applies_after_child_composition(self):
        p,s=timeline_fixture.image_project(timeline_fixture.rgba((.125,.25,.375,.5)))
        child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        clip=p['sequences'][0]['tracks'][0]['clips'][0]
        clip.pop('asset_id');clip['sequence_id']='child';clip['effects']=[effect(1)]
        p['sequences'].append(child)
        host=FloatTimeline(p,'main',s,working_signal=timeline_fixture.LINEAR)
        out,_=host.render_frame(0)
        np.testing.assert_array_equal(out,timeline_fixture.rgba((.25,.5,.75,.5)))

    def test_nonlinear_working_signal_and_dynamic_channels_reject(self):
        p,s=timeline_fixture.image_project();p['sequences'][0]['tracks'][0]['clips'][0]['effects']=[effect(1)]
        s['a'].signal=ColorSignal('bt709','srgb')
        with self.assertRaises(AppError):FloatTimeline(p,'main',s,working_signal=ColorSignal('bt709','srgb'))
        with self.assertRaises(AppError):compile_effects([effect(keyframes=[{'property':'amount'}])])

    def test_real_standard_render_and_preview_share_exposure_and_PNG16(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000
            pixels=case.visual(np.broadcast_to(np.array([.125,.125,.125,1],np.float32),(2,16,32,4)).copy())
            case.s['tracks'][0]['clips'][0]['effects']=[effect(1)]
            output=case.execute(end=2);actual=case.reference(output)
            expected=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535
            expected[:,:,:,:3]*=2
            np.testing.assert_array_equal(actual,expected)
            frame=case.execute(mode='frame');png=case.png(frame)
            self.assertTrue(np.all(png[:,:,:3]==16384))
            # The real standard renderer must execute this same authored effect,
            # not a separately reproduced point-transform fixture.
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):
                result=render_project(case.root,case.p,case.s,case.root/'renders/exposure.mkv')
            data=case.native([ffmpeg_path(),'-nostdin','-v','error','-i',result['path'],
                '-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
            y=np.frombuffer(data,'<u2').reshape(2,3,16,32)[:,0]
            self.assertLessEqual(float(np.max(np.abs(y-(64+expected[:,:,:,0]*876)))),1.5)
            case.assert_clean()
        finally:
            case.tearDown();case.doCleanups()


if __name__=='__main__':unittest.main()
