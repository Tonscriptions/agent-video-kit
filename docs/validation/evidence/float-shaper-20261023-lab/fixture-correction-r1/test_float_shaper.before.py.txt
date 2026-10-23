"""Independent Hermite, actual native Float32, and author-clock shaper proofs."""
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal, convert_rgba
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_lut import compile_lut, apply_lut, verify_dependencies, INTERPOLATIONS, INTERPOLATIONS_1D
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.lut_library import parse_lut_metadata, prepare_lut_registration, register_lut
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as fixture
from test_float_lut import write_cube, scalar_lookup, track
import test_float_preview as preview_fixture

LINEAR={'primaries':'bt709','transfer':'linear'}
SRGB={'primaries':'bt709','transfer':'srgb'}


def write_shaper(path, values, *, cube=None, ranges=None, domains=None):
    text='TITLE "Original 1D # and shaper fixture" # preserved title\n'
    if values is not None: text+='LUT_1D_SIZE '+str(len(values))+'\n'
    if cube is not None: text+='LUT_3D_SIZE '+str(len(cube))+'\n'
    for dimension,limits in (ranges or {}).items():
        text+=f'LUT_{dimension}D_INPUT_RANGE {limits[0]} {limits[1]}\n'
    if domains:
        text+='DOMAIN_MIN '+' '.join(map(str,domains[0]))+'\nDOMAIN_MAX '+' '.join(map(str,domains[1]))+'\n'
    rows=[]
    if values is not None: rows.extend(np.asarray(values,np.float32).reshape(-1,3))
    if cube is not None: rows.extend(np.asarray(cube,np.float32).reshape(-1,3))
    path.write_text(text+''.join(' '.join(format(float(v),'.9g') for v in row)+'\n' for row in rows),encoding='utf8',newline='\n')


def one_d_oracle(table, rgb, method='linear', domain=((0,0,0),(1,1,1))):
    """Scalar interpolation from Hermite endpoint values/tangents, not weights."""
    result=np.empty_like(rgb,dtype=np.float32);n=len(table)
    for i in range(len(rgb)):
        for channel in range(3):
            a,b=domain[0][channel],domain[1][channel]
            x=float(np.float32(min(1.,max(0.,(float(rgb[i,channel])-a)/(b-a))))*np.float32(n-1))
            left=int(math.floor(x));right=min(left+1,n-1);t=x-left
            p,q=float(table[left,channel]),float(table[right,channel])
            if method=='nearest': out=float(table[int(math.floor(x+.5)),channel])
            elif method in ('linear','cosine'):
                u=t if method=='linear' else (1-math.cos(math.pi*t))/2
                out=p+(q-p)*u
            else:
                before=float(table[max(left-1,0),channel]);after=float(table[min(right+1,n-1),channel])
                factor=1. if method=='cubic' else .5
                m0,m1=(q-before)*factor,(after-p)*factor
                out=(2*t**3-3*t**2+1)*p+(t**3-2*t**2+t)*m0+(-2*t**3+3*t**2)*q+(t**3-t**2)*m1
            result[i,channel]=out
    return result


