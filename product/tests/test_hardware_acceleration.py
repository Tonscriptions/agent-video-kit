"""Policy, forced-frame boundaries and native CPU fallback without a GPU requirement."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_sequence_compositing as fixtures
import test_delivery_precision as alpha_fixtures
from ai_ad_editor.errors import AppError
from ai_ad_editor.hardware_acceleration import (AccelerationSession, apply_overrides, configuration,
    encoder_candidates, frame_hashes, hardware_failure, rewrite_command)
from ai_ad_editor.render import render_project
from ai_ad_editor.render_queue import normalize_job
from ai_ad_editor.schema_contract import make_validator
from ai_ad_editor.utils import atomic_write_json


class HardwarePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hardware-policy-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = {'canvas': {'width': 160, 'height': 96},
                         'timebase': {'display_fps': {'num': 24, 'den': 1}},
                         'acceleration': {'encode': 'prefer', 'decode': 'prefer'}}
        self.encoder = {'container': 'mkv', 'video': {'codec': 'libx264', 'bitrate': '2M', 'pixel_format': 'yuv420p'}}
        self.args = ['ffmpeg', '-i', 'a.mp4', '-filter_complex', '[0:v]null[vout]', '-c:v', 'libx264',
                     '-preset', 'medium', '-b:v', '2M', '-pix_fmt', 'yuv420p', '-f', 'matroska', 'out.mkv']

    def session(self, **policy):
        self.settings['acceleration'].update(policy)
        session = AccelerationSession(self.root, self.settings, self.encoder, 'test')
        session.selected_encoder = 'h264_nvenc'
        session.selected_decoders = {0: {'backend': 'cuda', 'pix_fmt': 'yuv420p'}}
        return session

    def execute(self, session, outcomes, gate=lambda: None):
        def result(args, **kwargs):
            value = outcomes.pop(0)
            if isinstance(value, AppError):
                raise value
            return subprocess.CompletedProcess(args, value[0], '', value[1])
        with patch('ai_ad_editor.hardware_acceleration.run_process', side_effect=result):
            return session.execute(self.args, '[0:v]null[vout]', lambda a, g: (a, {'kind': 'inline'}), gate)

    def test_configuration_rejects_unknown_boolean_string_budget_and_modes(self):
        for value in ([], {'unknown': 1}, {'decode': True}, {'encode': 'yes'}, {'encoder': []},
                      {'probe_max_bytes': True}, {'probe_max_bytes': '1048576'}, {'probe_max_bytes': 1024**3+1}):
            with self.subTest(value=value), self.assertRaises(AppError):
                configuration(value)
        self.assertEqual(configuration(None)['encode'], 'off')

    def test_queue_preserves_policy_and_rejects_invalid_override(self):
        job = normalize_job(self.root, {'job_id': 'a', 'hardware_encode': 'require', 'hardware_decoder': 'cuda', 'hardware_probe_mib': 16})
        self.assertEqual(job['hardware_encode'], 'require')
        settings = {}; apply_overrides(settings, job)
        self.assertEqual(settings['acceleration']['probe_max_bytes'], 16*1024**2)
        for raw in ({'hardware_probe_mib': True}, {'hardware_decoder': 'http'}, {'hardware_encode': 'yes'}):
            with self.assertRaises(AppError):
                normalize_job(self.root, raw)

    def test_schema_rejects_acceleration_extensions(self):
        validator = make_validator()
        schema = validator.schema['$defs']['settings']['properties']['acceleration']
        from jsonschema import Draft202012Validator
        checker = Draft202012Validator(schema)
        self.assertFalse(list(checker.iter_errors({'encode': 'require', 'decode': 'off'})))
        for raw in ({'encode': True}, {'remote': 'https://example.invalid'}, {'probe_max_bytes': 0}):
            self.assertTrue(list(checker.iter_errors(raw)))

    def test_explicit_bitrate_is_required_even_for_prefer(self):
        self.encoder['video'].pop('bitrate')
        with self.assertRaises(AppError) as caught:
            self.session()
        self.assertEqual(caught.exception.code, 'ACCELERATION_BITRATE_REQUIRED')

    def test_no_cross_platform_candidate_or_unsupported_codec(self):
        self.assertEqual(encoder_candidates('libx264', 'auto', 'linux'), [])
        self.assertEqual(encoder_candidates('libvpx', 'auto', 'win32'), [])
        self.assertEqual(encoder_candidates('libvpx-vp9', 'auto', 'win32'), ['vp9_qsv'])

    def test_physical_input_indices_preserve_image_audio_and_ten_bit(self):
        args = ['ffmpeg', '-loop', '1', '-i', 'a.png', '-i', 'b.wav', '-i', 'c.mp4', '-filter_complex',
                '[0:v]null[x];[2:v:0]null[y]', '-c:v', 'libx265', '-crf', '18', '-pix_fmt', 'yuv420p10le']
        command, graph = rewrite_command(args, args[args.index('-filter_complex')+1], 'hevc_nvenc',
            {2: {'backend': 'cuda', 'pix_fmt': 'yuv420p10le'}}, {**self.encoder['video'], 'pixel_format': 'yuv420p10le'}, 'mp4')
        self.assertEqual(command[command.index('-hwaccel')+1], 'cuda')
        self.assertEqual(command[command.index('-hwaccel_output_format')+2:command.index('-hwaccel_output_format')+4], ['-i', 'c.mp4'])
        self.assertIn('[2:v]hwdownload,format=p010le,format=yuv420p10le[hardware_input_2]', graph)
        self.assertIn('[0:v]null[x]', graph)
        self.assertNotIn('[2:v:0]null', graph)
        self.assertNotIn('-crf', command)
        self.assertEqual(command[-1], 'p010le')

    def test_prefer_fallback_is_bounded_and_logs_all_completed_attempts(self):
        session = self.session()
        result, _, _ = self.execute(session, [(1, 'CUDA device lost'), (1, 'h264_nvenc failed'), (0, '')])
        self.assertEqual(result.returncode, 0)
        attempts = session.evidence['attempts']
        self.assertEqual([a['encoder'] for a in attempts], ['h264_nvenc', 'h264_nvenc', 'libx264'])
        self.assertEqual([a['decoders'] for a in attempts], [{'0': 'cuda'}, {}, {}])
        self.assertEqual(len(list(session.directory.glob('render-*.stderr.log'))), 3)

    def test_required_encode_never_becomes_cpu(self):
        session = self.session(encode='require')
        result, _, _ = self.execute(session, [(1, 'CUDA failed'), (1, 'nvenc failed')])
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(a['encoder'] == 'h264_nvenc' for a in session.evidence['attempts']))

    def test_required_decode_survives_preferred_encode_fallback(self):
        session = self.session(decode='require')
        self.execute(session, [(1, 'nvenc failed'), (0, '')])
        self.assertEqual([a['decoders'] for a in session.evidence['attempts']], [{'0': 'cuda'}, {'0': 'cuda'}])
        self.assertEqual(session.evidence['attempts'][-1]['encoder'], 'libx264')

    def test_cancel_timeout_and_start_error_do_not_retry(self):
        for code in ('CANCELLED', 'PROCESS_TIMEOUT', 'PROCESS_START_FAILED'):
            with self.subTest(code=code):
                session = self.session()
                with self.assertRaises(AppError):
                    self.execute(session, [AppError(code, code, exit_code=6)])
                self.assertEqual(len(session.evidence['attempts']), 1)
                self.assertEqual(session.evidence['attempts'][0]['stderr_scope'], 'partial executor tail')

    def test_io_and_content_failures_do_not_retry(self):
        for stderr in ('cuda: No space left on device', 'nvenc Permission denied', 'Invalid data found when processing input', 'error opening output'):
            with self.subTest(stderr=stderr):
                session = self.session()
                self.execute(session, [(1, stderr)])
                self.assertEqual(len(session.evidence['attempts']), 1)

    def test_changed_inputs_stop_before_any_attempt(self):
        session = self.session()
        def gate():
            raise AppError('RENDER_INPUT_CHANGED', 'changed', exit_code=6)
        with self.assertRaises(AppError):
            self.execute(session, [], gate)
        self.assertEqual(session.evidence['attempts'], [])

    def test_final_format_and_color_gate_rejects_silent_loss(self):
        session = self.session()
        session.settings['color'] = {'primaries': 'bt2020'}
        probe = {'video': {'codec': 'h264', 'width': 160, 'height': 96, 'pix_fmt': 'yuv420p'},
                 'streams': [{'codec_type': 'video', 'color_primaries': 'bt2020'}]}
        session.verify_output(probe)
        for key, wrong in [('pix_fmt', 'yuv420p10le'), ('codec', 'hevc'), ('width', 80)]:
            changed = copy.deepcopy(probe); changed['video'][key] = wrong
            with self.assertRaises(AppError): session.verify_output(changed)
        probe['streams'][0]['color_primaries'] = 'bt709'
        with self.assertRaises(AppError): session.verify_output(probe)

    def test_hash_comparison_keeps_pts_duration_and_sample_size(self):
        self.assertNotEqual(frame_hashes('0,0,0,1,16,aaaa'), frame_hashes('0,0,1,1,16,aaaa'))
        self.assertEqual(frame_hashes('#header\n0, 0, 0, 1, 16, aaaa'), ['0,0,0,1,16,aaaa'])


class HardwareNativeFallbackTests(unittest.TestCase):
    setUpClass = fixtures.SequenceCompositingTests.__dict__['setUpClass']
    tearDownClass = fixtures.SequenceCompositingTests.__dict__['tearDownClass']
    setUp = fixtures.SequenceCompositingTests.setUp
    call = fixtures.SequenceCompositingTests.call
    layer = fixtures.SequenceCompositingTests.layer

    def project(self):
        self.layer('seq_main', 'track_video_1', 'red_clip', 'red')
        ops = self.base/'ops.json'; atomic_write_json(ops, {'operations': self.ops})
        self.call('timeline', 'compose', '--project', self.root, '--input', ops)
        value = json.loads((self.root/'project.json').read_text(encoding='utf8'))
        value['settings']['acceleration'] = {'encode': 'prefer', 'decode': 'require'}
        value['settings']['output']['video']['bitrate'] = '2M'
        return value, next(s for s in value['sequences'] if s['id'] == 'seq_main')

    def test_real_cpu_fallback_retains_clock_manifest_and_image_exclusion(self):
        project, sequence = self.project()
        with patch('ai_ad_editor.hardware_acceleration.encoder_candidates', return_value=[]):
            result = render_project(self.root, project, sequence, self.root/'renders/cpu.mkv')
        self.assertEqual(result['acceleration']['status'], 'verified')
        self.assertEqual(result['probe']['video']['pix_fmt'], 'yuv444p')
        self.assertEqual(result['delivery']['clock']['expected_video_frames'], 8)
        self.assertEqual(len(result['acceleration']['attempts']), 1)
        self.assertFalse(result['acceleration']['selected_decoders'])
        self.assertTrue(Path(result['acceleration']['report']).is_file())

    def test_required_unavailable_keeps_old_output_and_failure_report(self):
        project, sequence = self.project(); project['settings']['acceleration']['encode'] = 'require'
        out = self.root/'renders/old.mkv'; out.write_bytes(b'old')
        with patch('ai_ad_editor.hardware_acceleration.encoder_candidates', return_value=[]), self.assertRaises(AppError) as caught:
            render_project(self.root, project, sequence, out)
        self.assertEqual(caught.exception.code, 'HARDWARE_REQUIRED_UNAVAILABLE')
        self.assertEqual(out.read_bytes(), b'old')
        operation = json.loads((self.root/'operations'/f'{caught.exception.operation_id}.json').read_text(encoding='utf8'))
        self.assertEqual(operation['plan']['acceleration']['status'], 'failed')
        self.assertEqual(operation['plan']['acceleration']['attempts'], [])

    def test_dry_run_does_not_probe_or_allocate_hardware(self):
        project, sequence = self.project()
        with patch.object(AccelerationSession, 'prepare', side_effect=AssertionError('unexpected probe')):
            result = render_project(self.root, project, sequence, self.root/'renders/dry.mkv', dry_run=True)
        self.assertEqual(result['plan']['acceleration']['status'], 'planned')

    def test_quality_failure_does_not_fallback_or_publish(self):
        project, sequence = self.project()
        with patch('ai_ad_editor.hardware_acceleration.encoder_candidates', return_value=[]), \
             patch('ai_ad_editor.render.check_output', return_value={'ok': False, 'errors': ['synthetic gate']}), \
             self.assertRaises(AppError) as caught:
            render_project(self.root, project, sequence, self.root/'renders/rejected.mkv')
        self.assertEqual(caught.exception.code, 'RENDER_QUALITY_FAILED')
        report = next((self.root/'renders/diagnostics').glob('acceleration_*/report.json'))
        self.assertEqual(len(json.loads(report.read_text(encoding='utf8'))['attempts']), 1)
        self.assertFalse((self.root/'renders/rejected.mkv').exists())


class HardwareAlphaBoundaryTests(unittest.TestCase):
    setUpClass = alpha_fixtures.DeliveryPrecisionTests.__dict__['setUpClass']
    setUp = alpha_fixtures.DeliveryPrecisionTests.setUp
    author = alpha_fixtures.DeliveryPrecisionTests.author

    def configured(self, mode):
        sequence = self.author()
        self.project['settings']['acceleration'] = {'encode': mode}
        self.project['settings']['output'] = {'container': 'webm',
            'video': {'codec': 'libvpx-vp9', 'pixel_format': 'yuva420p', 'crf': 18, 'bitrate': '2M'},
            'audio': {'codec': 'libopus'}}
        return sequence

    def test_preferred_hardware_keeps_transparency_on_cpu(self):
        sequence = self.configured('prefer')
        result = render_project(self.root, self.project, sequence, self.root/'renders/alpha.webm')
        self.assertIsNone(result['acceleration']['selected_encoder'])
        frames = alpha_fixtures.decode(Path(result['path']), decoder='libvpx-vp9')
        self.assertEqual(len(frames), 10)
        self.assertLess(int(frames[:, :, :, 3].min()), 10)
        self.assertGreater(int(frames[:, :, :, 3].max()), 240)

    def test_required_hardware_refuses_to_flatten_alpha(self):
        sequence = self.configured('require')
        with self.assertRaises(AppError) as caught:
            render_project(self.root, self.project, sequence, self.root/'renders/alpha.webm')
        self.assertEqual(caught.exception.code, 'HARDWARE_REQUIRED_UNAVAILABLE')
        self.assertFalse((self.root/'renders/alpha.webm').exists())
