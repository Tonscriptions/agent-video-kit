from __future__ import annotations

import array
import bisect
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

from PIL import Image, ImageDraw

from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json


TPS = 90000
FPS = 24
WIDTH, HEIGHT = 96, 64


def elapsed(source, span, speeds):
    """Independent closed-form oracle for the one-ramp authored fixtures."""
    left, right = speeds
    if abs(right - left) < 1e-12:
        return source / left
    slope = (right - left) / span
    return math.log1p(slope * source / left) / slope


def mapped(step, source):
    local = source - step['in']
    span = step['out'] - step['in']
    def integral(value):
        total = 0.
        for left, right, rates in step.get('pieces', [(0., span, step['speeds'])]):
            total += elapsed(max(0., min(value, right) - left), right - left, rates)
        return total
    value = integral(local)
    value *= step['duration'] / integral(span)
    return step['start'] + (step['duration'] - value if step['reverse'] else value)


def unmapped(step, output):
    value = output - step['start']
    if step['reverse']:
        value = step['duration'] - value
    span = step['out'] - step['in']
    value *= elapsed(span, span, step['speeds']) / step['duration']
    left, right = step['speeds']
    slope = (right - left) / span
    return step['in'] + (value * left if abs(slope) < 1e-12 else left * math.expm1(slope * value) / slope)


class NestedTimeMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.fixture = tempfile.TemporaryDirectory(prefix='nested-clock-source-')
        cls.fixture_root = Path(cls.fixture.name)
        cls.source = cls.fixture_root / 'source.mp4'
        frames = []
        for index in range(72):
            image = Image.new('RGB', (WIDTH, HEIGHT), (60, 90, 120))
            draw = ImageDraw.Draw(image)
            for bit in range(7):
                level = 240 if index & (1 << bit) else 16
                draw.rectangle((bit * 12, 0, bit * 12 + 11, 19), fill=(level,) * 3)
            frames.append(image.tobytes())
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}',
                        '-r', str(FPS), '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p',
                        str(cls.source)], input=b''.join(frames), capture_output=True, check=True)
        cls.speech = cls.fixture_root / 'pulses.wav'
        samples = array.array('h')
        for index in range(3 * 48000):
            at = index / 48000
            amplitude = .6 if .6 <= at < .9 or 1.8 <= at < 2.1 else .03
            sample = int(32767 * amplitude * math.sin(2 * math.pi * 400 * at))
            samples.extend((sample, sample))
        with wave.open(str(cls.speech), 'wb') as handle:
            handle.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            handle.writeframes(samples.tobytes())

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nested-clock-project-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.call('project', 'init', self.root)
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8-sig'))
        project['settings']['canvas'].update(width=WIDTH, height=HEIGHT)
        project['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        atomic_write_json(self.root / 'project.json', project)
        self.call('media', 'ingest', '--project', self.root, '--input', self.source, '--asset-id', 'frames')

    def call(self, *args):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            code = main(list(map(str, args)))
        value = json.loads(capture.getvalue())
        self.assertEqual(code, 0, value)
        return value

    def render_case(self, parents, *, leaf_speeds=(1., 1.), leaf_reverse=False,
                    source_in=0., source_out=3., animated=False, mask_animated=False, audio=False, output_fps=FPS):
        span = source_out - source_in
        leaf_duration = round(elapsed(span, span, leaf_speeds) * TPS)
        steps = [{'in': source_in, 'out': source_out, 'start': 0., 'duration': leaf_duration / TPS,
                  'speeds': leaf_speeds, 'reverse': leaf_reverse}]
        leaf = {'op': 'append_clip', 'sequence_id': 'child_0', 'track_id': 'child_0_video_1', 'id': 'leaf',
                'asset_id': 'frames', 'source_in_tick': round(source_in * TPS), 'source_out_tick': round(source_out * TPS),
                'duration_tick': leaf_duration, 'reverse': leaf_reverse}
        if leaf_speeds != (1., 1.):
            leaf['speed_curve'] = {'keyframes': [{'at_tick': 0, 'speed': leaf_speeds[0]},
                {'at_tick': round(span * TPS), 'speed': leaf_speeds[1]}]}
        if animated:
            leaf['transform'] = {'scale': .4}
            leaf['keyframes'] = [{'property': 'transform.scale', 'keyframes': [
                {'at_tick': 0, 'value': .4, 'interpolation': 'linear'},
                {'at_tick': leaf_duration, 'value': .9, 'interpolation': 'linear'}]}]
        if mask_animated:
            leaf['mask'] = {'type': 'rectangle', 'x': 0., 'y': 0., 'width': .4, 'height': 1., 'keyframes': [
                {'property': 'width', 'keyframes': [{'at_tick': 0, 'value': .4, 'interpolation': 'linear'},
                                                  {'at_tick': leaf_duration, 'value': .9, 'interpolation': 'linear'}]}]}
        operations = [{'op': 'add_sequence', 'id': 'child_0', 'duration_tick': leaf_duration}, leaf]
        if audio:
            self.call('media', 'ingest', '--project', self.root, '--input', self.speech, '--asset-id', 'pulses')
            operations += [{'op': 'add_track', 'sequence_id': 'child_0', 'track_id': 'child_audio', 'kind': 'audio', 'order': 1},
                           {**leaf, 'track_id': 'child_audio', 'id': 'audio_leaf', 'asset_id': 'pulses'}]
        current = 'child_0'
        current_duration = leaf_duration
        for index, config in enumerate(parents):
            target = 'seq_main' if index == len(parents) - 1 else f'child_{index + 1}'
            left = int(round(config.get('in', 0.) * TPS))
            right = int(round(config.get('out', current_duration / TPS) * TPS))
            speeds = tuple(config.get('speeds', (1., 1.)))
            pieces = []
            points = config.get('points')
            if points:
                for a, b in zip(points, points[1:]):
                    pieces.append((a[0], b[0], (a[1], a[1] if a[2] == 'hold' else b[1])))
                duration = round(sum(elapsed(b - a, b - a, rates) for a, b, rates in pieces) * TPS)
            else:
                duration = round(elapsed((right - left) / TPS, (right - left) / TPS, speeds) * TPS)
            start = int(round(config.get('start', 0.) * TPS))
            reverse = bool(config.get('reverse', False))
            steps.append({'in': left / TPS, 'out': right / TPS, 'start': start / TPS,
                          'duration': duration / TPS, 'speeds': speeds, 'reverse': reverse})
            if pieces:
                steps[-1]['pieces'] = pieces
            if target != 'seq_main':
                operations.append({'op': 'add_sequence', 'id': target, 'duration_tick': start + duration})
            clip = {'op': 'append_sequence_clip', 'sequence_id': target,
                    'track_id': 'track_video_1' if target == 'seq_main' else target + '_video_1',
                    'nested_sequence_id': current, 'id': f'parent_{index}', 'source_in_tick': left,
                    'source_out_tick': right, 'duration_tick': duration, 'timeline_start_tick': start, 'reverse': reverse}
            if speeds != (1., 1.):
                clip['speed_curve'] = {'keyframes': [{'at_tick': 0, 'speed': speeds[0]},
                                                    {'at_tick': right - left, 'speed': speeds[1]}]}
            if points:
                clip['speed_curve'] = {'keyframes': [{'at_tick': round(at * TPS), 'speed': rate, 'interpolation': interpolation}
                                                    for at, rate, interpolation in points]}
            if config.get('animate'):
                clip['transform'] = {'scale': .4}
                clip['keyframes'] = [{'property': 'transform.scale', 'keyframes': [
                    {'at_tick': 0, 'value': .4, 'interpolation': 'linear'},
                    {'at_tick': duration, 'value': .9, 'interpolation': 'linear'}]}]
            operations.append(clip)
            current, current_duration = target, start + duration
        changes = self.base / 'changes.json'
        changes.write_text(json.dumps({'operations': operations}), encoding='utf-8')
        self.call('timeline', 'compose', '--project', self.root, '--input', changes)
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8-sig'))
        project['sequences'][0]['duration_tick'] = current_duration
        project['settings']['timebase']['display_fps'] = {'num': output_fps, 'den': 1}
        atomic_write_json(self.root / 'project.json', project)
        output = self.root / ('renders/case.mkv' if audio else 'renders/case.mp4')
        options = ('--container', 'mkv', '--audio-codec', 'pcm_s16le') if audio else ()
        def authored_hashes():
            value = json.loads((self.root / 'project.json').read_text(encoding='utf-8-sig'))
            authored = json.dumps({key: value[key] for key in ['assets', 'settings', 'sequences']},
                                  ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
            return {'authored_project': hashlib.sha256(authored).hexdigest(),
                    'rights_ledger': hashlib.sha256((self.root / 'rights-ledger.json').read_bytes()).hexdigest()}
        originals = authored_hashes()
        result = self.call('render', '--project', self.root, '--output', output, *options)
        self.assertEqual(originals, authored_hashes())
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-map', '0:v:0', '-an',
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True).stdout
        images = [Image.frombytes('RGB', (WIDTH, HEIGHT), raw[pos:pos + WIDTH * HEIGHT * 3])
                  for pos in range(0, len(raw), WIDTH * HEIGHT * 3)]
        return output, images, steps, result

    def assert_source_clock(self, parents, **kwargs):
        _, images, steps, _ = self.render_case(parents, **kwargs)
        reverse = sum(step['reverse'] for step in steps) % 2
        candidates = []
        for index in range(72):
            clock = (index + reverse) / FPS
            for step in steps:
                if clock < step['in'] - 1e-8 or clock > step['out'] + 1e-8:
                    break
                clock = mapped(step, clock)
            else:
                candidates.append((clock, index))
        candidates.sort()
        self.assertGreater(len(candidates), 10)
        clocks = [item[0] for item in candidates]
        errors = []
        for frame, image in enumerate(images):
            observed = sum(1 << bit for bit in range(7) if image.getpixel((bit * 12 + 6, 8))[0] > 128)
            position = max(0, bisect.bisect_right(clocks, frame / kwargs.get('output_fps', FPS) + 2e-5) - 1)
            expected = candidates[position][1]
            errors.append(abs(observed - expected))
        self.assertGreater(len(images), 10)
        self.assertLessEqual(max(errors), 1, f'Nested source-frame drift: {errors}')

    def test_nested_clock_forward_ramp_matches_source_frames(self):
        self.assert_source_clock([{'speeds': (1., 4.)}])

    def test_nested_clock_reverse_ramp_matches_source_frames(self):
        self.assert_source_clock([{'speeds': (1., 4.), 'reverse': True}])

    def test_nested_clock_two_nonlinear_parents_compose(self):
        self.assert_source_clock([{'speeds': (1., 3.)}, {'speeds': (.7, 1.8)}])

    def test_nested_clock_inner_reverse_preserves_outer_curve(self):
        self.assert_source_clock([{'speeds': (1., 3.), 'reverse': True}, {'speeds': (.7, 1.8)}])

    def test_nested_clock_double_reverse_does_not_cancel_wrong_clock(self):
        self.assert_source_clock([{'speeds': (1., 3.), 'reverse': True}, {'speeds': (.7, 1.8), 'reverse': True}])

    def test_nested_clock_trimmed_leaf_curve_keeps_original_source_domain(self):
        self.assert_source_clock([{'in': .2, 'out': .95, 'speeds': (.8, 1.7)}],
                                 leaf_speeds=(1., 3.), leaf_reverse=True, source_in=.25, source_out=2.75)

    def test_nested_clock_transform_animation_uses_authored_child_clock(self):
        _, images, steps, _ = self.render_case([{'speeds': (1., 4.)}], animated=True)
        errors = []
        for frame, image in enumerate(images):
            child = unmapped(steps[1], frame / FPS)
            scale = .4 + .5 * min(1., max(0., child / steps[0]['duration']))
            row = [image.getpixel((x, HEIGHT // 2))[1] > 35 for x in range(WIDTH)]
            self.assertTrue(any(row))
            width = max(x for x, value in enumerate(row) if value) - min(x for x, value in enumerate(row) if value) + 1
            errors.append(abs(width - WIDTH * scale))
        self.assertLessEqual(max(errors), 3., f'Child keyframe clock drift: {errors}')

    def test_nested_clock_mask_local_animation_uses_authored_clock(self):
        _, images, steps, _ = self.render_case([{'speeds': (1., 4.)}], mask_animated=True)
        errors = []
        for frame, image in enumerate(images):
            child = unmapped(steps[1], frame / FPS)
            width = WIDTH * (.4 + .5 * min(1., max(0., child / steps[0]['duration'])))
            observed = sum(image.getpixel((x, HEIGHT // 2))[1] > 35 for x in range(WIDTH))
            errors.append(abs(observed - width))
        self.assertLessEqual(max(errors), 3., f'Mask-local keyframe clock drift: {errors}')

    def test_nested_clock_inner_parent_animation_uses_outer_inverse_clock(self):
        _, images, steps, _ = self.render_case([{'speeds': (1., 2.), 'animate': True}, {'speeds': (.8, 2.)}])
        errors = []
        for frame, image in enumerate(images):
            child = unmapped(steps[2], frame / FPS)
            scale = .4 + .5 * min(1., max(0., child / steps[1]['duration']))
            row = [image.getpixel((x, HEIGHT // 2))[1] > 35 for x in range(WIDTH)]
            self.assertTrue(any(row))
            width = max(x for x, value in enumerate(row) if value) - min(x for x, value in enumerate(row) if value) + 1
            errors.append(abs(width - WIDTH * scale))
        self.assertLessEqual(max(errors), 3., f'Parent keyframe clock drift: {errors}')

    def test_nested_clock_resamples_to_different_output_rate(self):
        self.assert_source_clock([{'speeds': (1., 4.)}], output_fps=30)

    def test_nested_clock_multiple_segments_and_hold_keep_breakpoints(self):
        self.assert_source_clock([{'points': [(0., 1., 'hold'), (.75, 2., 'linear'),
                                             (2., 4., 'linear'), (3., 1., 'linear')]}])

    def test_nested_clock_reversed_multi_segment_curve_keeps_breakpoints(self):
        self.assert_source_clock([{'reverse': True, 'points': [(0., 1., 'hold'), (.75, 2., 'linear'),
                                                              (2., 4., 'linear'), (3., 1., 'linear')]}])

    def test_nested_clock_audio_pulses_follow_same_integrated_clock(self):
        output, _, steps, result = self.render_case([{'speeds': (1., 4.)}], audio=True)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-map', '0:a:0', '-vn', '-ac', '1',
                              '-ar', '48000', '-f', 's16le', 'pipe:1'], capture_output=True, check=True).stdout
        samples = array.array('h'); samples.frombytes(raw)
        mismatches = []
        checked = 0
        for offset in range(0, len(samples) - 960, 960):
            at = (offset + 480) / 48000
            source = unmapped(steps[1], at)
            if min(abs(source - boundary) for boundary in (.6, .9, 1.8, 2.1)) < .10:
                continue
            expected = .6 <= source < .9 or 1.8 <= source < 2.1
            rms = math.sqrt(sum((x / 32768) ** 2 for x in samples[offset:offset + 960]) / 960)
            checked += 1
            if (rms > .15) != expected:
                mismatches.append(round(at, 4))
        self.assertGreater(checked, 15)
        self.assertEqual(mismatches, [], f'Audio envelope follows averaged speed at {mismatches}')
        self.assertTrue(any(item.get('feature') == 'audio_speed_curve_piecewise' for item in result['data']['warnings']))


if __name__ == '__main__':
    unittest.main()