def effect(**parameters):
    return {'type':'lut','parameters':{'path':'look.cube','input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}


class FloatShaperTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='float-shaper-',dir=base);self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.values=np.array([[-.2,.1,.3],[.4,.2,1.3],[.8,1.4,-.1],[1.2,.9,1.1]],np.float32)
        write_shaper(self.root/'look.cube',self.values)

    def plan(self,e=None,**kwargs):
        return compile_lut(e or effect(),resource_root=self.root,**kwargs)

    def apply(self,a,e=None,tick=0,**kwargs):
        return apply_lut(a,self.plan(e),tick,working_signal=fixture.LINEAR,**kwargs)

    def native(self,a,filters):
        result=subprocess.run([ffmpeg_path(),'-nostdin','-v','error','-cpuflags','0','-filter_threads','1',
            '-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{a.shape[1]}x{len(a)}','-i','pipe:0',
            '-vf',filters,'-frames:v','1','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1'],
            input=np.moveaxis(a[...,[1,2,0,3]],2,0).astype('<f4').tobytes(),capture_output=True,cwd=self.root,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        return np.moveaxis(np.frombuffer(result.stdout,'<f4').reshape(4,*a.shape[:2])[[2,0,1,3]],0,-1).copy()

    def test_all_five_methods_match_independent_scalar_hermite_oracle(self):
        rng=np.random.default_rng(112)
        a=rng.uniform(-.4,1.4,(3,31,4)).astype(np.float32);a[...,3]=rng.uniform(0,1,(3,31))
        a.reshape(-1,4)[:7,:3]=np.array([0,1,.5,1/3,2/3,-1,2])[:,None]
        for method in INTERPOLATIONS_1D:
            with self.subTest(method=method):
                actual,meta=self.apply(a,effect(interpolation_1d=method))
                expected=one_d_oracle(self.values,a.reshape(-1,4)[:,:3],method).reshape(3,31,3)
                np.testing.assert_array_equal(actual[...,:3],expected)
                np.testing.assert_array_equal(actual[...,3],a[...,3]);self.assertEqual(meta['stages'],['1D'])

    def test_five_methods_match_actual_native_Float32_1D(self):
        rng=np.random.default_rng(113);a=rng.uniform(-.3,1.3,(3,32,4)).astype(np.float32);a[...,3]=rng.random((3,32))
        for method in INTERPOLATIONS_1D:
            with self.subTest(method=method):
                actual,_=self.apply(a,effect(interpolation_1d=method))
                np.testing.assert_allclose(actual,self.native(a,f'lut1d=file=look.cube:interp={method}'),rtol=0,atol=9e-7)

    def test_nearest_half_ties_choose_upper_sample(self):
        values=np.arange(6,dtype=np.float32).reshape(2,3);write_shaper(self.root/'look.cube',values)
        actual,_=self.apply(fixture.rgba((.5,.5,.5,.4)),effect(interpolation_1d='nearest'))
        np.testing.assert_array_equal(actual[...,:3],np.broadcast_to(values[1],actual[...,:3].shape))

    def test_per_channel_nonzero_domains_are_normalized_and_clamped(self):
        domain=((-2,.25,3),(2,.75,5));write_shaper(self.root/'look.cube',self.values,domains=domain)
        a=fixture.rgba((-.5,.4,4,.2));a[0,:3,:3]=[[-10,0,-1],[0,.5,4],[10,2,9]]
        actual,meta=self.apply(a)
        np.testing.assert_array_equal(actual[...,:3],one_d_oracle(self.values,a.reshape(-1,4)[:,:3],domain=domain).reshape(a.shape[:2]+(3,)))
        self.assertEqual(meta['domain_1d_min'],list(domain[0]))

    def test_Resolve_1D_range_offsets_are_applied(self):
        write_shaper(self.root/'look.cube',self.values,ranges={1:(-2,4)})
        a=fixture.rgba((1,-2,4,1));actual,meta=self.apply(a)
        expected=one_d_oracle(self.values,a.reshape(-1,4)[:,:3],domain=((-2,)*3,(4,)*3)).reshape(a.shape[:2]+(3,))
        np.testing.assert_array_equal(actual[...,:3],expected);self.assertEqual(meta['table_dialect'],'resolve')

    def test_Resolve_3D_range_offsets_are_applied_without_1D(self):
        cube=write_cube(self.root/'cube.cube',2);write_shaper(self.root/'look.cube',None,cube=cube,ranges={3:(-1,2)})
        a=fixture.rgba((.2,.4,.6,1));actual,_=self.apply(a)
        expected=scalar_lookup(cube,a.reshape(-1,4)[:,:3],'tetrahedral',((-1,)*3,(2,)*3)).reshape(a.shape[:2]+(3,))
        np.testing.assert_array_equal(actual[...,:3],expected)

    def test_combined_shaper_runs_before_nonlinear_cross_channel_cube(self):
        cube=write_cube(self.root/'cube.cube',4);write_shaper(self.root/'look.cube',self.values,cube=cube)
        a=fixture.rgba((.23,.51,.76,1));actual,meta=self.apply(a)
        first=one_d_oracle(self.values,a.reshape(-1,4)[:,:3])
        expected=scalar_lookup(cube,first,'tetrahedral').reshape(a.shape[:2]+(3,))
        reverse=one_d_oracle(self.values,scalar_lookup(cube,a.reshape(-1,4)[:,:3],'tetrahedral'))
        np.testing.assert_array_equal(actual[...,:3],expected)
        self.assertFalse(np.allclose(first,reverse));self.assertEqual(meta['stages'],['1D','3D'])

    def test_all_25_method_pairs_match_separate_actual_native_stages(self):
        cube=write_cube(self.root/'cube.cube',4);write_shaper(self.root/'shaper.cube',self.values)
        write_shaper(self.root/'look.cube',self.values,cube=cube)
        rng=np.random.default_rng(114);a=rng.uniform(0,1,(2,16,4)).astype(np.float32)
        for first in INTERPOLATIONS_1D:
            for second in INTERPOLATIONS:
                with self.subTest(first=first,second=second):
                    actual,_=self.apply(a,effect(interpolation_1d=first,interpolation=second))
                    reference=self.native(a,f'lut1d=file=shaper.cube:interp={first},lut3d=file=cube.cube:interp={second}')
                    np.testing.assert_allclose(actual,reference,rtol=0,atol=1.3e-6)

    def test_combined_per_stage_ranges_and_Float32_stage_boundary(self):
        cube=write_cube(self.root/'cube.cube',3);write_shaper(self.root/'look.cube',self.values,cube=cube,ranges={1:(-1,2),3:(-.3,1.4)})
        rng=np.random.default_rng(115);a=rng.uniform(0,1,(2,7,4)).astype(np.float32)
        actual,_=self.apply(a,effect(interpolation='trilinear',interpolation_1d='spline'))
        first=one_d_oracle(self.values,a.reshape(-1,4)[:,:3],'spline',((-1,)*3,(2,)*3))
        expected=scalar_lookup(cube,first,'trilinear',((-.3,)*3,(1.4,)*3)).reshape(a.shape[:2]+(3,))
        np.testing.assert_array_equal(actual[...,:3],expected)

    def test_alpha_bits_and_hidden_RGB_are_preserved_independently(self):
        a=fixture.rgba((.3,.4,.5,0));a[0,:3,3]=[-0.,np.nextafter(np.float32(0),np.float32(1)),.5]
        actual,_=self.apply(a)
        np.testing.assert_array_equal(actual[...,3].view(np.uint32),a[...,3].view(np.uint32))
        self.assertGreater(float(actual[0,0,0]),0)

    def test_zero_intensity_preserves_all_Float32_bits(self):
        a=fixture.rgba((-.0,-2,3,-.0));actual,meta=self.apply(a,effect(intensity=0))
        np.testing.assert_array_equal(actual.view(np.uint32),a.view(np.uint32));self.assertTrue(meta['intensity_zero_bit_exact'])

    def test_table_outputs_and_cubic_spline_overshoots_remain_unclipped(self):
        values=np.array([[-1]*3,[2]*3,[2]*3,[-1]*3],np.float32);write_shaper(self.root/'look.cube',values)
        for method in ('cubic','spline'):
            actual,_=self.apply(fixture.rgba((.5,.5,.5,1)),effect(interpolation_1d=method))
            self.assertGreater(float(actual[0,0,0]),2)

    def test_intensity_mixes_in_linear_working_signal_after_srgb_1D(self):
        a=fixture.rgba((.15,.3,.55,.6));e=effect(input_signal=SRGB,output_signal=SRGB,intensity=.3)
        actual,_=self.apply(a,e)
        encoded=convert_rgba(a,fixture.LINEAR,ColorSignal('bt709','srgb'))[0]
        graded=encoded.copy();graded[...,:3]=one_d_oracle(self.values,encoded.reshape(-1,4)[:,:3]).reshape(a.shape[:2]+(3,))
        linear=convert_rgba(graded,ColorSignal('bt709','srgb'),fixture.LINEAR)[0]
        expected=(a[...,:3].astype(np.float64)*.7+linear[...,:3].astype(np.float64)*.3).astype(np.float32)
        np.testing.assert_array_equal(actual[...,:3],expected)

    def test_author_intensity_six_modes_and_Fraction_ticks(self):
        for mode in ('linear','hold','ease_in','ease_out','ease_in_out','bezier'):
            with self.subTest(mode=mode):
                e=effect();e['keyframes']=[track(mode=mode,controls=[.2,.8] if mode=='bezier' else None)]
                a=fixture.rgba((.2,.4,.6,1));actual,meta=self.apply(a,e,Fraction(50))
                full,_=self.apply(a);strength=0 if mode=='hold' else .25 if mode=='ease_in' else .75 if mode=='ease_out' else .5
                np.testing.assert_allclose(actual[...,:3],a[...,:3]*(1-strength)+full[...,:3]*strength,rtol=0,atol=6e-8)
                self.assertEqual(meta['author_tick'],'50')

    def test_combined_table_payload_and_arrays_are_immutable(self):
        cube=write_cube(self.root/'cube.cube',3);write_shaper(self.root/'look.cube',self.values,cube=cube)
        plan=self.plan();self.assertEqual(len(plan.cube.payload),(4+27)*12)
        for table in (plan.cube.table_1d,plan.cube.table):
            with self.assertRaises(ValueError):table.setflags(write=True)
        np.testing.assert_array_equal(plan.cube.table_1d,self.values);np.testing.assert_array_equal(plan.cube.table,cube)

    def test_registered_combined_metadata_counts_both_stages_and_pins_SHA(self):
        cube=write_cube(self.root/'cube.cube',3);write_shaper(self.root/'look.cube',self.values,cube=cube,ranges={1:(-1,2),3:(0,1)})
        metadata=parse_lut_metadata(self.root/'look.cube')
        self.assertEqual(metadata['expected_samples'],31);self.assertEqual(metadata['sample_count'],31)
        self.assertTrue(metadata['sample_count_valid']);self.assertEqual(metadata['lut_1d_size'],4)
        self.assertEqual(metadata['lut_1d_input_range'],[-1,2])
        record=register_lut(self.root,prepare_lut_registration(self.root,self.root/'look.cube',lut_id='combined'))
        e=effect(lut_id='combined');e['parameters'].pop('path');plan=self.plan(e)
        verify_dependencies(plan.dependencies);self.assertEqual(plan.cube.dependency.sha256,record['sha256'])
        (self.root/record['uri']).write_text('modified',encoding='utf8')
        with self.assertRaises(AppError):verify_dependencies(plan.dependencies)

    def test_1D_registry_metadata_and_BOM_title_comments(self):
        path=self.root/'look.cube';path.write_bytes(b'\xef\xbb\xbf'+path.read_bytes())
        metadata=parse_lut_metadata(path);self.assertEqual(metadata['lut_1d_size'],4)
        self.assertTrue(metadata['sample_count_valid']);self.assertEqual(metadata['expected_samples'],4)
        self.assertEqual(self.plan().cube.dependency.sha256,'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest())

    def test_1D_and_3D_header_order_does_not_change_data_stage_order(self):
        cube=write_cube(self.root/'cube.cube',2);path=self.root/'look.cube'
        write_shaper(path,self.values,cube=cube);a=self.plan().cube.payload
        text=path.read_text(encoding='utf8').replace('LUT_1D_SIZE 4\nLUT_3D_SIZE 2','LUT_3D_SIZE 2\nLUT_1D_SIZE 4')
        path.write_text(text,encoding='utf8');self.assertEqual(self.plan().cube.payload,a)

    def test_incomplete_extra_nan_infinite_or_unknown_headers_reject(self):
        for text in ('LUT_1D_SIZE 4\n0 0 0\n','LUT_1D_SIZE 2\n'+'0 0 0\n'*3,
            'LUT_1D_SIZE 2\n'+'nan 0 0\n'*2,'LUT_1D_SIZE 2\n'+'inf 0 0\n'*2,
            'LUT_1D_SIZE 2\nLUT_UNKNOWN 1\n'+'0 0 0\n'*2,
            'LUT_1D_SIZE 2\nLUT_3D_SIZE 2\n'+'0 0 0\n'*9):
            with self.subTest(text=text[:45]):
                (self.root/'look.cube').write_text(text,encoding='utf8')
                with self.assertRaises(AppError):self.plan()

    def test_invalid_sizes_duplicate_headers_and_post_data_headers_reject(self):
        for text in ('LUT_1D_SIZE 1\n','LUT_1D_SIZE 65537\n','LUT_1D_SIZE 2.0\n','LUT_1D_SIZE true\n',
            'LUT_1D_SIZE 2\nLUT_1D_SIZE 2\n0 0 0\n1 1 1\n',
            'LUT_1D_SIZE 2\n0 0 0\nTITLE "late"\n1 1 1\n'):
            (self.root/'look.cube').write_text(text,encoding='utf8')
            with self.assertRaises(AppError):self.plan()

    def test_ambiguous_domains_Resolve_ranges_and_missing_dimensions_reject(self):
        cube=write_cube(self.root/'cube.cube',2)
        for options in ({'cube':cube,'domains':((0,0,0),(1,1,1))},
            {'ranges':{1:(0,1)},'domains':((0,0,0),(1,1,1))},{'ranges':{3:(0,1)}},
            {'ranges':{1:(2,1)}},{'ranges':{1:(0,float('nan'))}}):
            write_shaper(self.root/'look.cube',self.values,**options)
            with self.assertRaises(AppError):self.plan()

    def test_combined_and_max_1D_budget_reject_before_table_allocation(self):
        for headers,budget in [('LUT_1D_SIZE 65536\n',1024),('LUT_1D_SIZE 65536\nLUT_3D_SIZE 256\n',2000000)]:
            (self.root/'look.cube').write_text(headers,encoding='utf8')
            with patch('ai_ad_editor.float_lut.bytearray',side_effect=AssertionError('unadmitted allocation'),create=True):
                with self.assertRaises(AppError) as caught:self.plan(max_working_bytes=budget)
            self.assertEqual(caught.exception.code,'FLOAT_LUT_BUDGET')

    def test_retained_tables_share_cache_and_are_charged_for_both_stages(self):
        cube=write_cube(self.root/'cube.cube',2);write_shaper(self.root/'look.cube',self.values,cube=cube)
        compiler=EffectCompiler(resource_root=self.root,working_signal=fixture.LINEAR)
        plans=compiler.compile([effect(),effect()]);actual,metadata=compiler.apply(fixture.rgba(),plans,0)
        self.assertIs(plans[0].cube,plans[1].cube);self.assertEqual(len(compiler.cubes),1)
        retained=len(plans[0].cube.payload)
        with self.assertRaises(AppError):apply_lut(fixture.rgba(),plans[0],0,working_signal=fixture.LINEAR,retained_table_bytes=retained-1)

    def test_workspace_rejects_before_surface_output_allocation(self):
        plan=self.plan();a=fixture.rgba()
        with patch('ai_ad_editor.float_lut.np.empty_like',side_effect=AssertionError('unadmitted output')):
            with self.assertRaises(AppError):apply_lut(a,plan,0,working_signal=fixture.LINEAR,max_working_bytes=1024)

    def test_changed_source_is_rejected_while_plan_keeps_original_shaper(self):
        plan=self.plan();a=fixture.rgba();before=apply_lut(a,plan,0,working_signal=fixture.LINEAR)[0]
        write_shaper(self.root/'look.cube',self.values+1)
        np.testing.assert_array_equal(apply_lut(a,plan,0,working_signal=fixture.LINEAR)[0],before)
        with self.assertRaises(AppError):verify_dependencies(plan.dependencies)

    def test_cancel_is_polled_before_each_shared_stage(self):
        cube=write_cube(self.root/'cube.cube',2);write_shaper(self.root/'look.cube',self.values,cube=cube)
        plan=self.plan();count=0
        def cancel():
            nonlocal count
            count+=1
            if count==5:raise AppError('TEST_CANCEL','controlled callback',exit_code=2)
        with self.assertRaises(AppError) as caught:apply_lut(fixture.rgba(shape=(20,30)),plan,0,working_signal=fixture.LINEAR,tile_pixels=5,cancel=cancel)
        self.assertEqual(caught.exception.code,'TEST_CANCEL');self.assertEqual(count,5)

    def test_invalid_1D_method_and_no_1D_stage_never_silently_ignore_parameter(self):
        for method in ('tetrahedral','invalid',None,True,[],{}):
            with self.assertRaises(AppError):self.plan(effect(interpolation_1d=method))
        write_cube(self.root/'look.cube',2)
        with self.assertRaises(AppError):self.plan(effect(interpolation_1d='linear'))

    def test_nonfinite_surfaces_and_invalid_alpha_reject(self):
        for value in (float('nan'),float('inf'),-float('inf')):
            a=fixture.rgba();a[0,0,0]=value
            with self.assertRaises(AppError):self.apply(a)
        for value in (-.1,1.1):
            a=fixture.rgba();a[0,0,3]=value
            with self.assertRaises(AppError):self.apply(a)

    def test_nonfinite_1D_interpolation_does_not_reach_3D_indices(self):
        large=np.float32(np.finfo(np.float32).max)
        values=np.array([[-large]*3,[large]*3,[large]*3,[-large]*3],np.float32)
        cube=write_cube(self.root/'cube.cube',2);write_shaper(self.root/'look.cube',values,cube=cube)
        with self.assertRaises(AppError) as caught:self.apply(fixture.rgba((.5,.5,.5,1)),effect(interpolation_1d='cubic'))
        self.assertEqual(caught.exception.code,'FLOAT_LUT_VALUES')

    def test_different_tiles_produce_identical_1D_and_shaper_pixels(self):
        cube=write_cube(self.root/'cube.cube',3);write_shaper(self.root/'look.cube',self.values,cube=cube)
        a=np.random.default_rng(116).uniform(0,1,(13,25,4)).astype(np.float32);baseline=self.apply(a)[0]
        for tile in (1,7,127,262144):np.testing.assert_array_equal(self.apply(a,tile_pixels=tile)[0],baseline)

    def test_ordered_exposure_shaper_chain_has_distinct_order(self):
        compiler=EffectCompiler(resource_root=self.root,working_signal=fixture.LINEAR)
        exposure={'type':'exposure','parameters':{'amount':1}}
        first=compiler.apply(fixture.rgba(),compiler.compile([effect(),exposure]),0)[0]
        second=compiler.apply(fixture.rgba(),compiler.compile([exposure,effect()]),0)[0]
        self.assertFalse(np.allclose(first,second))

    def test_presentation_window_uses_original_author_intensity(self):
        write_shaper(self.root/'look.cube',np.array([[1,0,0],[1,0,0]],np.float32))
        p,s=fixture.image_project(fixture.rgba((0,0,1,1)),duration=30);e=effect();e['keyframes']=[track()]
        c=p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(duration_tick=30,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':100,'offset_tick':40},effects=[e])
        before=copy.deepcopy(p);actual,_=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR,resource_root=self.root).render_frame(0)
        np.testing.assert_array_equal(actual,fixture.rgba((.4,0,.6,1)));self.assertEqual(p,before)

    def test_real_formal_preview_PCM_PNG_and_shaper_cache_invalidation(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000
            original=fixture.rgba((.2,.4,.6,.5),shape=(16,32));original[...,0]=np.arange(32,dtype=np.float32)[None,:]/31
            pixels=case.visual(np.stack([original]*2));audio=case.audio();path=case.root/'look.cube'
            constant=np.array([[1,0,0],[1,0,0]],np.float32);write_shaper(path,constant)
            e=effect();e['keyframes']=[track(left=.25,right=.75,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects']=[e];before=copy.deepcopy(case.p)
            result=case.execute(end=2);actual=case.reference(result)
            source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535;expected=source.copy()
            for i,strength in enumerate((.25,.75)):
                graded=(source[i,...,:3].astype(np.float64)*(1-strength)+np.array([1,0,0])*strength).astype(np.float32)
                expected[i,...,:3]=(graded.astype(np.float64)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3]=1
            np.testing.assert_allclose(actual,expected,rtol=0,atol=6e-8)
            self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            self.assertTrue(case.execute(end=2)['cache_hit'])
            png=case.png(case.execute(mode='frame'));np.testing.assert_allclose(png,np.rint(expected[0].astype(np.float64)*65535).astype(np.uint16),rtol=0,atol=1)
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal=render_project(case.root,case.p,case.s,case.root/'renders/shaper.mkv')
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload=np.moveaxis(np.rint(expected[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest())
            delivered=case.native([ffmpeg_path(),'-nostdin','-v','error','-i',formal['path'],'-map','0:a:0','-vn','-f','f32le','-c:a','pcm_f32le','pipe:1'])
            self.assertEqual(delivered,audio[:9600].tobytes())
            for section in ('settings','sequences','assets'):self.assertEqual(case.p[section],before[section])
            write_shaper(path,np.array([[0,0,1],[0,0,1]],np.float32));changed=case.execute(end=2)
            self.assertNotEqual(changed['cache_key'],result['cache_key']);self.assertFalse(changed['cache_hit'])
            self.assertFalse(np.array_equal(case.reference(changed),actual));case.assert_clean()
        finally:case.doCleanups()
