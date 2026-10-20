from __future__ import annotations
import contextlib
import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
from PIL import Image
from ai_ad_editor import html_shutter as shutter,html_motion as html
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project,load_project
from ai_ad_editor.utils import atomic_write_json
from test_html_motion import cli,spec,TPS


def png(size,pixels):
    image=Image.frombytes('RGBA',size,bytes(pixels));data=io.BytesIO();image.save(data,format='PNG');return data.getvalue()


def half_up(n,d):return (2*n+d)//(2*d)


def independent_pixels(frames):
    result=bytearray();count=len(frames)
    for i in range(0,len(frames[0]),4):
        alpha=sum(f[i+3] for f in frames)
        result.extend([half_up(sum(f[i+c]*f[i+3] for f in frames),alpha) if alpha else 0 for c in range(3)])
        result.append(half_up(alpha,count))
    return bytes(result)


class ShutterMathTests(unittest.TestCase):
    def config(self,**kwargs):return shutter.configuration(duration_tick=TPS,**kwargs)

    def reject(self,fn,*args,**kwargs):
        with self.assertRaises(AppError) as caught:fn(*args,**kwargs)
        self.assertEqual(caught.exception.code,'HTML_SHUTTER_INVALID')

    def test_recipe_is_explicit_inherited_and_copied(self):
        original=self.config(samples=8,cut_ticks=[10000,45000]);saved=copy.deepcopy(original)
        changed=self.config(saved=original,fraction=.75);self.assertEqual(changed['samples'],8)
        changed['cut_ticks'].append(80000);self.assertEqual(original,saved)
        self.assertEqual(self.config(saved=original,clear_cuts=True)['cut_ticks'],[])

    def test_invalid_fields_and_numbers_reject_without_coercion(self):
        for value in [True,0,17,1.5,'8']:
            self.reject(self.config,samples=value)
        for value in [True,float('nan'),float('inf'),-.1,1.01,'0.5']:
            self.reject(self.config,fraction=value)
        wrong=self.config();wrong['unknown']=1;self.reject(self.config,saved=wrong)
        wrong=self.config();wrong['version']=True;self.reject(self.config,saved=wrong)

    def test_cut_order_range_duplicates_and_clear_are_validated(self):
        for cuts in [[0],[TPS],[-1],[20,10],[10,10],[True],list(range(1,258))]:
            self.reject(self.config,cut_ticks=cuts)
        self.reject(self.config,cut_ticks=[10],clear_cuts=True)

    def test_actual_redraw_and_layout_passes_are_in_budget(self):
        small=shutter.profile(spec(),4,self.config(samples=8),layout_check='strict')
        self.assertEqual(small['capture_count'],32);self.assertEqual(small['work_pixels'],96*64*32*5)
        with self.assertRaises(AppError) as caught:
            shutter.profile(spec(width=1920,height=1080),60,self.config(samples=8))
        self.assertEqual(caught.exception.code,'HTML_SHUTTER_BUDGET')

    def test_single_sample_and_zero_exposure_use_original_frame_times(self):
        for config in [self.config(),self.config(samples=16,fraction=0)]:
            profile=shutter.profile(spec(),4,config)
            self.assertFalse(profile['enabled']);self.assertEqual(profile['capture_count'],4)
            rows=shutter.schedule(spec(),TPS,profile)
            self.assertEqual([r['worker_time_seconds'] for r in rows],[0,.25,.5,.75])

    def test_interior_midpoint_exposure_has_exact_zero_mean_bias(self):
        profile=shutter.profile(spec(),4,self.config(samples=8))
        rows=[r for r in shutter.schedule(spec(),TPS,profile) if r['output_frame']==2]
        self.assertEqual(sum(Fraction(r['requested_seconds_rational']) for r in rows)/8,Fraction(1,2))
        self.assertTrue(all(not r['clamped'] for r in rows))

    def test_source_start_clamps_and_cut_uses_anchor_segment(self):
        profile=shutter.profile(spec(),4,self.config(samples=4,fraction=1,cut_ticks=[44100]))
        rows=shutter.schedule(spec(),TPS,profile)
        self.assertEqual([r['worker_time_seconds'] for r in rows[:2]],[0,0])
        for row in rows:
            t=row['worker_time_seconds'];self.assertGreaterEqual(t,float(Fraction(row['segment_start_rational'])))
            self.assertLess(t,float(Fraction(row['segment_end_rational'])))
        self.assertTrue(all(r['worker_time_seconds']>=.49 for r in rows if r['output_frame']==2))

    def test_rational_fps_retains_intended_and_actual_binary64_clocks(self):
        value=spec(fps={'num':30000,'den':1001},duration_tick=12012)
        config=shutter.configuration(samples=3,duration_tick=12012)
        rows=shutter.schedule(value,TPS,shutter.profile(value,4,config))
        for row in rows:
            self.assertEqual(Fraction(row['worker_time_binary64_rational']),Fraction.from_float(row['worker_time_seconds']))
            self.assertLess(abs(float(Fraction(row['clamped_seconds_rational']))-row['worker_time_seconds']),1e-14)

    def test_hidden_transparent_color_cannot_pollute_premultiplied_result(self):
        accumulator=shutter.AlphaAccumulator((1,1),2)
        accumulator.push(png((1,1),[255,0,0,255]));accumulator.push(png((1,1),[0,0,255,0]))
        output,metrics=accumulator.finish()
        with Image.open(io.BytesIO(output)) as image:self.assertEqual(image.getpixel((0,0)),(255,0,0,128))
        self.assertEqual(metrics['alpha_extrema'],[128,128])

    def test_all_transparent_hidden_rgb_is_zero(self):
        accumulator=shutter.AlphaAccumulator((1,1),3)
        for rgb in [[255,0,0,0],[0,255,0,0],[0,0,255,0]]:accumulator.push(png((1,1),rgb))
        output,_=accumulator.finish()
        with Image.open(io.BytesIO(output)) as image:self.assertEqual(image.getpixel((0,0)),(0,0,0,0))

    def test_native_integer_kernel_matches_independent_whole_pixel_reference(self):
        rng=random.Random(20261020);size=(17,5)
        for count in [2,3,8,16]:
            frames=[bytes(rng.randrange(256) for _ in range(size[0]*size[1]*4)) for _ in range(count)]
            accumulator=shutter.AlphaAccumulator(size,count)
            for frame in frames:accumulator.push(png(size,frame))
            output,metrics=accumulator.finish()
            with Image.open(io.BytesIO(output)) as image:actual=image.convert('RGBA').tobytes()
            self.assertEqual(actual,independent_pixels(frames),count)
            self.assertEqual(metrics['rgba_sha256'],'sha256:'+hashlib.sha256(actual).hexdigest())

    def test_count_and_dimensions_cannot_produce_partial_average(self):
        accumulator=shutter.AlphaAccumulator((1,1),2);accumulator.push(png((1,1),[1,2,3,4]))
        self.reject(accumulator.finish);self.reject(accumulator.push,png((2,1),[1,2,3,4]*2))
        accumulator.push(png((1,1),[1,2,3,4]));self.reject(accumulator.push,png((1,1),[1,2,3,4]))

    def test_implementation_digest_rechecks_actual_bytes_not_mtime(self):
        with tempfile.TemporaryDirectory(prefix='shutter-binding-') as folder:
            path=Path(folder)/'native.bin';path.write_bytes(b'original');stat=path.stat()
            expected={'files':[{'path':str(path),'sha256':'sha256:'+hashlib.sha256(b'original').hexdigest()}]}
            shutter.verify_implementation(expected);path.write_bytes(b'mutated!');os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            with self.assertRaises(AppError) as caught:shutter.verify_implementation(expected)
            self.assertEqual(caught.exception.code,'HTML_SHUTTER_RUNTIME_CHANGED')


