"""Independent alpha planes and native stream-end controls for final delivery."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from ai_ad_editor.media import probe_media
from ai_ad_editor.project import create_project, save_project
from ai_ad_editor.quality import check_output
from ai_ad_editor.runtime import configure_local_runtime
from test_source_transitions import invoke

TPS, SR, W, H = 90000, 48000, 256, 32


def native(*args, data=None):
    return subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)],
                          input=data, capture_output=True, check=True).stdout


def decode(path, *, decoder=None):
    options = ['-c:v', decoder] if decoder else []
    raw = native(*options, '-i', path, '-an', '-fps_mode', 'passthrough',
                 '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1')
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W, 4)


class DeliveryPrecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.base = tempfile.TemporaryDirectory(prefix='delivery-precision-fixture-')
        cls.addClassCleanup(cls.base.cleanup)
        cls.basepath = Path(cls.base.name)
        cls.fixture, project = create_project(cls.basepath/'project', name='delivery-precision')
        y, x = np.indices((H, W))
        cls.frames = np.empty((12, H, W, 4), dtype=np.uint8)
        for frame in range(12):
            cls.frames[frame, :, :, :3] = [60+frame*7, 120, 210]
            cls.frames[frame, :, :, 3] = (x+7*y+19*frame) % 256
        image = cls.basepath/'ramp.png'
        Image.fromarray(cls.frames[0]).save(image)
        movie = cls.basepath/'ramp.mkv'
        native('-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', '10',
               '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra', movie,
               data=cls.frames.tobytes())
        n = np.arange(5*SR)/SR
        cls.pcm = np.stack((.08+.01*n, -.07+.005*n), axis=1).astype('<f4')
        sound = cls.basepath/'sound.wav'
        native('-f', 'f32le', '-ar', SR, '-ac', 2, '-i', 'pipe:0', '-c:a', 'pcm_f32le',
               sound, data=cls.pcm.tobytes())
        for source, aid in ((image, 'ramp'), (movie, 'moving_ramp'), (sound, 'sound')):
            code, result = invoke('media', 'ingest', '--project', str(cls.fixture),
                                  '--input', str(source), '--asset-id', aid)
            if code:
                raise AssertionError(result)
        project = json.loads((cls.fixture/'project.json').read_bytes())
        project['settings']['canvas'].update(width=W, height=H)
        project['settings']['timebase']['display_fps'] = {'num': 10, 'den': 1}
        save_project(cls.fixture, project)

    def setUp(self):
        raw = tempfile.TemporaryDirectory(prefix='delivery-precision-')
        self.addCleanup(raw.cleanup)
        self.root = Path(raw.name)/'project'
        shutil.copytree(self.fixture, self.root)
        self.project = json.loads((self.root/'project.json').read_bytes())

    def author(self, *, duration=TPS, fps=(10, 1), asset='ramp'):
        self.project['settings']['timebase']['display_fps'] = {'num': fps[0], 'den': fps[1]}
        seq = self.project['sequences'][0]
        seq.update(duration_tick=duration, tracks=[
            {'id': 'picture', 'kind': 'video', 'order': 0, 'clips': [
                {'id': 'picture_clip', 'asset_id': asset, 'timeline_start_tick': 0,
                 'duration_tick': duration, 'source_in_tick': 0, 'source_out_tick': duration}]},
            {'id': 'sound_track', 'kind': 'audio', 'order': 1, 'clips': [
                {'id': 'sound_clip', 'asset_id': 'sound', 'timeline_start_tick': 0,
                 'duration_tick': duration, 'source_in_tick': 0, 'source_out_tick': duration}]}])
        save_project(self.root, self.project)
        return seq

    def render(self, name, *, alpha=False, codec='libvpx-vp9', crf=0, dry=False, mkv=False):
        suffix = '.webm' if alpha else ('.mkv' if mkv else '.mp4')
        output = self.root/'renders'/(name+suffix)
        options = (['--container', 'webm', '--video-codec', codec, '--audio-codec', 'libopus',
                    '--pixel-format', 'yuva420p'] if alpha else
                   ['--container', 'mkv', '--audio-codec', 'pcm_f32le', '--pixel-format', 'yuv444p'] if mkv else [])
        code, result = invoke('render', '--project', str(self.root), '--output', str(output),
                              '--crf', str(crf), *options, *(['--dry-run'] if dry else []))
        self.assertEqual(code, 0, result)
        return output, result

    def test_lossless_vp9_keeps_all_256_static_alpha_levels(self):
        self.author()
        output, result = self.render('static', alpha=True)
        rgba = decode(output, decoder='libvpx-vp9')
        self.assertEqual(len(rgba), 10)
        self.assertTrue(np.array_equal(rgba[:, :, :, 3], np.broadcast_to(self.frames[0, :, :, 3], (10, H, W))))
        manifest = json.loads(Path(result['data']['manifest']).read_bytes())
        self.assertIn('delivery', manifest)
        self.assertEqual(manifest['delivery']['alpha']['encoding_precision'], 'lossless-yuv-alpha')

    def test_lossless_vp9_keeps_spatial_and_temporal_alpha_changes(self):
        self.author(duration=108000, asset='moving_ramp')
        output, _ = self.render('dynamic', alpha=True)
        actual = decode(output, decoder='libvpx-vp9')
        self.assertEqual(len(actual), 12)
        self.assertTrue(np.array_equal(actual[:, :, :, 3], self.frames[:, :, :, 3]))

    def test_transparent_vp9_roundtrip_uses_the_actual_alpha_decoder(self):
        self.author(duration=108000, asset='moving_ramp')
        first, _ = self.render('first', alpha=True)
        code, ingest = invoke('media', 'ingest', '--project', str(self.root), '--input', str(first), '--asset-id', 'roundtrip')
        self.assertEqual(code, 0, ingest)
        self.project = json.loads((self.root/'project.json').read_bytes())
        self.author(duration=108000, asset='roundtrip')
        second, result = self.render('second', alpha=True)
        actual = decode(second, decoder='libvpx-vp9')
        self.assertTrue(np.array_equal(actual[:, :, :, 3], self.frames[:, :, :, 3]))
        manifest = json.loads(Path(result['data']['manifest']).read_bytes())
        source = next(row for row in manifest['inputs'] if row.get('asset_id') == 'roundtrip')
        self.assertEqual(source['decoder']['name'], 'libvpx-vp9')

    def test_reimported_alpha_composites_on_dark_and_light_backgrounds(self):
        self.author()
        source, _ = self.render('source', alpha=True)
        source_rgba = decode(source, decoder='libvpx-vp9')
        code, _ = invoke('media', 'ingest', '--project', str(self.root), '--input', str(source), '--asset-id', 'roundtrip')
        self.assertEqual(code, 0)
        self.project = json.loads((self.root/'project.json').read_bytes())
        self.author(asset='roundtrip')
        original_tracks = copy.deepcopy(self.project['sequences'][0]['tracks'])
        for index, track in enumerate(original_tracks, 1):
            track['order'] = index
        for background in (16, 240):
            with self.subTest(background=background):
                path = self.root/f'background_{background}.png'
                Image.new('RGB', (W, H), (background,)*3).save(path)
                aid = f'background_{background}'
                code, ingest = invoke('media', 'ingest', '--project', str(self.root), '--input', str(path), '--asset-id', aid)
                self.assertEqual(code, 0, ingest)
                self.project = json.loads((self.root/'project.json').read_bytes())
                self.project['sequences'][0]['tracks'] = [
                    {'id': 'background', 'kind': 'video', 'order': 0, 'clips': [
                        {'id': 'background_clip', 'asset_id': aid, 'timeline_start_tick': 0,
                         'duration_tick': TPS, 'source_in_tick': 0, 'source_out_tick': TPS}]},
                    *copy.deepcopy(original_tracks)]
                save_project(self.root, self.project)
                output, _ = self.render('background_'+str(background), mkv=True)
                rgb = decode(output)[:, :, :, :3].astype(float)
                coverage = source_rgba[:, :, :, 3:4].astype(float)/255
                expected = source_rgba[:, :, :, :3]*coverage+background*(1-coverage)
                self.assertLessEqual(float(np.abs(rgb-expected).max()), 3)

    def test_vp8_alpha_is_real_and_reimportable(self):
        self.author()
        output, _ = self.render('vp8', alpha=True, codec='libvpx', crf=10)
        rgba = decode(output, decoder='libvpx')
        self.assertEqual(len(rgba), 10)
        self.assertLess(int(rgba[:, :, :, 3].min()), 5)
        self.assertGreater(int(rgba[:, :, :, 3].max()), 250)
        code, _ = invoke('media', 'ingest', '--project', str(self.root), '--input', str(output), '--asset-id', 'vp8')
        self.assertEqual(code, 0)
        self.project = json.loads((self.root/'project.json').read_bytes())
        self.author(asset='vp8')
        rebuilt, _ = self.render('vp8_readback', alpha=True)
        self.assertTrue(np.array_equal(decode(rebuilt, decoder='libvpx-vp9')[:, :, :, 3], rgba[:, :, :, 3]))

    def test_lossy_alpha_encoding_reports_a_distinct_precision_scope(self):
        self.author(duration=108000, asset='moving_ramp')
        output, result = self.render('lossy', alpha=True, crf=35)
        actual = decode(output, decoder='libvpx-vp9')
        self.assertEqual(len(actual), 12)
        self.assertGreater(int(actual[:, :, :, 3].max()), 240)
        manifest = json.loads(Path(result['data']['manifest']).read_bytes())
        self.assertIn('delivery', manifest)
        self.assertEqual(manifest['delivery']['alpha']['encoding_precision'], 'lossy-yuv-alpha')
        self.assertFalse(manifest['delivery']['alpha']['rgba_lossless'])

    def test_fractional_mp4_keeps_41_frames_without_lengthening_audio(self):
        self.author(duration=360900)
        output, result = self.render('fractional')
        self.assertEqual(len(decode(output)), 41)
        probe = probe_media(output)
        self.assertAlmostEqual(probe['audio']['duration_seconds'], 4.01, places=3)
        metrics = result['data']['quality']['metrics']
        self.assertAlmostEqual(metrics['av_duration_delta_seconds'], .09, places=3)
        self.assertLess(metrics['av_sync_residual_seconds'], .002)

    def test_fractional_mkv_keeps_every_authored_pcm_sample(self):
        self.author(duration=360900)
        output, result = self.render('fractional_pcm', mkv=True)
        pcm = np.frombuffer(native('-i', output, '-vn', '-ar', SR, '-ac', 2, '-f', 'f32le', 'pipe:1'), dtype='<f4').reshape(-1, 2)
        self.assertEqual(len(pcm), 192480)
        self.assertTrue(np.array_equal(pcm, self.pcm[:192480]))
        self.assertIn('stream_timing', result['data']['quality']['metrics'])
        timing = result['data']['quality']['metrics']['stream_timing']
        self.assertEqual(timing['audio']['duration_source'], 'matroska-duration-tag')
        self.assertAlmostEqual(timing['audio']['end_seconds'], 4.01, places=6)

    def test_one_fps_short_root_explains_the_display_frame_tail(self):
        self.author(duration=9900, fps=(1, 1))
        output, result = self.render('one_fps')
        self.assertEqual(len(decode(output)), 1)
        self.assertAlmostEqual(result['data']['quality']['metrics']['expected_video_duration_seconds'], 1)

    def test_one_tick_over_a_frame_boundary_is_not_rounded_away(self):
        self.author(duration=9001)
        output, result = self.render('one_tick')
        self.assertEqual(len(decode(output)), 2)
        self.assertEqual(result['data']['quality']['metrics']['expected_video_frames'], 2)

    def test_fractional_rate_exact_boundary_and_next_tick(self):
        for duration, count in ((9009, 3), (9010, 4)):
            with self.subTest(duration_tick=duration):
                self.author(duration=duration, fps=(30000, 1001))
                output, result = self.render('fractional_rate_'+str(duration))
                self.assertEqual(len(decode(output)), count)
                self.assertIn('expected_video_frames', result['data']['quality']['metrics'])
                self.assertEqual(result['data']['quality']['metrics']['expected_video_frames'], count)

    def test_quality_cli_and_golden_share_the_same_quantized_clock(self):
        self.author(duration=360900)
        output, _ = self.render('quality_clock')
        for domain, extras in (('check', []), ('golden', ['--mode', 'capture']), ('golden', ['--mode', 'verify'])):
            with self.subTest(domain=domain, extras=extras):
                code, result = invoke('quality', domain, '--project', str(self.root), '--input', str(output),
                                      '--sequence-id', self.project['sequences'][0]['id'], '--require-audio', *extras)
                self.assertEqual(code, 0, result)


class DeliveryTimingGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.base = tempfile.TemporaryDirectory(prefix='delivery-timing-gates-')
        cls.addClassCleanup(cls.base.cleanup)
        cls.root = Path(cls.base.name)
        cls.settings = {'canvas': {'width': W, 'height': H}, 'timebase': {
            'ticks_per_second': TPS, 'display_fps': {'num': 10, 'den': 1}}}
        cls.paths = {}
        for name, sound_duration, audio_offset, common_offset in (
                ('good', 4.01, 0, 0), ('delayed', 4.01, .12, 0), ('advanced', 4.01, -.12, 0),
                ('short', 3.8, 0, 0), ('long', 4.3, 0, 0), ('both_shifted', 4.01, 0, .12)):
            path = cls.root/(name+'.mp4')
            native('-f', 'lavfi', '-i', f'color=c=0x8090a0:s={W}x{H}:r=10:d=4.1',
                   '-f', 'lavfi', '-i', f'sine=frequency=371:sample_rate={SR}:duration={sound_duration}',
                   '-filter_complex', f'[1:a]asetpts=PTS+{audio_offset}/TB[a]',
                   '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'ultrafast',
                   '-crf', '0', '-pix_fmt', 'yuv444p', '-c:a', 'aac',
                   '-output_ts_offset', common_offset, path)
            cls.paths[name] = path

    def check(self, name, expected=4.01):
        return check_output(self.paths[name], self.settings, expected, require_audio=True, run_expensive=False)

    def test_native_quantized_tail_passes_without_increasing_80_ms_limit(self):
        result = self.check('good')
        self.assertTrue(result['ok'], result)
        self.assertGreater(result['metrics']['av_duration_delta_seconds'], .08)
        self.assertLess(result['metrics']['av_sync_residual_seconds'], .002)

    def test_equal_length_but_delayed_audio_still_fails(self):
        result = self.check('delayed')
        self.assertFalse(result['ok'], result)
        self.assertTrue(any(e['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for e in result['errors']))

    def test_negative_audio_offset_still_fails(self):
        result = self.check('advanced')
        self.assertFalse(result['ok'], result)
        self.assertTrue(any(e['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for e in result['errors']))

    def test_audio_ending_early_still_fails(self):
        self.assertFalse(self.check('short')['ok'])

    def test_audio_ending_late_still_fails(self):
        self.assertFalse(self.check('long')['ok'])

    def test_common_timestamp_offset_is_not_hidden_by_equal_start_times(self):
        result = self.check('both_shifted')
        self.assertFalse(result['ok'], result)
        self.assertTrue(any(e['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for e in result['errors']))

    def test_no_author_duration_does_not_guess_a_quantization_allowance(self):
        result = self.check('good', expected=None)
        self.assertFalse(result['ok'], result)

    def test_malformed_stream_tag_is_reported_as_unverified_timing(self):
        probe = {'duration_seconds': 4.1, 'video': {'codec': 'h264', 'width': W, 'height': H, 'duration_seconds': 4.1},
                 'audio': {'codec': 'pcm_f32le', 'sample_rate': SR},
                 'streams': [{'codec_type': 'audio', 'tags': {'DURATION': '00:99:bad'}}]}
        with patch('ai_ad_editor.quality.probe_media', return_value=probe):
            result = self.check('good')
        self.assertIsNone(result['metrics']['audio_duration_seconds'])
        self.assertTrue(any(w['code'] == 'OUTPUT_AV_TIMING_UNAVAILABLE' for w in result['warnings']))

    def test_matroska_duration_tag_is_an_end_timestamp(self):
        probe = {'duration_seconds': 4.13,
                 'video': {'codec': 'h264', 'width': W, 'height': H, 'duration_seconds': 4.1},
                 'audio': {'codec': 'pcm_f32le', 'sample_rate': SR, 'start_time_seconds': .12},
                 'streams': [{'codec_type': 'audio', 'tags': {'DURATION': '00:00:04.130000000'}}]}
        with patch('ai_ad_editor.quality.probe_media', return_value=probe):
            result = self.check('good')
        timing = result['metrics']['stream_timing']['audio']
        self.assertAlmostEqual(timing['duration_seconds'], 4.01)
        self.assertAlmostEqual(timing['end_seconds'], 4.13)
        self.assertFalse(result['ok'])

    def test_stricter_requested_sync_gate_remains_effective(self):
        result = check_output(self.paths['delayed'], self.settings, 4.01,
                              run_expensive=False, max_av_sync_ms=10)
        self.assertFalse(result['ok'])


if __name__ == '__main__':
    unittest.main()
