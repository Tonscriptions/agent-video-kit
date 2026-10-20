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


if __name__=='__main__':unittest.main()