@unittest.skipUnless(os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'),'explicit existing native HTML toolchain not configured')
class ShutterNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configuration=json.loads(Path(os.environ['AI_AD_EDITOR_TEST_HTML_RUNTIME']).read_text(encoding='utf8'))
        cls.runtime=html.prepare_runtime(Path.cwd(),configuration)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='shutter-native-');self.addCleanup(self.temp.cleanup)
        self.root,self.project=create_project(Path(self.temp.name)/'project')
        atomic_write_json(self.root/'config/html-motion-runtime.json',self.runtime)
        self.source=Path(self.temp.name)/'source';self.source.mkdir()

    def source_asset(self,body=None,manifest=None):
        body=body or "ctx.clearRect(0,0,64,32);ctx.fillStyle='red';ctx.fillRect(4+Math.floor(t*32),8,4,8);ctx.fillStyle='rgba(0,255,0,0.5)';ctx.fillRect(48,8,8,8);"
        page="<!doctype html><style>*{margin:0}body{background:transparent}</style><canvas id='canvas' width='64' height='32'></canvas><script>const ctx=canvas.getContext('2d');window.film={frame(t){"+body+"}};</script>"
        (self.source/'index.html').write_text(page,encoding='utf8')
        atomic_write_json(self.source/'manifest.json',manifest or spec(width=64,height=32))
        code,result=cli('motion','html-source','--project',self.root,'--input',self.source/'manifest.json',
            '--asset-id','source','--creator','local-test','--license-spdx','CC0-1.0')
        self.assertEqual(code,0,result)

    def dom_asset(self,*,fail_between=False):
        extra="if(t>0&&t<.2)throw new Error('subframe-only-failure');" if fail_between else ''
        page="<!doctype html><style>*{margin:0}body{background:transparent}#moving{position:absolute;top:8px;width:4px;height:8px;background:red}</style><div id='moving'></div><script>window.film={frame(t){"+extra+"moving.style.left=(4+Math.floor(t*32))+'px'}};</script>"
        (self.source/'index.html').write_text(page,encoding='utf8')
        atomic_write_json(self.source/'manifest.json',spec(width=64,height=32))
        code,result=cli('motion','html-source','--project',self.root,'--input',self.source/'manifest.json','--asset-id','source')
        self.assertEqual(code,0,result)

    def render(self,name,*extra,previous=None):
        source=('--from-asset-id',previous) if previous else ('--source-asset-id','source')
        return cli('motion','html-render','--project',self.root,*source,'--asset-id',name,*extra)

    def report(self,result):
        path=result.get('data',{}).get('report') or result['errors'][0]['path']
        record=json.loads(Path(path).read_text(encoding='utf8'))
        self.assertTrue(record['cleanup']['all_children_reaped'],record)
        self.assertEqual(record['cleanup']['active_after_cleanup'],[])
        if record.get('status')=='succeeded':self.assertTrue(record['worker']['cleanup']['browser_closed'])
        return record

    def decode(self,result):
        path=self.root/result['data']['asset']['uri']
        return subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(path),'-an','-f','rawvideo','-pix_fmt','rgba','pipe:1'])

    def rectangle(self,x):
        data=bytearray(64*32*4)
        for y in range(8,16):
            for at in range(x,x+4):data[(y*64+at)*4:(y*64+at)*4+4]=bytes((255,0,0,255))
            for at in range(48,56):data[(y*64+at)*4:(y*64+at)*4+4]=bytes((0,255,0,128))
        return bytes(data)

    def test_real_subframe_pixels_match_precomputed_positions_and_independent_alpha(self):
        self.source_asset();code,result=self.render('blur','--shutter-samples','4','--shutter-fraction','1')
        self.assertEqual(code,0,result);report=self.report(result);actual=self.decode(result)
        # Fixed source pixel positions computed independently of product schedule.
        positions=[[4,4,5,7],[9,11,13,15],[17,19,21,23],[25,27,29,31]]
        expected=b''.join(independent_pixels([self.rectangle(x) for x in group]) for group in positions)
        self.assertEqual(actual,expected)
        self.assertEqual(report['encoded_clock']['frame_count'],4)
        self.assertTrue(report['encoded_clock']['all_frames_exact'])
        self.assertEqual(len(report['worker']['frame_hashes']),16)
        self.assertTrue(all(len(v['frames'])==16 for v in report['worker']['verification']))
        self.assertEqual(report['worker']['cleanup']['pages_closed'],3)
        self.assertEqual([r['samples'] for r in report['shutter_evidence']['encoded_frames']],[4]*4)

    def test_default_and_zero_exposure_keep_exact_cfr_pixels(self):
        self.source_asset();a,plain=self.render('plain');b,zero=self.render('zero','--shutter-samples','16','--shutter-fraction','0')
        self.assertEqual(a,0,plain);self.assertEqual(b,0,zero)
        expected=b''.join(self.rectangle(x) for x in [4,12,20,28])
        self.assertEqual(self.decode(plain),expected);self.assertEqual(self.decode(zero),expected)
        self.assertEqual(self.report(zero)['shutter_evidence']['source_capture_count'],4)
        self.assertEqual(self.report(plain)['worker']['frame_hashes'],self.report(zero)['worker']['frame_hashes'])

    def test_cut_stops_scene_ghost_and_saved_recipe_replays_or_clears_explicitly(self):
        self.source_asset("ctx.fillStyle=t<0.49?'red':'blue';ctx.fillRect(0,0,64,32);")
        code,first=self.render('cut','--shutter-samples','4','--shutter-fraction','1','--shutter-cut-tick','44100')
        self.assertEqual(code,0,first);code,replay=self.render('replay',previous='cut');self.assertEqual(code,0,replay)
        self.assertEqual(self.decode(first),self.decode(replay));self.report(first);self.report(replay)
        raw=self.decode(first);stride=64*32*4
        self.assertEqual(raw[2*stride:3*stride],bytes((0,0,255,255))*(64*32))
        self.assertEqual(replay['data']['asset']['html_motion']['shutter'],first['data']['asset']['html_motion']['shutter'])
        code,clear=self.render('clear','--shutter-clear-cuts',previous='cut');self.assertEqual(code,0,clear);self.report(clear)
        raw=self.decode(clear);self.assertEqual(raw[2*stride:3*stride],bytes((128,0,128,255))*(64*32))
        self.assertEqual(clear['data']['asset']['html_motion']['shutter']['cut_ticks'],[])

    def test_strict_layout_gate_covers_every_actual_subframe(self):
        self.dom_asset();code,result=self.render('strict','--shutter-samples','4','--shutter-fraction','1','--layout-check','strict')
        self.assertEqual(code,0,result);self.report(result)
        quality=json.loads(Path(result['data']['layout_report']).read_text(encoding='utf8'))
        self.assertEqual(quality['frame_count'],16)
        self.assertEqual(quality['worker']['cleanup']['pages_closed'],2)
        self.assertTrue(quality['cleanup']['all_children_reaped'])
        self.assertEqual(result['data']['asset']['html_motion']['layout_evidence']['sampling_scope'],'actual_shutter_subframes')
        self.assertEqual([r['sampling']['capture_index'] for r in quality['frames']],list(range(16)))

    def test_failure_between_output_anchors_is_seen_before_encoding(self):
        self.dom_asset(fail_between=True)
        code,plain=self.render('plain','--layout-check','strict');self.assertEqual(code,0,plain);self.report(plain)
        before=(self.root/'project.json').read_bytes()
        code,result=self.render('rejected','--layout-check','strict','--shutter-samples','4','--shutter-fraction','1')
        self.assertEqual(code,6,result);self.assertIn('subframe-only-failure',json.dumps(result))
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.report(result)
        self.assertNotIn('rejected',[a['id'] for a in load_project(self.root)[1]['assets']])

    def test_canvas_layout_remains_explicitly_unverified_with_subframes(self):
        self.source_asset();before=(self.root/'project.json').read_bytes()
        code,result=self.render('canvas','--shutter-samples','4','--layout-check','strict')
        self.assertEqual(code,2,result);self.assertEqual(result['errors'][0]['code'],'HTML_QUALITY_FAILED')
        report=self.report(result)
        self.assertTrue(any(x.get('kind')=='canvas-or-SVG-semantic-text' for x in report['issues']))
        self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_real_cancel_after_one_blended_frame_cleans_owned_browser_and_encoder(self):
        self.source_asset("if(t>.1){while(true){}}ctx.clearRect(0,0,64,32);ctx.fillStyle='red';ctx.fillRect(0,0,8,8);")
        before=(self.root/'project.json').read_bytes();flag=self.root/'cancel.flag';ready=threading.Event()
        def cancel():
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                for path in (self.root/'validation').glob('html-motion-*.json'):
                    try:progress=json.loads(path.read_text(encoding='utf8')).get('progress',{})
                    except (OSError,ValueError):continue
                    if progress.get('encoded_output_frames',0)>=1:flag.touch();ready.set();return
                time.sleep(.03)
        thread=threading.Thread(target=cancel,daemon=True);thread.start()
        code,result=self.render('cancelled','--shutter-samples','4','--shutter-fraction','1',
            '--cancel-file',flag,'--timeout-seconds','30');thread.join(timeout=1)
        self.assertTrue(ready.is_set(),'actual first blended frame must precede cancellation')
        self.assertEqual(code,8,result);self.assertEqual((self.root/'project.json').read_bytes(),before)
        report=self.report(result);self.assertGreaterEqual(report['progress']['encoded_output_frames'],1)
        self.assertEqual(report['status'],'failed')

    def test_invalid_sampling_and_total_work_reject_before_browser(self):
        self.source_asset(manifest=spec(width=1920,height=1080,duration_tick=TPS*15))
        before=(self.root/'project.json').read_bytes()
        with mock.patch('ai_ad_editor.html_motion.BrowserProcessJob',side_effect=AssertionError('browser started')):
            code,result=self.render('budget','--shutter-samples','8')
            self.assertEqual(code,2,result);self.assertEqual(result['errors'][0]['code'],'HTML_SHUTTER_BUDGET')
            code,result=self.render('nan','--shutter-fraction','nan')
            self.assertEqual(code,2,result);self.assertEqual(result['errors'][0]['code'],'HTML_SHUTTER_INVALID')
        self.assertEqual((self.root/'project.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
