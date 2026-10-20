"""Native ABI, program validation, real backends, dimensions and isolation."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import unittest
from unittest.mock import patch
from ai_ad_editor import hsl_native,hsl_program
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.selective_hsl import SPECS
from test_selective_hsl import SelectiveCase,effect,FRAME,oracle_frame

PACKAGE=Path(hsl_native.__file__).parent
MANIFEST=json.loads((PACKAGE/'native_hsl_manifest.json').read_bytes())


class NativeHSLTests(SelectiveCase):
    def setUp(self):
        super().setUp();selection=patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'native'})
        selection.start();self.addCleanup(selection.stop)

    def library(self):
        library=ctypes.CDLL(str(PACKAGE/MANIFEST['binary_filename']))
        library.avk_hsl_validate_program.argtypes=[ctypes.c_char_p];library.avk_hsl_validate_program.restype=ctypes.c_int
        library.f0r_init.restype=ctypes.c_int;self.assertEqual(library.f0r_init(),1);self.addCleanup(library.f0r_deinit)
        library.f0r_construct.argtypes=[ctypes.c_uint,ctypes.c_uint];library.f0r_construct.restype=ctypes.c_void_p
        library.f0r_destruct.argtypes=[ctypes.c_void_p]
        library.f0r_set_param_value.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
        library.f0r_update.argtypes=[ctypes.c_void_p,ctypes.c_double,ctypes.c_void_p,ctypes.c_void_p]
        return library

    def fake_package(self):
        fake=self.root/'fake-package';fake.mkdir()
        for name in ['native_hsl_manifest.json','native_hsl.c','NATIVE_HSL_LICENSE.txt',MANIFEST['binary_filename']]:
            shutil.copyfile(PACKAGE/name,fake/name)
        return fake

    def program(self,**parameters):
        return hsl_program.compile_program([str(parameters.get(name,spec[1])) for name,spec in SPECS.items()])[0]

    def test_default_executes_verified_native_backend_and_hash_named_module(self):
        _,metadata,_=self.native(effect(),count=2)
        self.assertEqual(metadata[0]['backend'],'ffmpeg:frei0r')
        self.assertEqual(metadata[0]['plugin_sha256'],MANIFEST['binary_sha256'])
        self.assertEqual(metadata[0]['program']['format'],'AVKHSL01')
        self.assertNotEqual(metadata[0]['reference_kernel_sha256'],metadata[0]['kernel_sha256'])

    def test_all_six_easings_match_actual_expression_backend(self):
        for easing in ['hold','linear','ease_in','ease_out','ease_in_out','bezier']:
            value=effect(params={'orange_saturation':.6,'purple_lightness':-.3},easing=easing)
            native=self.native(value)[0]
            with patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'expression'}):reference=self.native(value)[0]
            for a,b in zip(native,reference):self.compare(a,b)

    def test_nonlinear_reverse_ancestor_DAG_matches_actual_expression_backend(self):
        mapping={'source_start':0.,'source_end':1.,'timeline_start':0.,'timeline_duration':.6931471805599453,
            'speed':1.,'reverse':True,'segments':[(0.,1.,1.,2.)],'curve_scale':1.}
        clip={'id':'curve','timeline_start_tick':0,'duration_tick':90000,
            '_nested_keyframe_clock':{'maps':[mapping],'authored_start':0.}}
        native=self.native(effect(easing='bezier'),clip=clip)[0]
        with patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'expression'}):reference=self.native(effect(easing='bezier'),clip=clip)[0]
        for a,b in zip(native,reference):self.compare(a,b)

    def test_odd_dimensions_stride_and_parallel_chunk_tail_match_independent_HLS(self):
        rng=random.Random(771)
        for width,height in [(17,13),(257,131)]:
            raw=bytes(rng.randrange(256) for _ in range(width*height*4));graph=self.bind({'type':'selective_hsl','parameters':{
                'red_hue':53,'orange_saturation':-.4,'cyan_lightness':.2,'magenta_hue':-21}})[0]
            result=subprocess.run([ffmpeg_path(),'-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
                '-video_size',f'{width}x{height}','-framerate','6','-i','pipe:0','-vf',graph+',format=rgba',
                '-frames:v','1','-f','rawvideo','-pix_fmt','rgba','pipe:1'],input=raw,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
            self.assertEqual(len(result.stdout),len(raw));self.compare(result.stdout,oracle_frame(raw,{
                'red_hue':53,'orange_saturation':-.4,'cyan_lightness':.2,'magenta_hue':-21}))

    def test_binary_tampering_rejects_auto_without_silent_fallback(self):
        fake=self.fake_package();(fake/MANIFEST['binary_filename']).write_bytes(b'changed')
        with patch.object(hsl_native,'__file__',str(fake/'hsl_native.py')),patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'auto'}):
            with self.assertRaises(AppError) as error:self.bind(effect())
        self.assertEqual(error.exception.code,'SELECTIVE_HSL_NATIVE_INTEGRITY')

    def test_source_tampering_rejects(self):
        fake=self.fake_package();(fake/'native_hsl.c').write_bytes(b'changed')
        with patch.object(hsl_native,'__file__',str(fake/'hsl_native.py')):
            with self.assertRaises(AppError) as error:self.bind(effect())
        self.assertEqual(error.exception.code,'SELECTIVE_HSL_NATIVE_INTEGRITY')

    def test_manifest_path_or_malformed_value_rejects_structurally(self):
        fake=self.fake_package()
        for name in ['../other.dll','https://example.invalid/file.dll',1,None]:
            (fake/'native_hsl_manifest.json').write_text(json.dumps({**MANIFEST,'binary_filename':name}),encoding='utf8')
            with patch.object(hsl_native,'__file__',str(fake/'hsl_native.py')):
                with self.assertRaises(AppError) as error:self.bind(effect())
            self.assertEqual(error.exception.code,'SELECTIVE_HSL_NATIVE_INTEGRITY')

    def test_missing_module_auto_falls_back_and_explicit_native_rejects(self):
        with patch.object(hsl_native,'__file__',str(self.root/'absent/hsl_native.py')):
            with self.assertRaises(AppError) as error:self.bind(effect())
            self.assertEqual(error.exception.code,'SELECTIVE_HSL_NATIVE_UNAVAILABLE')
            with patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'auto'}):
                _,metadata,_=self.bind(effect());self.assertEqual(metadata[0]['backend'],'ffmpeg:geq')
                self.assertIn('fallback_reason',metadata[0])

    def test_missing_local_filter_auto_falls_back_and_explicit_native_rejects(self):
        with patch.object(hsl_native,'_runtime_supported',return_value=False):
            with self.assertRaises(AppError):self.bind(effect())
            with patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'auto'}):
                self.assertEqual(self.bind(effect())[1][0]['fallback_reason'],'local-ffmpeg-without-frei0r')

    def test_explicit_expression_skips_native_loading_and_invalid_mode_rejects(self):
        with patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'expression'}),patch.object(hsl_native,'_runtime_supported',side_effect=AssertionError):
            self.assertEqual(self.bind(effect())[1][0]['backend'],'ffmpeg:geq')
        with patch.dict(os.environ,{'AI_AD_EDITOR_HSL_BACKEND':'bad'}):
            with self.assertRaises(AppError) as error:self.bind(effect())
        self.assertEqual(error.exception.code,'SELECTIVE_HSL_BACKEND_INVALID')

    def test_program_rejects_code_and_unsupported_AST(self):
        for text in ['__import__("os")','(1).__class__','t[0]','[t]','x','1e999','2**3','lambda:1']:
            with self.assertRaises(AppError):hsl_program.compile_program([text]*25)

    def test_program_count_size_and_depth_are_bounded(self):
        with self.assertRaises(AppError):hsl_program.compile_program(['1']*24)
        self.assertEqual(len(hsl_program.compile_program(['1']*25)[0]),128)
        with patch.object(hsl_program,'MAX_PROGRAM_BYTES',127):
            with self.assertRaises(AppError):hsl_program.compile_program(['1']*25)
        expression='t'
        for _ in range(130):expression='('+expression+'+1)'
        with self.assertRaises(AppError):hsl_program.compile_program([expression]*25)

    def test_native_validator_rejects_corrupt_layout_indices_opcodes_and_hex(self):
        lib=self.library();raw=self.program(red_hue=45);self.assertEqual(lib.avk_hsl_validate_program(raw.hex().encode()),1)
        bad=[b'',b'zz'*len(raw),raw.hex().encode()[:-2],b'0'*131074]
        for offset,value in [(0,0),(8,999999),(12,999999),(112,99)]:
            changed=bytearray(raw);struct.pack_into('<I',changed,offset,value);bad.append(changed.hex().encode())
        for child in [1,999999]:
            changed=bytearray(raw);struct.pack_into('<IIII',changed,128,2,child,0,0);bad.append(changed.hex().encode())
        deep=b'AVKHSL01'+struct.pack('<I25I',129,*([128]*25))+struct.pack('<IIII',0,0,0,0)
        deep+=b''.join(struct.pack('<IIII',6,i-1,0,0) for i in range(1,129));bad.append(deep.hex().encode())
        for index,text in enumerate(bad):
            with self.subTest(index=index):self.assertEqual(lib.avk_hsl_validate_program(text),0)

    def test_native_validator_rejects_nonfinite_constant(self):
        lib=self.library();raw=bytearray(self.program(red_hue=45));struct.pack_into('<d',raw,116,float('nan'))
        self.assertEqual(lib.avk_hsl_validate_program(raw.hex().encode()),0)

    def test_invalid_or_absent_program_is_identity_without_unsafe_memory_access(self):
        lib=self.library();instance=lib.f0r_construct(48,24);self.assertTrue(instance)
        try:
            source=ctypes.create_string_buffer(FRAME);output=ctypes.create_string_buffer(len(FRAME))
            for text in [None,b'not-a-program']:
                if text is not None:
                    value=ctypes.c_char_p(text);lib.f0r_set_param_value(instance,ctypes.byref(value),0)
                lib.f0r_update(instance,0,source,output);self.assertEqual(output.raw,FRAME)
        finally:lib.f0r_destruct(instance)

    def test_lazy_branch_does_not_evaluate_inactive_division_by_zero(self):
        lib=self.library();expressions=['0']*25;expressions[0]='if(lt(t,1),45,1/(t-t))';expressions[-1]='1'
        raw=hsl_program.compile_program(expressions)[0];instance=lib.f0r_construct(48,24)
        try:
            value=ctypes.c_char_p(raw.hex().encode());lib.f0r_set_param_value(instance,ctypes.byref(value),0)
            source=ctypes.create_string_buffer(FRAME);output=ctypes.create_string_buffer(len(FRAME))
            lib.f0r_update(instance,0,source,output);self.compare(output.raw,oracle_frame(FRAME,{'red_hue':45}))
            self.assertNotEqual(output.raw,FRAME)
        finally:lib.f0r_destruct(instance)

    def test_parallel_instances_and_repeated_clock_reset_have_no_shared_pixel_state(self):
        lib=self.library();width,height=256,128;raw=(FRAME*((width*height*4+len(FRAME)-1)//len(FRAME)))[:width*height*4]
        def run(hue):
            instance=lib.f0r_construct(width,height);self.assertTrue(instance)
            try:
                value=ctypes.c_char_p(self.program(red_hue=hue).hex().encode());lib.f0r_set_param_value(instance,ctypes.byref(value),0)
                source=ctypes.create_string_buffer(raw);output=ctypes.create_string_buffer(len(raw));results=[]
                for time in [0.,.5,0.]:lib.f0r_update(instance,time,source,output);results.append(output.raw)
                self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2]);return results[0]
            finally:lib.f0r_destruct(instance)
        with ThreadPoolExecutor(max_workers=3) as pool:outputs=list(pool.map(run,[30,-30,60]))
        for output,hue in zip(outputs,[30,-30,60]):self.compare(output,oracle_frame(raw,{'red_hue':hue}))

    def test_invalid_dimensions_reject_before_allocation(self):
        lib=self.library()
        for width,height in [(0,1),(1,0),(8193,8),(8,8193),(2**32-1,2**32-1)]:
            self.assertFalse(lib.f0r_construct(width,height))

    def test_content_addressed_library_matches_source_and_only_one_binary_ships(self):
        self.assertEqual('sha256:'+hashlib.sha256((PACKAGE/'native_hsl.c').read_bytes()).hexdigest(),MANIFEST['source_sha256'])
        self.assertEqual([p.name for p in PACKAGE.glob('avk_hsl_*.dll')],[MANIFEST['binary_filename']])


if __name__=='__main__':unittest.main()
