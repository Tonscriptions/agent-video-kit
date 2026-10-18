from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from ai_ad_editor.ctc_alignment import (conv_grid, frame_boundary, frame_windows,
    map_text, output_frames, read_transcript, timed_units, viterbi)
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_ctc import ENGINE, PROTOCOL, model_files, validate_alignment
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, run_process, sha256_file
from test_local_asr import invoke

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {'model_type': 'wav2vec2', 'architectures': ['Wav2Vec2ForCTC'], 'vocab_size': 4,
          'pad_token_id': 0, 'conv_kernel': [10, 3, 3, 3, 3, 2, 2], 'conv_stride': [5, 2, 2, 2, 2, 2, 2]}


class CtcAlgorithmTests(unittest.TestCase):
    def test_viterbi_matches_independent_enumeration_including_repeats(self):
        rng = np.random.default_rng(82631)
        for target in ([1], [1, 2], [1, 1], [1, 2, 1], [2, 2, 1]):
            frames = 6
            values = rng.random((frames, 3)) + .01
            scores = np.log(values / values.sum(axis=1, keepdims=True))
            best = -float('inf')
            for path in itertools.product(range(3), repeat=frames):
                # Enumerate acoustic labels, collapse repeats first, then blanks.
                collapsed = [c for i, c in enumerate(path) if (i == 0 or c != path[i-1]) and c != 0]
                if collapsed == target:
                    best = max(best, sum(float(scores[t, c]) for t, c in enumerate(path)))
            actual = viterbi(scores, list(target), 0)
            self.assertAlmostEqual(actual['path_log_probability'], best, places=10)
            self.assertEqual([t['token_id'] for t in actual['tokens']], list(target))
            for a, b in zip(actual['tokens'], actual['tokens'][1:]):
                self.assertLessEqual(a['end_frame'], b['start_frame'])
                if a['token_id'] == b['token_id']:
                    self.assertLess(a['end_frame'], b['start_frame'])

    def test_unreachable_repeats_and_negative_infinity_fail(self):
        for scores, ids in ((np.log(np.full((2, 2), .5)), [1, 1]), (np.full((4, 2), -np.inf), [1])):
            with self.assertRaisesRegex(AppError, 'CTC|重复'):
                viterbi(scores, ids, 0)

    def test_invalid_emissions_and_explicit_dp_budget(self):
        for value in (float('nan'), float('inf'), .5):
            scores = np.full((4, 2), -.7)
            scores[1, 1] = value
            with self.assertRaises(AppError):
                viterbi(scores, [1], 0)
        with patch('ai_ad_editor.ctc_alignment.MAX_STATES', 10):
            with self.assertRaises(AppError) as caught:
                viterbi(np.full((4, 2), -.7), [1], 0)
            self.assertEqual(caught.exception.code, 'ALIGNMENT_DP_BUDGET_EXCEEDED')

    def test_viterbi_checkpoints_are_observed(self):
        def stop():
            raise RuntimeError('cancel-observed')
        with self.assertRaisesRegex(RuntimeError, 'cancel-observed'):
            viterbi(np.full((100, 2), -.7), [1], 0, checkpoint=stop)

    def test_source_indices_punctuation_and_explicit_case(self):
        result = map_text('A, a\n中！', {'<pad>': 0, 'a': 1, '中': 2}, 0, case='lower', offset=4)
        self.assertEqual([t['start_char'] for t in result['tokens']], [4, 7, 9])
        self.assertEqual([t['token'] for t in result['tokens']], ['a', 'a', '中'])
        self.assertEqual(''.join(t['text'] for t in result['ignored']), ', \n！')

    def test_oov_expansion_controls_and_empty_text_are_not_silently_removed(self):
        for text in ('臺', 'ß', 'a\u0301', '\x00', '！？ \n'):
            with self.assertRaises(AppError):
                map_text(text, {'<pad>': 0, 'A': 1, 'S': 2}, 0)

    def test_grid_and_long_window_cover_every_frame_once_with_bounded_input(self):
        stride, receptive = conv_grid(CONFIG)
        self.assertEqual((stride, receptive), (320, 400))
        samples = 16000 * 63 + 137
        windows = frame_windows(samples, stride, receptive, window_samples=480000, context_samples=8000)
        retained = [i for w in windows for i in range(w['core_start'], w['core_end'])]
        self.assertEqual(retained, list(range((samples + stride - 1)//stride)))
        for w in windows:
            self.assertEqual(w['sample_start'] % stride, 0)
            self.assertLessEqual(w['sample_end'] - w['sample_start'], 480000)
        self.assertEqual(frame_boundary(0, len(retained), samples, stride, receptive), 0)
        self.assertEqual(frame_boundary(1, len(retained), samples, stride, receptive), 360)
        self.assertEqual(frame_boundary(len(retained), len(retained), samples, stride, receptive), samples)
        self.assertGreater(windows[-1]['right_zero_pad'], 0)

    def test_window_and_adapter_grid_refuse_unsupported_options(self):
        for config in ({**CONFIG, 'add_adapter': True}, {**CONFIG, 'conv_stride': [2]}):
            with self.assertRaises(AppError):
                conv_grid(config)
        for window, context in ((480001, 8000), (400, 8000), (480000, 100)):
            with self.assertRaises(AppError):
                frame_windows(16000, 320, 400, window_samples=window, context_samples=context)

    def test_every_tail_remainder_has_positive_cells_and_exact_source_coverage(self):
        for samples in (*range(1, 641), *(32000 + i for i in range(320))):
            count = output_frames(samples, 320, 400)
            edges = [frame_boundary(i, count, samples, 320, 400) for i in range(count + 1)]
            self.assertEqual((edges[0], edges[-1]), (0, samples))
            self.assertTrue(all(a < b for a, b in zip(edges, edges[1:])))

    def test_timed_whitespace_units_preserve_punctuation_and_repeated_source_ranges(self):
        text = 'AB, AB!'
        chars = [{**t, 'start_sample': 100+i*100, 'end_sample': 180+i*100,
                  'posterior_geometric_mean': .5} for i, t in enumerate(map_text(text, {'<pad>': 0, 'A': 1, 'B': 2}, 0)['tokens'])]
        units = timed_units(text, chars, offset=0, granularity='whitespace')
        self.assertEqual([u['text'] for u in units], ['AB,', 'AB!'])
        self.assertEqual([u['start_char'] for u in units], [0, 4])
        self.assertEqual([(u['start_sample'], u['end_sample']) for u in units], [(100, 280), (300, 480)])


class CtcCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        temp = ROOT / 'product/.runtime/temp'
        temp.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='ctc-', dir=temp)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'中文工程'
        self.assertEqual(invoke('project', 'init', str(self.root))[0], 0)
        self.model = self.base/'model'
        self.model.mkdir()
        for name, value in {'config.json': CONFIG, 'vocab.json': {'<pad>': 0, 'A': 1, 'B': 2, '|': 3},
            'preprocessor_config.json': {'sampling_rate': 16000, 'feature_extractor_type': 'Wav2Vec2FeatureExtractor'},
            'special_tokens_map.json': {'pad_token': '<pad>'}, 'tokenizer_config.json': {'tokenizer_class': 'Wav2Vec2CTCTokenizer'}}.items():
            atomic_write_json(self.model/name, value)
        (self.model/'model.safetensors').write_bytes(b'protocol-only fixture; not model inference evidence')
        self.evidence = self.base/'evidence.txt'
        self.evidence.write_text('internal protocol fixture', encoding='utf-8')
        audio = self.base/'source.wav'
        with wave.open(str(audio), 'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(bytes(64000))
        code, result = invoke('media', 'ingest', '--project', str(self.root), '--input', str(audio))
        self.assertEqual(code, 0, result)
        self.asset_id = result['data']['asset']['id']
        self.transcript = self.base/'text.txt'
        self.transcript.write_text('AB, AB!', encoding='utf-8')
        plan = self.base/'track.json'
        atomic_write_json(plan, {'operations': [{'op': 'add_track', 'track_id': 'captions', 'kind': 'subtitle', 'order': 2}]})
        self.assertEqual(invoke('timeline', 'compose', '--project', str(self.root), '--input', str(plan))[0], 0)
        self.register_options = ['asr', 'adapter', 'register', '--project', str(self.root), '--adapter-id', 'ctc',
            '--engine', ENGINE, '--python-executable', sys.executable, '--model-path', str(self.model), '--evidence', str(self.evidence)]
        self.calls = 0
        self.change = None

    def metadata(self):
        return tuple((self.root/name).read_bytes() for name in ('project.json', 'project.lock.json', 'rights-ledger.json'))

    def register(self):
        code, value = invoke(*self.register_options)
        self.assertEqual(code, 0, value)
        return value

    def options(self):
        return ['subtitle', 'align', '--project', str(self.root), '--asset-id', self.asset_id, '--transcript', str(self.transcript),
            '--adapter-id', 'ctc', '--output', 'assets/aligned/new.json', '--granularity', 'whitespace']

    def fake_runner(self, argv, **kwargs):
        if not any(str(arg).endswith('ctc_worker.py') for arg in argv):
            return run_process(argv, **kwargs)
        self.calls += 1
        self.assertIn('-I', argv)
        request = json.loads(Path(argv[-1]).read_text(encoding='utf-8'))
        prepared = request['prepared']
        segments = []
        for segment in prepared['segments']:
            end = segment['end_sample'] or 32000
            count = (end - segment['start_sample'] + 319)//320
            chars = []
            for i, token in enumerate(segment['tokens']):
                a, b = 2+i*4, 4+i*4
                chars.append({**token, 'start_frame': a, 'end_frame': b, 'posterior_geometric_mean': .9,
                    'start_sample': segment['start_sample'] + frame_boundary(a, count, end-segment['start_sample'], 320, 400),
                    'end_sample': segment['start_sample'] + frame_boundary(b, count, end-segment['start_sample'], 320, 400)})
            segments.append({**{k: segment[k] for k in ('text', 'start_char', 'end_char', 'ignored')},
                'start_sample': segment['start_sample'], 'end_sample': end, 'frames': count, 'characters': chars,
                'units': timed_units(segment['text'], chars, offset=segment['start_char'], granularity=prepared['granularity'])})
        value = {'protocol': PROTOCOL, 'network': 'disabled', 'status': 'succeeded', 'blocked_network_events': [],
            'request_sha256': 'sha256:'+sha256_file(Path(argv[-1])), 'input_sha256': request['input_sha256'],
            'source_sha256': request['source_sha256'], 'adapter_sha256': request['adapter']['sha256'],
            'alignment': {'format': 'agent-ctc-alignment-v1', **{k: prepared[k] for k in (
                'original_text', 'original_file_text', 'index_basis', 'granularity', 'case', 'stride_samples', 'receptive_samples')},
                'sample_rate': 16000, 'samples': 32000, 'segments': segments}}
        if self.change:
            self.change(value, request)
        atomic_write_json(Path(request['response']), value)
        return subprocess.CompletedProcess(argv, 0, '', '')

    def test_registration_dry_run_and_inspection_do_not_change_metadata(self):
        before = self.metadata()
        self.assertEqual(invoke(*self.register_options, '--dry-run')[0], 0)
        self.assertEqual(self.metadata(), before)
        self.register()
        before = self.metadata()
        code, value = invoke('asr', 'adapter', 'inspect', '--project', str(self.root), '--adapter-id', 'ctc')
        self.assertEqual(code, 0, value)
        self.assertTrue(value['data']['verification']['ok'])
        self.assertTrue(any(x['role'] == 'implementation' for x in value['data']['adapter']['artifacts']))
        self.assertEqual(self.metadata(), before)

    def test_ctc_rejects_pickle_custom_code_duplicate_vocab_and_grid(self):
        baseline = (self.model/'config.json').read_bytes()
        for name in ('weights.bin', 'custom.py', 'hook.pth'):
            path = self.model/name
            path.write_bytes(b'unsafe')
            self.assertEqual(invoke(*self.register_options)[0], 10)
            path.unlink()
        for config in ({**CONFIG, 'auto_map': {'x': 'module.Class'}}, {**CONFIG, 'vocab_size': 9}, {**CONFIG, 'add_adapter': True}):
            atomic_write_json(self.model/'config.json', config)
            self.assertEqual(invoke(*self.register_options)[0], 10)
        (self.model/'config.json').write_bytes(baseline)
        (self.model/'vocab.json').write_text('{"A":1,"A":2}', encoding='utf-8')
        self.assertEqual(invoke(*self.register_options)[0], 10)

    def test_alignment_dry_run_does_not_decode_or_infer(self):
        self.register()
        before = self.metadata()
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            code, value = invoke(*self.options(), '--dry-run')
        self.assertEqual(code, 0, value)
        runner.assert_not_called()
        self.assertEqual(self.metadata(), before)
        self.assertFalse((self.root/'assets/aligned/new.json').exists())

    def test_protocol_applies_repeated_words_exact_source_indices_and_parent_rights(self):
        self.register()
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=self.fake_runner):
            code, value = invoke(*self.options(), '--apply', '--track-id', 'captions', '--timeline-start-tick', '9000')
        self.assertEqual(code, 0, value)
        data = value['data']
        self.assertEqual(self.calls, 1)
        self.assertTrue(data['validation']['ok'])
        words = data['generated_clips'][0]['subtitle']['word_timing']
        self.assertEqual([w['start_char'] for w in words], [0, 4])
        self.assertEqual([w['text'] for w in words], ['AB,', 'AB!'])
        self.assertEqual(len(data['registered_assets']), 3)
        self.assertEqual(Path(data['transcript_copy']).read_bytes(), self.transcript.read_bytes())
        ledger = json.loads((self.root/'rights-ledger.json').read_text(encoding='utf-8'))
        serialized = json.dumps(ledger)
        self.assertIn('asr_adapter_ctc', serialized)
        self.assertEqual(invoke('rights', 'check', '--project', str(self.root))[0], 7)

    def test_bad_bindings_time_grid_and_text_rollback_without_assets(self):
        self.register()
        before = self.metadata()
        changes = [lambda v, r: v.update(request_sha256='sha256:bad'),
            lambda v, r: v['alignment']['segments'][0]['characters'][0].update(start_sample=500),
            lambda v, r: v['alignment']['segments'][0]['characters'][0].update(text='B'),
            lambda v, r: v['alignment']['segments'][0]['units'][0].update(start_char=4),
            lambda v, r: v.update(blocked_network_events=['socket.connect'])]
        for change in changes:
            self.change = change
            with patch('ai_ad_editor.local_ctc.run_process', side_effect=self.fake_runner):
                code, value = invoke(*self.options())
            self.assertEqual(code, 6, value)
            self.assertEqual(self.metadata(), before)
            self.assertFalse((self.root/'assets/aligned/new.json').exists())

    def test_post_write_validation_failure_restores_metadata_and_removes_three_outputs(self):
        self.register()
        before = self.metadata()
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=self.fake_runner), patch('ai_ad_editor.ctc_cli.validate_project', return_value={'ok': False}):
            code, value = invoke(*self.options(), '--apply', '--track-id', 'captions')
        self.assertEqual(code, 2, value)
        self.assertEqual(self.metadata(), before)
        self.assertFalse(any((self.root/'assets/aligned').glob('*')))

    def test_existing_output_is_preserved_without_worker(self):
        self.register()
        output = self.root/'assets/aligned/new.srt'
        output.parent.mkdir(parents=True)
        output.write_bytes(b'existing')
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            code, value = invoke(*self.options())
        self.assertEqual(code, 2, value)
        runner.assert_not_called()
        self.assertEqual(output.read_bytes(), b'existing')

    def test_locked_track_and_highlight_quota_fail_before_worker(self):
        self.register()
        path=self.root/'project.json'
        project=json.loads(path.read_text(encoding='utf-8'))
        project['sequences'][0]['tracks'][-1]['locked']=True
        atomic_write_json(path,project)
        before=self.metadata()
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            self.assertEqual(invoke(*self.options(),'--apply','--track-id','captions')[0],2)
        runner.assert_not_called();self.assertEqual(self.metadata(),before)
        project['sequences'][0]['tracks'][-1]['locked']=False
        atomic_write_json(path,project)
        self.transcript.write_text('A '*129,encoding='utf-8')
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            code,value=invoke(*self.options(),'--apply','--track-id','captions')
        self.assertEqual(code,2,value);runner.assert_not_called()

    def test_late_project_io_error_rolls_back_three_files_and_metadata(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.local_ctc.run_process',side_effect=self.fake_runner), patch('ai_ad_editor.ctc_cli.save_project',side_effect=OSError('fixture disk error')):
            code,value=invoke(*self.options())
        self.assertEqual(code,9,value)
        self.assertIn('ALIGNMENT_IO_FAILED',json.dumps(value))
        self.assertEqual(self.metadata(),before)
        self.assertFalse(any((self.root/'assets/aligned').glob('*')))

    def test_ctc_cannot_be_used_as_whisper(self):
        self.register()
        code, value = invoke('subtitle', 'transcribe', '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'ctc')
        self.assertEqual(code, 2, value)

    def test_srt_strict_parse_windows_and_canonical_source_indices(self):
        path = self.base/'cues.srt'
        path.write_text('1\n00:00:00,100 --> 00:00:00,900\nAB!\n\n2\n00:00:01,000 --> 00:00:02,000\nAB,\n', encoding='utf-8')
        parsed = read_transcript(path)
        self.assertEqual(parsed['original_text'], 'AB!\nAB,')
        self.assertEqual(parsed['segments'][1]['start_char'], 4)
        self.assertEqual(parsed['segments'][0]['start_sample'], 1600)
        path.write_text('1\n-00:00:00,100 --> 00:00:01,000\nAB\n', encoding='utf-8')
        with self.assertRaises(AppError):
            read_transcript(path)
        path.write_text('1\n00:00:00,000 --> 00:00:01,000\nAB\n\nnot a cue', encoding='utf-8')
        with self.assertRaises(AppError):
            read_transcript(path)

    def test_cancel_and_timeout_and_unknown_character_do_not_commit(self):
        self.register()
        before = self.metadata()
        cancel = self.base/'cancel.flag'
        cancel.touch()
        code, value = invoke(*self.options(), '--cancel-file', str(cancel))
        self.assertEqual(code, 8, value)
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=AppError('PROCESS_TIMEOUT', 'fixture timeout', exit_code=6)):
            self.assertEqual(invoke(*self.options())[0], 6)
        self.transcript.write_text('臺', encoding='utf-8')
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            self.assertEqual(invoke(*self.options())[0], 2)
        runner.assert_not_called()
        self.assertEqual(self.metadata(), before)

    def test_model_tampering_rejected_before_worker(self):
        self.register()
        (self.model/'model.safetensors').write_bytes(b'changed')
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            code, value = invoke(*self.options())
        self.assertEqual(code, 10, value)
        runner.assert_not_called()

    def test_idempotent_replay_runs_worker_once_and_changed_transcript_conflicts(self):
        self.register()
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=self.fake_runner):
            first_code, first = invoke(*self.options(), '--idempotency-key', 'alignment-once')
            second_code, second = invoke(*self.options(), '--idempotency-key', 'alignment-once')
        self.assertEqual((first_code, second_code), (0, 0), (first, second))
        self.assertEqual(self.calls, 1)
        self.assertEqual(first['operation_id'], second['operation_id'])
        self.assertIn('IDEMPOTENT_REPLAY', json.dumps(second))
        before = self.metadata()
        self.transcript.write_text('BA', encoding='utf-8')
        code, value = invoke(*self.options(), '--idempotency-key', 'alignment-once')
        self.assertEqual(code, 2, value)
        self.assertIn('IDEMPOTENCY_CONFLICT', json.dumps(value))
        self.assertEqual(self.metadata(), before)

    def test_native_read_locks_deny_model_and_transcript_changes_during_worker(self):
        self.register()
        def attempted_write(value, request):
            for path in (self.model/'model.safetensors', self.transcript):
                with self.assertRaises(PermissionError):
                    path.write_bytes(b'changed')
        self.change = attempted_write
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=self.fake_runner):
            code, value = invoke(*self.options())
        self.assertEqual(code, 0, value)


if __name__ == '__main__':
    unittest.main()
