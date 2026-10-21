"""Native integer PCM must not acquire a second integer quantization on resampling."""
from __future__ import annotations
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

import numpy as np
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.render import build_filter_graph
from test_magnetic_reorder import invoke

RATE, TPS = 48000, 90000


class AudioResamplePrecisionTests(unittest.TestCase):
    @staticmethod
    def native(arguments, *, data=None, cwd=None):
        result = subprocess.run(list(map(str, arguments)), input=data, capture_output=True, cwd=cwd, timeout=120)
        if result.returncode:
            raise AssertionError(result.stderr.decode('utf8', 'replace'))
        return result.stdout

    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parents[1] / '.runtime/temp'
        base.mkdir(parents=True, exist_ok=True)
        cls.shared = tempfile.TemporaryDirectory(prefix='resample-precision-', dir=base)
        cls.addClassCleanup(cls.shared.cleanup)
        cls.fixture = Path(cls.shared.name)
        cls.video = cls.fixture / 'picture.mkv'
        cls.native([ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i',
            'color=c=0x203040:size=32x18:rate=25:duration=2', '-c:v', 'ffv1', cls.video])
        cls.sources, cls.normalized = {}, {}
        for name, rate, channels, floating in (
            ('mono8k', 8000, 1, False), ('stereo44k', 44100, 2, False), ('float48k', 48000, 2, True)
        ):
            t = np.arange(2 * rate, dtype=np.float64) / rate
            rng = np.random.default_rng(821173)
            gain = rng.uniform(.11, .67, 80)[np.minimum((t * 40).astype(int), 79)]
            values = np.stack([gain * (np.sin(2*np.pi*(233+197*c)*t + .17*c) +
                .13*np.sin(2*np.pi*(391+109*c)*t)) for c in range(channels)], axis=1)
            path = cls.fixture / (name + '.wav')
            if floating:
                cls.native([ffmpeg_path(), '-v', 'error', '-f', 'f32le', '-ar', rate, '-ac', channels,
                    '-i', 'pipe:0', '-c:a', 'pcm_f32le', path], data=values.astype('<f4').tobytes())
            else:
                with wave.open(str(path), 'wb') as output:
                    output.setnchannels(channels); output.setsampwidth(2); output.setframerate(rate)
                    output.writeframes(np.rint(values * 32767).astype('<i2').tobytes())
            cls.sources[name] = path
            # Normalize the whole native stream independently, before any author
            # selection, nested composition or reversal. No renderer plan is used.
            raw = cls.native([ffmpeg_path(), '-v', 'error', '-i', path, '-af',
                'aresample=48000:osf=flt:first_pts=0,'
                'aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo',
                '-f', 'f32le', '-ac', '2', 'pipe:1'])
            cls.normalized[name] = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
            if len(cls.normalized[name]) != 2 * RATE:
                raise AssertionError('independent whole-stream normalization changed sample count')

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(prefix='case-', dir=self.fixture)
        self.addCleanup(self.case.cleanup)
        self.root = Path(self.case.name) / 'project'
        create_project(self.root)

    def compare(self, name, *, selected=True, reverse=False, nested=False, curve=False):
        code, response = invoke('media', 'ingest', '--project', self.root, '--input', self.sources[name])
        self.assertEqual(code, 0, response)
        video_code, video_response = invoke('media', 'ingest', '--project', self.root, '--input', self.video)
        self.assertEqual(video_code, 0, video_response)
        project = load_project(self.root)[1]
        project['settings']['canvas'] = {'width':32, 'height':18, 'background':'#000000'}
        project['settings']['timebase'] = {'ticks_per_second':TPS, 'display_fps':{'num':25, 'den':1}}
        left, right = (.125, 1.375) if selected else (0., 2.)
        duration = round((right-left) * TPS)
        audio = {'id':'sound', 'asset_id':response['data']['asset']['id'], 'timeline_start_tick':0,
            'source_in_tick':round(left*TPS), 'source_out_tick':round(right*TPS),
            'duration_tick':duration, 'reverse':reverse}
        if curve:
            audio['speed_curve'] = {'keyframes':[{'at_tick':0, 'speed':1.}, {'at_tick':duration, 'speed':1.}]}
        sequence = project['sequences'][0]
        sequence['duration_tick'] = duration
        sequence['tracks'] = [{'id':'picture', 'kind':'video', 'clips':[{'id':'background',
            'asset_id':video_response['data']['asset']['id'], 'timeline_start_tick':0,
            'source_in_tick':0, 'source_out_tick':duration, 'duration_tick':duration}]},
            {'id':'audio', 'kind':'audio', 'clips':[audio]}]
        if nested:
            child = copy.deepcopy(sequence); child['id'] = 'child'
            child['tracks'] = [{'id':'child-audio', 'kind':'audio', 'clips':[audio]}]
            project['sequences'].append(child)
            sequence['tracks'][1]['clips'] = [{'id':'parent', 'sequence_id':'child',
                'timeline_start_tick':0, 'source_in_tick':0, 'source_out_tick':duration, 'duration_tick':duration}]
        save_project(self.root, project)
        inputs, graph, _, _ = build_filter_graph(self.root, project, sequence)
        raw = self.native([ffmpeg_path(), '-v', 'error', '-filter_complex_threads', '1', *inputs,
            '-filter_complex', graph, '-map', '[aout]', '-f', 'f32le', '-ac', '2', 'pipe:1',
            '-map', '[vout]', '-f', 'null', 'NUL'], cwd=self.root)
        actual = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
        expected = self.normalized[name][round(left*RATE):round(right*RATE)]
        if reverse: expected = expected[::-1]
        self.assertEqual(actual.shape, expected.shape)
        difference = actual.astype(np.float64) - expected
        # Permit float32 mixing roundoff, far below the observed unwanted
        # s16 quantization (~1.08e-5 at 8 kHz mono).
        maximum = float(np.max(np.abs(difference)))
        rms = float(np.sqrt(np.mean(difference**2)))
        self.assertLessEqual(maximum, 6e-8, f'{name}: max error={maximum}, RMS={rms}')
        self.assertLessEqual(rms, 2e-8, f'{name}: RMS={rms}')

    def test_8k_mono_complete_stream_keeps_fractional_resampler_samples(self):
        self.compare('mono8k', selected=False)

    def test_8k_mono_selected_window_uses_whole_stream_float_samples(self):
        self.compare('mono8k')

    def test_8k_mono_reverse_keeps_float_precision_and_sample_order(self):
        self.compare('mono8k', reverse=True)

    def test_8k_mono_nested_window_keeps_float_precision(self):
        self.compare('mono8k', nested=True)

    def test_44k_stereo_selected_window_keeps_float_precision(self):
        self.compare('stereo44k')

    def test_44k_stereo_reverse_keeps_float_precision(self):
        self.compare('stereo44k', reverse=True)

    def test_identity_curve_remains_consistent_with_float_reference(self):
        self.compare('mono8k', selected=False, curve=True)

    def test_native_48k_float_control_stays_sample_exact(self):
        self.compare('float48k')


if __name__ == '__main__':
    unittest.main()
