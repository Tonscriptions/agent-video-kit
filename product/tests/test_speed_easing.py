"""Encoded-frame and independent quadrature checks for authored speed easing."""
from __future__ import annotations

import bisect
import contextlib
from functools import lru_cache
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import unittest

from PIL import Image

import test_nested_time_mapping as fixtures
from ai_ad_editor.cli import main
from ai_ad_editor.render import _expr_arg, _speed_curve_segments, speed_curve_duration_seconds
from ai_ad_editor.time_mapping import compose_expression, curve_elapsed, make_map, map_time
from ai_ad_editor.utils import atomic_write_json

TPS, FPS, W, H = 90000, 24, 96, 64


def rate_at(x, mode, controls=(), speeds=(.6, 4.)):
    if mode == 'ease_in': y = x * x
    elif mode == 'ease_out': y = 1 - (1 - x) ** 2
    elif mode == 'ease_in_out': y = 2 * x * x if x < .5 else 1 - 2 * (1 - x) ** 2
    elif mode == 'bezier':
        x1, y1, x2, y2 = controls if len(controls) == 4 else (1/3, controls[0], 2/3, controls[1])
        lo, hi = 0., 1.
        for _ in range(48):
            u = (lo + hi) / 2
            bx = 3*(1-u)**2*u*x1 + 3*(1-u)*u*u*x2 + u**3
            if bx < x: lo = u
            else: hi = u
        u = (lo + hi) / 2
        y = 3*(1-u)**2*u*y1 + 3*(1-u)*u*u*y2 + u**3
    else: y = x
    return speeds[0] + (speeds[1] - speeds[0]) * y


@lru_cache(maxsize=64)
def reference_table(mode, controls=(), speeds=(.6, 4.)):
    # Composite Simpson quadrature in source coordinates; independent of the
    # product's Bezier subdivision and logarithmic remap segments.
    n = 8192
    values = [0.]
    for index in range(n):
        a, b = index/n, (index+1)/n
        values.append(values[-1] + (b-a)/6*(1/rate_at(a, mode, controls, speeds)
            + 4/rate_at((a+b)/2, mode, controls, speeds) + 1/rate_at(b, mode, controls, speeds)))
    return tuple(values)


def elapsed(x, span, mode, controls=(), speeds=(.6, 4.)):
    table = reference_table(mode, tuple(controls), tuple(speeds))
    at = max(0., min(1., x/span)) * (len(table)-1)
    index = min(len(table)-2, int(at))
    return span * (table[index] + (table[index+1]-table[index])*(at-index))


def undo(step, time):
    left, right, duration, reverse, mode, controls, speeds = step
    local = duration-time if reverse else time
    table = reference_table(mode, tuple(controls), tuple(speeds))
    target = max(0., min(table[-1], local/duration*table[-1]))
    index = max(0, min(len(table)-2, bisect.bisect_right(table, target)-1))
    fraction = (target-table[index])/(table[index+1]-table[index])
    return left+(right-left)*(index+fraction)/(len(table)-1)


class SpeedEasingTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.NestedTimeMappingTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.NestedTimeMappingTests.tearDownClass.__func__)
    setUp = fixtures.NestedTimeMappingTests.setUp
    call = fixtures.NestedTimeMappingTests.call

    def curve(self, span, mode, controls=(), speeds=(.6, 4.)):
        left = {'at_tick': 0, 'speed': speeds[0], 'interpolation': mode}
        if mode == 'bezier': left['control_points'] = list(controls)
        return {'keyframes': [left, {'at_tick': round(span*TPS), 'speed': speeds[1]}]}

    def case(self, mode, controls=(), *, reverse=False, nested=False, animated=False,
             second=False, trim=False, audio=False):
        src_in, src_out = (.25, 2.75) if trim else (0., 3.)
        span = src_out-src_in
        speeds = (.6, 4.)
        seconds = elapsed(span, span, mode, controls, speeds)
        duration = round(seconds*TPS)
        steps = [(src_in, src_out, duration/TPS, reverse, mode, controls, speeds)]
        leaf_sequence = 'child' if nested else 'seq_main'
        track = 'child_video_1' if nested else 'track_video_1'
        operations = [{'op': 'add_sequence', 'id': 'child', 'duration_tick': 3*TPS}] if nested else []
        leaf = {'op': 'append_clip', 'sequence_id': leaf_sequence, 'track_id': track, 'id': 'leaf',
                'asset_id': 'frames', 'source_in_tick': round(src_in*TPS), 'source_out_tick': round(src_out*TPS),
                'duration_tick': 3*TPS if nested else duration}
        if not nested: leaf.update(speed_curve=self.curve(span, mode, controls), reverse=reverse)
        if animated:
            leaf['transform'] = {'scale': .25}
            leaf['keyframes'] = [{'property': 'transform.scale', 'keyframes': [
                {'at_tick': 0, 'value': .25, 'interpolation': 'linear'},
                {'at_tick': 3*TPS, 'value': 1., 'interpolation': 'linear'}]}]
        operations.append(leaf)
        if audio:
            self.call('media', 'ingest', '--project', self.root, '--input', self.speech, '--asset-id', 'pulses')
            audio_track = 'child_audio' if nested else 'track_audio_1'
            if nested: operations.append({'op': 'add_track', 'sequence_id': 'child', 'track_id': audio_track, 'kind': 'audio'})
            operations.append({**leaf, 'asset_id': 'pulses', 'track_id': audio_track, 'id': 'sound'})
        if nested:
            target = 'middle' if second else 'seq_main'
            if second: operations.append({'op': 'add_sequence', 'id': target, 'duration_tick': duration})
            operations.append({'op': 'append_sequence_clip', 'sequence_id': target,
                'track_id': 'middle_video_1' if second else 'track_video_1', 'nested_sequence_id': 'child',
                'id': 'curve_parent', 'source_in_tick': 0, 'source_out_tick': 3*TPS,
                'duration_tick': duration, 'speed_curve': self.curve(3., mode, controls), 'reverse': reverse})
            if second:
                second_mode, second_controls, second_speeds = 'ease_out', (), (.8, 2.)
                outer_span = duration/TPS
                duration = round(elapsed(outer_span, outer_span, second_mode, (), second_speeds)*TPS)
                operations.append({'op': 'append_sequence_clip', 'sequence_id': 'seq_main', 'track_id': 'track_video_1',
                    'nested_sequence_id': 'middle', 'id': 'outer', 'source_in_tick': 0, 'source_out_tick': round(outer_span*TPS),
                    'duration_tick': duration, 'speed_curve': self.curve(outer_span, second_mode, (), second_speeds), 'reverse': True})
                steps.append((0., outer_span, duration/TPS, True, second_mode, second_controls, second_speeds))
        changes = self.base/'easing.json'
        changes.write_text(json.dumps({'operations': operations}), encoding='utf-8')
        self.call('timeline', 'compose', '--project', self.root, '--input', changes)
        project = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        project['sequences'][0]['duration_tick'] = duration
        atomic_write_json(self.root/'project.json', project)
        def authored():
            p = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
            raw = json.dumps({k:p[k] for k in ('assets','settings','sequences')}, sort_keys=True, separators=(',',':')).encode()
            return hashlib.sha256(raw).hexdigest(), hashlib.sha256((self.root/'rights-ledger.json').read_bytes()).hexdigest()
        original = authored()
        output = self.root/('renders/easing.mkv' if audio else 'renders/easing.mp4')
        options = ('--container','mkv','--audio-codec','pcm_s16le') if audio else ()
        result = self.call('render','--project',self.root,'--output',output,*options)
        self.assertEqual(original, authored())
        raw = subprocess.run(['ffmpeg','-v','error','-i',str(output),'-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
        frames = [Image.frombytes('RGB',(W,H),raw[i:i+W*H*3]) for i in range(0,len(raw),W*H*3)]
        self.assertGreater(len(frames),10)
        if not animated:
            errors=[]
            for index,image in enumerate(frames):
                source=index/FPS
                for step in reversed(steps): source=undo(step,source)
                expected=max(0,min(71,math.floor(source*FPS + 1e-6)))
                actual=sum(1<<bit for bit in range(7) if image.getpixel((bit*12+6,10))[0]>128)
                errors.append(abs(actual-expected))
            self.assertLessEqual(max(errors),1,f'Actual eased source frames drift: {errors}')
        return output, frames, steps, result

    def test_speed_easing_integrals_follow_authored_profiles(self):
        for mode, controls in [('ease_in',()),('ease_out',()),('ease_in_out',()),('bezier',(.05,.9)),('bezier',(.12,.02,.9,.3)),('bezier',(1.,0.,0.,1.))]:
            with self.subTest(mode=mode,controls=controls):
                curve={'speed_curve':self.curve(3.,mode,controls)}
                segments=_speed_curve_segments(curve,3*TPS,TPS)
                for at in (.1,.7,1.5,2.2,3.):
                    self.assertLessEqual(abs(curve_elapsed(segments,at)-elapsed(at,3.,mode,controls)),.00025)

    def test_speed_easing_compose_derives_real_duration(self):
        operations=[{'op':'append_clip','asset_id':'frames','id':'auto','track_id':'track_video_1',
            'source_in_tick':0,'source_out_tick':3*TPS,'speed_curve':self.curve(3.,'ease_in')}]
        changes=self.base/'auto.json';changes.write_text(json.dumps({'operations':operations}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',changes)
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        clip=project['sequences'][0]['tracks'][0]['clips'][0]
        self.assertLessEqual(abs(clip['duration_tick']/TPS-elapsed(3.,3.,'ease_in')),.00025+1/TPS)

    def test_speed_easing_direct_ease_in_encoded_frames(self): self.case('ease_in')
    def test_speed_easing_direct_ease_out_reverse_encoded_frames(self): self.case('ease_out',reverse=True)
    def test_speed_easing_direct_in_out_nonzero_source_trim(self): self.case('ease_in_out',trim=True)
    def test_speed_easing_two_control_bezier_encoded_frames(self): self.case('bezier',(.05,.9))
    def test_speed_easing_four_control_bezier_encoded_frames(self): self.case('bezier',(.12,.02,.9,.3))
    def test_speed_easing_two_parent_clocks_compose(self): self.case('bezier',(.12,.02,.9,.3),nested=True,reverse=True,second=True)

    def test_speed_easing_nested_bezier_keeps_original_animation_clock(self):
        _,frames,steps,result=self.case('bezier',(.12,.02,.9,.3),nested=True,animated=True)
        widths=[]
        for index,image in enumerate(frames):
            child=undo(steps[0],index/FPS)
            expected=W*(.25+.75*min(1.,max(0.,child/3.)))
            present=[x for x in range(W) if image.getpixel((x,H//2))[1]>35]
            self.assertTrue(present)
            widths.append(abs(max(present)-min(present)+1-expected))
        self.assertLessEqual(max(widths),3.,f'Authored Bezier clock drift: {widths}')
        self.assertFalse(any(w.get('feature')=='speed_curve_easing_linearized' for w in result['data']['warnings']))

    def test_speed_easing_audio_reverse_pulse_envelope(self):
        output,_,steps,result=self.case('ease_in',reverse=True,audio=True)
        import array
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
        samples=array.array('f');samples.frombytes(raw);checks=[]
        for index in range(0,len(samples)-960,960):
            at=(index+480)/48000
            if at>=steps[-1][2]:continue
            source=undo(steps[0],at)
            if min(abs(source-edge) for edge in (.6,.9,1.8,2.1))<.1:continue
            rms=math.sqrt(sum(float(s)**2 for s in samples[index:index+960])/960)
            checks.append((rms>.15)==(.6<=source<.9 or 1.8<=source<2.1))
        self.assertGreater(len(checks),15);self.assertTrue(all(checks),checks)
        self.assertTrue(any(w.get('feature')=='audio_speed_curve_piecewise' for w in result['data']['warnings']))

    def reject_curve(self, point, tail=None):
        before=(self.root/'project.json').read_bytes(),(self.root/'rights-ledger.json').read_bytes()
        change=self.base/'bad.json';change.write_text(json.dumps({'operations':[{'op':'append_clip','asset_id':'frames',
            'id':'bad','track_id':'track_video_1','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS,
            'speed_curve':{'keyframes':[point,*(tail if tail is not None else [{'at_tick':3*TPS,'speed':2.}])]}}]}),encoding='utf-8')
        captured=io.StringIO()
        with contextlib.redirect_stdout(captured): code=main(['timeline','compose','--project',str(self.root),'--input',str(change)])
        response=json.loads(captured.getvalue())
        self.assertNotEqual(code,0,response)
        self.assertEqual(before,((self.root/'project.json').read_bytes(),(self.root/'rights-ledger.json').read_bytes()))
        return response

    def test_speed_easing_invalid_bezier_controls_roll_back(self):
        for controls in (None,[.2],[False,.3],[1.2,.1,.8,.9],[.2,float('inf')]):
            point={'at_tick':0,'speed':1.,'interpolation':'bezier'}
            if controls is not None:point['control_points']=controls
            with self.subTest(controls=controls):self.reject_curve(point)

    def test_speed_easing_nonpositive_bezier_interior_is_rejected(self):
        self.reject_curve({'at_tick':0,'speed':1.,'interpolation':'bezier','control_points':[.2,-5.,.8,-5.]})

    def test_speed_easing_segment_budget_rejects_without_project_changes(self):
        self.reject_curve({'at_tick':0,'speed':1.,'interpolation':'linear'},
            [{'at_tick':i*200,'speed':1.+(i%2),'interpolation':'linear'} for i in range(1,1100)])

    def test_speed_easing_positive_bezier_overshoot_is_preserved(self):
        controls=(1.4,1.2)
        clip={'speed_curve':self.curve(3.,'bezier',controls,speeds=(1.,2.))}
        got=speed_curve_duration_seconds(clip,3*TPS,TPS)
        self.assertLessEqual(abs(got-elapsed(3.,3.,'bezier',controls,(1.,2.))),.00025)

    def test_speed_easing_compilation_reports_error_bound_and_budget(self):
        segments=_speed_curve_segments({'speed_curve':self.curve(3.,'ease_in')},3*TPS,TPS)
        certificate=getattr(segments,'certificate',{})
        self.assertTrue(certificate.get('adaptive'))
        self.assertLessEqual(certificate['source_clock_error_bound_seconds'],.00025)
        self.assertLessEqual(certificate['segment_count'],1024)
        mapping=make_map({'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':2*TPS},segments,TPS)
        bound=mapping['curve_compilation']['normalized_clock_error_bound_seconds']
        errors=[abs(map_time(mapping,at/10)-2*elapsed(at/10,3.,'ease_in')/elapsed(3.,3.,'ease_in')) for at in range(31)]
        self.assertLessEqual(max(errors),bound)

    def test_speed_easing_legacy_hold_linear_duration_control(self):
        curve={'speed_curve':{'keyframes':[{'at_tick':0,'speed':1.,'interpolation':'hold'},
            {'at_tick':TPS,'speed':2.,'interpolation':'linear'},{'at_tick':3*TPS,'speed':4.}]}}
        self.assertAlmostEqual(speed_curve_duration_seconds(curve,3*TPS,TPS),1+math.log(2),places=9)

    def test_speed_easing_nearly_constant_clock_bound_and_ffmpeg_pts(self):
        import re
        span=10000.;a=.01;b=a+4e-9
        clip={'source_in_tick':0,'source_out_tick':round(span*TPS),'duration_tick':TPS,
              'speed_curve':self.curve(span,'ease_in',speeds=(a,b))}
        segments=_speed_curve_segments(clip,round(span*TPS),TPS)
        def oracle(source):
            z=math.sqrt((b-a)/a)*source/span
            return source/a*(math.atan(z)/z if z else 1.)
        bound=getattr(segments,'certificate',{}).get('source_clock_error_bound_seconds',.00025)
        self.assertLessEqual(abs(curve_elapsed(segments,span)-oracle(span)),bound+1e-9)
        mapping=make_map(clip,segments,TPS);mapping['curve_scale']=1.
        expression=compose_expression([mapping],'N*5000')
        video_filter='settb=expr=1/90000,setpts='+_expr_arg('('+expression+')/TB')+',showinfo'
        completed=subprocess.run(['ffmpeg','-v','info','-f','lavfi','-i','color=size=16x16:rate=1:duration=3',
            '-vf',video_filter,'-frames:v','3','-fps_mode','passthrough','-f','null','-'],capture_output=True,check=True)
        pts=[int(v) for v in re.findall(rb'\bn:\s*\d+\s+pts:\s*(-?\d+)',completed.stderr)]
        self.assertEqual(len(pts),3,completed.stderr.decode('utf-8','replace'))
        self.assertLessEqual(max(abs(t/TPS-oracle(i*5000)) for i,t in enumerate(pts)),bound+1/TPS)
