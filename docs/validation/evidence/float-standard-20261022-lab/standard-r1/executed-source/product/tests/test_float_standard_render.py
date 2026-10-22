"""Original pixels -> common render/queue/resume, checked after real encoding."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor import cli, render
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_standard_render import ENGINE, configuration
from ai_ad_editor.media import ffmpeg_path, probe_media
from ai_ad_editor.project import create_project, project_write_lock, save_project
from ai_ad_editor.validator import validate_project

NATIVE_CALLS = []
RENDER_RECEIPTS = []
ERROR_RECEIPTS = []
LINEAR = {'primaries': 'bt709', 'transfer': 'linear'}


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


class FloatStandardRenderTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.runtime/temp'
        base.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='float-standard-', dir=base)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root, self.p = create_project(self.base / 'project')
        self.p['settings']['timebase']['display_fps'] = {'num': 10, 'den': 1}
        self.p['settings']['canvas'].update(width=32, height=16, background='#000000')
        self.p['settings']['color']['transfer'] = 'linear'
        self.p['settings']['output'] = {'container': 'mkv',
            'video': {'codec': 'libx264', 'crf': 0, 'preset': 'ultrafast', 'pixel_format': 'yuv444p10le'},
            'audio': {'codec': 'pcm_f32le'}}
        self.p['settings']['pixel_pipeline'] = {'engine': ENGINE, 'working_signal': dict(LINEAR),
            'output_signal': dict(LINEAR), 'window_frames': 2, 'sources': {}}
        self.s = self.p['sequences'][0]
        self.s['duration_tick'] = 9000

    def native(self, command):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=self.root, capture_output=True, timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        NATIVE_CALLS.append({'test': self.id(), 'command': command, 'exit_code': result.returncode,
            'stdout_bytes': len(result.stdout), 'stdout_sha256': 'sha256:' + hashlib.sha256(result.stdout).hexdigest(),
            'stderr': result.stderr.decode('utf8', 'replace')[-4000:]})
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf8', 'replace'))
        return result.stdout

    def visual(self, rgba=None, *, vfr=False, sar=None):
        if rgba is None:
            rgba = np.broadcast_to(np.array([.25, .5, .75, 1], np.float32), (1, 16, 32, 4)).copy()
        if rgba.ndim == 3:
            rgba = rgba[None]
        count, h, w, _ = rgba.shape
        self.p['settings']['canvas'].update(width=w, height=h)
        raw = self.root / 'assets/source.gbrap16'
        planes = np.moveaxis(np.rint(rgba.astype(np.float64) * 65535).astype('<u2')[:, :, :, [1, 2, 0, 3]], 3, 1)
        raw.write_bytes(planes.tobytes())
        output = self.root / 'assets/source.nut'
        command = [ffmpeg_path(), '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'gbrap16le',
                   '-video_size', f'{w}x{h}', '-framerate', '8' if vfr else '10', '-i', raw]
        if vfr:
            self.assertEqual(count, 8)
            command += ['-vf', 'settb=1/8,setpts=if(eq(N,0),0,if(eq(N,1),1,if(eq(N,2),3,if(eq(N,3),5,if(eq(N,4),8,if(eq(N,5),11,if(eq(N,6),15,20)))))))+40', '-fps_mode', 'vfr']
        elif sar:
            command += ['-vf', f'setsar={sar}']
        self.native([*command, '-c:v', 'ffv1', '-level', '3', '-g', '1', output])
        self.p['assets'].append({'id': 'picture', 'kind': 'video', 'uri': 'assets/source.nut',
            'sha256': sha(output), 'rights_ref': None, 'probe': probe_media(output)})
        self.p['settings']['pixel_pipeline']['sources']['picture'] = {'source_signal': dict(LINEAR), 'display_geometry': 'square-unrotated'}
        self.s['tracks'][0]['clips'] = [{'id': 'picture', 'asset_id': 'picture', 'timeline_start_tick': 0,
            'duration_tick': self.s['duration_tick'], 'source_in_tick': 0, 'source_out_tick': self.s['duration_tick']}]
        return rgba

    def audio(self):
        t = np.arange(48000, dtype=np.float64) / 48000
        samples = np.stack((.2*np.sin(2*np.pi*347*t), .17*np.cos(2*np.pi*619*t)), 1).astype('<f4')
        raw = self.root / 'assets/audio.f32'; raw.write_bytes(samples.tobytes())
        wave = self.root / 'assets/audio.wav'
        self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', raw, '-c:a', 'pcm_f32le', wave])
        self.p['assets'].append({'id': 'sound', 'kind': 'audio', 'uri': 'assets/audio.wav', 'sha256': sha(wave), 'probe': probe_media(wave)})
        self.s['tracks'][1]['clips'] = [{'id': 'sound', 'asset_id': 'sound', 'timeline_start_tick': 0,
            'duration_tick': 90000, 'source_in_tick': 0, 'source_out_tick': 90000}]
        return samples

    def execute(self, name='actual.mkv', **kwargs):
        save_project(self.root, self.p)
        with project_write_lock(self.root):
            try:
                result = render.render_project(self.root, self.p, self.s, self.root/'renders'/name, **kwargs)
            except AppError as exc:
                ERROR_RECEIPTS.append({'test': self.id(), 'error': exc.as_dict()})
                raise
        RENDER_RECEIPTS.append({'test': self.id(), **copy.deepcopy(result)})
        return result

    def invoke(self, *args):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main(list(map(str, args)))
        return code, json.loads(buffer.getvalue())

    def assert_clean(self):
        self.assertFalse([t.name for t in threading.enumerate() if t.name.startswith(('float-encoder-', 'float-native-'))])
        self.assertFalse(list((self.root/'renders/.tmp').glob('*')))

    def decode_y(self, output, w, h):
        data = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', output, '-map', '0:v:0', '-an', '-pix_fmt', 'yuv444p10le', '-f', 'rawvideo', 'pipe:1'])
        return np.frombuffer(data, '<u2').reshape(-1, 3, h, w)

    def test_standard_ten_bit_delivery_preserves_more_than_800_independent_gray_levels(self):
        values = np.arange(65536, dtype=np.float32).reshape(256, 256) / 65535
        rgba = np.ones((256, 256, 4), np.float32); rgba[:, :, :3] = values[:, :, None]
        self.visual(rgba)
        result = self.execute()
        actual = self.decode_y(result['path'], 256, 256)
        expected = 64 + values.astype(np.float64) * 876
        self.assertGreaterEqual(len(np.unique(actual[0, 0])), 870)
        self.assertLessEqual(float(np.max(np.abs(actual[0, 0] - expected))), 1.5)
        self.assertTrue(np.all(np.abs(actual[0, 1:].astype(int) - 512) <= 1))
        transport = result['delivery']['pixel_pipeline']['transport']
        self.assertEqual(transport['frames'], 1)
        self.assertEqual(transport['RGB_quantization_bits'], 16)
        self.assertTrue(transport['owned_threads_closed'])
        self.assert_clean()

    def test_webm_all_alpha_codes_and_near_rounding_boundaries_survive_separate_plane(self):
        codes = np.arange(256, dtype=np.float32) / 255
        rgba = np.ones((16, 256, 4), np.float32); rgba[:, :, :3] = [.125, .375, .875]
        rgba[:, :, 3] = codes
        self.p['settings']['canvas']['background'] = 'transparent'
        self.p['settings']['output'] = {'container': 'webm', 'video': {'codec': 'libvpx-vp9', 'crf': 0, 'pixel_format': 'yuva420p'}, 'audio': {'codec': 'libopus'}}
        self.visual(rgba)
        result = self.execute('alpha.webm')
        data = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-c:v', 'libvpx-vp9', '-i', result['path'], '-map', '0:v:0', '-vf', 'alphaextract', '-pix_fmt', 'gray', '-f', 'rawvideo', 'pipe:1'])
        np.testing.assert_array_equal(np.frombuffer(data, np.uint8).reshape(-1, 16, 256)[0], np.broadcast_to(np.arange(256, dtype=np.uint8), (16, 256)))
        self.assertEqual(result['delivery']['pixel_pipeline']['transport']['alpha_quantization_bits'], 8)
        self.assert_clean()

    def test_common_audio_reverse_freeze_keeps_each_pcm_sample(self):
        self.s['duration_tick'] = 90000
        self.visual(np.broadcast_to(np.array([.25, .25, .25, 1], np.float32), (10, 16, 32, 4)).copy())
        samples = self.audio()
        self.s['tracks'][1]['clips'][0].update(source_out_tick=72000, reverse=True, freeze={'at_tick': 22500, 'duration_tick': 18000})
        result = self.execute()
        actual = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', result['path'], '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])
        reverse = samples[:38400][::-1]
        expected = np.concatenate((reverse[:12000], np.zeros((9600, 2), '<f4'), reverse[12000:]))
        self.assertEqual(actual, expected.tobytes())
        self.assertEqual(result['delivery']['clock']['expected_audio_samples_48000'], 48000)
        self.assertEqual(len(self.decode_y(result['path'], 32, 16)), 10)
        self.assert_clean()

    def test_fractional_end_keeps_video_ceil_and_exact_independent_audio(self):
        self.s['duration_tick'] = 112501
        self.visual(np.broadcast_to(np.array([.3, .3, .3, 1], np.float32), (13, 16, 32, 4)).copy())
        samples = self.audio()
        result = self.execute()
        actual = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', result['path'], '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])
        self.assertEqual(actual, np.concatenate((samples, np.zeros((12001, 2), '<f4'))).tobytes())
        self.assertEqual(len(self.decode_y(result['path'], 32, 16)), 13)
        self.assert_clean()

    def test_public_cli_mp4_and_persistent_queue_use_same_pipeline(self):
        self.visual()
        self.p['settings']['color']['transfer'] = 'bt709'
        self.p['settings']['pixel_pipeline']['output_signal']['transfer'] = 'bt709-oetf'
        self.p['settings']['output'] = {'container': 'mp4', 'video': {'codec': 'libx264', 'crf': 18, 'pixel_format': 'yuv420p'}, 'audio': {'codec': 'aac', 'bitrate': '192k'}}
        save_project(self.root, self.p)
        code, value = self.invoke('render', '--project', self.root, '--output', self.root/'renders/cli.mp4')
        self.assertEqual(code, 0, value)
        self.assertEqual(value['data']['delivery']['pixel_pipeline']['engine'], ENGINE)
        jobs = self.base/'jobs.json'; jobs.write_text(json.dumps({'job_id': 'float', 'output': 'renders/queued.mp4'}), encoding='utf8')
        code, value = self.invoke('queue', 'enqueue', '--project', self.root, '--input', jobs)
        self.assertEqual(code, 0, value)
        code, value = self.invoke('queue', 'run', '--project', self.root, '--job-id', 'float')
        self.assertEqual(code, 0, value)
        self.assertEqual(value['data']['summary']['succeeded'], 1, value)
        manifest = json.loads((self.root/'renders/queued.mp4.manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['delivery']['pixel_pipeline']['engine'], ENGINE)
        self.assertEqual(manifest['probe']['video']['codec_name'], 'h264')
        self.assert_clean()

    def test_transparent_frame_rejects_opaque_output_without_replacing_previous(self):
        rgba = np.ones((16, 32, 4), np.float32); rgba[:, :, 3] = .5
        self.visual(rgba); self.p['settings']['canvas']['background'] = 'transparent'
        output = self.root/'renders/actual.mkv'; output.write_bytes(b'old user movie')
        with self.assertRaises(AppError) as caught:
            self.execute()
        self.assertEqual(caught.exception.code, 'FLOAT_RENDER_ALPHA')
        self.assertEqual(output.read_bytes(), b'old user movie')
        self.assert_clean()

    def test_changed_registered_original_rejects_before_encoder(self):
        self.visual(); (self.root/'assets/source.nut').write_bytes(b'changed original')
        with patch('ai_ad_editor.float_standard_render._EncoderPipe', side_effect=AssertionError('must not encode')):
            with self.assertRaises(AppError) as caught:
                self.execute()
        self.assertEqual(caught.exception.code, 'FLOAT_RENDER_SOURCE_CHANGED')
        self.assert_clean()

    def test_known_non_square_source_is_rejected_instead_of_silent_raster(self):
        self.visual(sar='2/1')
        with self.assertRaises(AppError) as caught:
            self.execute()
        self.assertEqual(caught.exception.code, 'FLOAT_RENDER_GEOMETRY')
        self.assert_clean()

    def test_declared_unsupported_operator_never_falls_back_to_legacy(self):
        self.visual(); self.s['tracks'][0]['clips'][0]['effects'] = [{'type': 'blur', 'radius': 3}]
        with patch('ai_ad_editor.render.build_filter_graph', side_effect=AssertionError('legacy fallback')):
            with self.assertRaises(AppError) as caught:
                self.execute()
        self.assertTrue(caught.exception.code.startswith('FLOAT_TIMELINE_'), caught.exception.code)
        self.assert_clean()

    def test_runtime_configuration_and_schema_reject_unhandled_fields(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[2]/'docs/specs/agent-project.schema.json').read_text(encoding='utf8'))
        self.visual()
        for update in ({'decoder': 'a b'}, {'scan': 'interlaced'}, {'demux_origin': '1/0'}, {'demux_origin': .5}, {'unknown': 1}):
            with self.subTest(update=update):
                p = copy.deepcopy(self.p); p['settings']['pixel_pipeline']['sources']['picture'].update(update)
                with self.assertRaises(AppError):
                    configuration(p['settings']['pixel_pipeline'], p['settings'], render.output_settings(p['settings']))
                if update != {'demux_origin': '1/0'}:
                    self.assertTrue(list(Draft202012Validator(schema).iter_errors(p)))

    def test_builtin_validation_rejects_color_tags_instead_of_relabelling(self):
        self.visual(); self.p['settings']['color']['transfer'] = 'bt709'
        with patch('ai_ad_editor.validator._schema_report', return_value=([], [], 'builtin')):
            report = validate_project(self.root, self.p)
        self.assertTrue(any(e['code'] == 'FLOAT_RENDER_COLOR_TAGS' for e in report['errors']), report)


if __name__ == '__main__':
    unittest.main()
