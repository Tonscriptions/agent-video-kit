from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.subtitle_segments import (SOURCE_FORMAT, UPSTREAM, checked_source, checked_rules,
    checked_corrections, segment_source, display_cues, srt_text, load_source)
from ai_ad_editor.utils import atomic_write_json

TPS = 90000
TEXT = '它叫 OpenFilm，免费开源，MIT 协议。'


def source(text=TEXT, duration=315000, *, start=0, **extra):
    return {'format': SOURCE_FORMAT, 'ticks_per_second': TPS, 'lines': [
        {'id': 'ad', 'text': text, 'start_tick': start, 'end_tick': start + duration, **extra}]}


def invoke(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, json.loads(output.getvalue())


class SubtitleSegmentPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def test_cjk_clauses_keep_source_punctuation_and_display_convention(self):
        original = source()
        before = copy.deepcopy(original)
        result = segment_source(original)
        self.assertEqual(original, before)
        self.assertEqual([p['text'] for p in result['pieces']], ['它叫 OpenFilm，', '免费开源，', 'MIT 协议。'])
        self.assertEqual([p['display_text'] for p in result['pieces']], ['它叫 OpenFilm', '免费开源', 'MIT 协议'])
        self.assertEqual(result['source'], original)
        self.assertEqual(result['pieces'][0]['start_tick'], 0)
        self.assertEqual(result['pieces'][-1]['end_tick'], 315000)
        self.assertEqual(result['pieces'][1]['start_tick'], result['pieces'][0]['end_tick'])
        self.assertTrue(all(p['timing_basis'] == 'estimated-from-line' for p in result['pieces']))

    def test_english_abbreviations_initials_and_decimal_units_are_not_sentences(self):
        text = 'Mr. Smith arrived at 3.5 s, e.g. right on time, and we started the demo.'
        r = segment_source(source(text, 540000))
        self.assertEqual([p['display_text'] for p in r['pieces']], [
            'Mr. Smith arrived at 3.5 s,', 'e.g. right on time,', 'and we started the demo.'])

    def test_number_unit_and_latin_words_survive_tight_width(self):
        r = segment_source(source('it took 3.5 s to render the whole thing', 450000), rules={'maxChars': 12})
        self.assertTrue(any('3.5 s' in p['text'] for p in r['pieces']))
        self.assertTrue(any('render' in p['text'] for p in r['pieces']))
        for p in r['pieces']:
            a, b = p['from'], p['to']
            self.assertFalse(a > 0 and r['source']['lines'][0]['text'][a - 1].isalpha() and p['text'][0].isalpha())
            self.assertEqual(r['source']['lines'][0]['text'][a:b], p['text'])

    def test_pause_marks_keep_given_word_onsets(self):
        marks = [{'index': i, 'start_tick': t * 90} for i, t in zip([0, 4, 8, 14, 19, 24], [0, 300, 600, 1700, 2000, 2300])]
        r = segment_source(source('one two three four five six', 252000, marks=marks))
        self.assertEqual([(p['start_tick'], p['end_tick']) for p in r['pieces']], [(0, 103680), (153000, 252000)])
        self.assertEqual(r['source']['lines'][0]['marks'], marks)
        self.assertTrue(all(p['timing_basis'] == 'provided-onsets-with-weighted-interiors' for p in r['pieces']))

    def test_unicode_codepoints_emoji_astral_han_combining_and_zwj(self):
        for text in ['🎬 它叫 OpenFilm，免费开源，MIT 协议。', '𠮷野家的新广告，今天正式发布，欢迎观看。',
                     'Cafe\u0301 is ready, and the camera is rolling.', '👩\u200d💻 我们用代码剪片，然后输出新的字幕。']:
            with self.subTest(text=text):
                r = segment_source(source(text, 630000))
                at = 0
                for p in r['pieces']:
                    self.assertFalse(text[at:p['from']].strip())
                    self.assertEqual(text[p['from']:p['to']], p['text'])
                    at = p['to']
                self.assertFalse(text[at:].strip())
                self.assertEqual(r['index_unit'], 'unicode-code-point')

    def test_absolute_ticks_above_double_integer_range_keep_unit_precision(self):
        small = segment_source(source())
        offset = 2**60 + 17
        large = segment_source(source(start=offset))
        self.assertEqual([(p['start_tick'] - offset, p['end_tick'] - offset) for p in large['pieces']],
                         [(p['start_tick'], p['end_tick']) for p in small['pieces']])

    def test_non_millisecond_timebase_and_marks_roundtrip(self):
        s = source('one two three four five six', 300007, start=2**60 + 3,
                   marks=[{'index': i, 'start_tick': 2**60 + 3 + t} for i, t in [(0, 0), (4, 27001), (8, 54002), (14, 153003), (19, 180004), (24, 207005)]])
        s['ticks_per_second'] = 90001
        r = segment_source(s)
        self.assertEqual(r['source'], s)
        self.assertEqual(r['pieces'][-1]['end_tick'], s['lines'][0]['end_tick'])

    def test_quantized_piece_time_cannot_escape_short_original_line(self):
        with self.assertRaises(AppError) as caught:
            segment_source(source('Alpha beta gamma delta', 2), rules={'maxChars': 5, 'minMs': 0})
        self.assertEqual(caught.exception.code, 'SUBTITLE_SEGMENT_TIMING_UNREPRESENTABLE')

    def test_srt_uses_integer_millisecond_rounding_and_rejects_zero_duration(self):
        self.assertIn('00:00:00,001 --> 00:00:00,002', srt_text([{'start_tick': 45, 'end_tick': 135, 'text': 'a'}], TPS))
        with self.assertRaises(AppError) as caught:
            srt_text([{'start_tick': 0, 'end_tick': 1, 'text': 'a'}], TPS)
        self.assertEqual(caught.exception.code, 'SUBTITLE_SEGMENT_SRT_QUANTIZATION')

    def test_supplied_translation_and_bilingual_alignment(self):
        translation = 'It is called OpenFilm. It is free and open source, under the MIT license.'
        r = segment_source(source(translation=translation))
        bilingual = display_cues(r, 'bilingual')
        self.assertEqual(len(bilingual), 3)
        self.assertEqual(bilingual[0]['text'], '它叫 OpenFilm\nIt is called OpenFilm.')
        for p in r['pieces']:
            t = p['translation']
            self.assertEqual(translation[t['from']:t['to']], t['text'])
        self.assertTrue(any(w['code'] == 'SUBTITLE_TRANSLATION_HEURISTIC_ALIGNMENT' for w in r['warnings']))

    def test_shared_translation_merges_contiguous_display_cues(self):
        r = segment_source(source(translation='OK'))
        self.assertEqual(len(display_cues(r, 'original')), 3)
        self.assertEqual(len(display_cues(r, 'translation')), 1)
        self.assertEqual(display_cues(r, 'translation')[0]['parts'], [0, 1, 2])
        self.assertEqual(display_cues(r, 'translation')[0]['end_tick'], 315000)
        with self.assertRaises(AppError):
            segment_source(source(translation='OK'), edits=[{'line_id': 'ad', 'part': 0, 'target': 'translation', 'text': 'Yes'},
                                                           {'line_id': 'ad', 'part': 1, 'target': 'translation', 'text': 'No'}])

    def test_translation_mode_requires_explicit_translation(self):
        r = segment_source(source())
        with self.assertRaises(AppError):
            display_cues(r, 'bilingual')
        with self.assertRaises(AppError):
            display_cues(r, 'translation')

    def test_multiple_original_span_corrections_and_leading_space(self):
        s = source('  ' + TEXT + '  ')
        r = segment_source(s, edits=[{'line_id': 'ad', 'part': 0, 'text': '它叫 Agent Video Kit'},
                                     {'line_id': 'ad', 'part': 2, 'text': '自由使用。'}])
        self.assertEqual(r['source']['lines'][0]['text'], '它叫 Agent Video Kit，免费开源，自由使用。')
        self.assertEqual(r['original_source'], s)
        self.assertEqual({c['part'] for c in r['corrections']}, {0, 2})

    def test_correction_preserves_unaffected_mark_times_with_nonbmp_prefix(self):
        s = source('🎬 它叫 OpenFilm，免费开源，MIT 协议。', 630000)
        text = s['lines'][0]['text']
        marks = [{'index': text.index('免费'), 'start_tick': 210000}, {'index': text.index('MIT'), 'start_tick': 420000}]
        s['lines'][0]['marks'] = marks
        initial = segment_source(s)
        part = next(p['part'] for p in initial['pieces'] if '免费' in p['text'])
        r = segment_source(s, edits=[{'line_id': 'ad', 'part': part, 'text': '完全开放'}])
        revised = r['source']['lines'][0]
        self.assertTrue(any(m['index'] == revised['text'].index('MIT') and m['start_tick'] == 420000 for m in revised['marks']))
        self.assertIn('完全开放', revised['text'])

    def test_deleting_one_piece_does_not_change_other_spoken_word_onsets(self):
        s = source('one two three, four five six, seven eight nine', 540000,
                   marks=[{'index': i, 'start_tick': t} for i, t in [(0, 0), (4, 27000), (8, 54000), (15, 180000), (20, 207000), (25, 234000), (30, 360000), (36, 387000), (42, 414000)]])
        initial = segment_source(s)
        self.assertEqual(len(initial['pieces']), 3)
        r = segment_source(s, edits=[{'line_id': 'ad', 'part': 1, 'text': ''}])
        line = r['source']['lines'][0]
        self.assertNotIn('four', line['text'])
        self.assertTrue(any(m['start_tick'] == 360000 and m['index'] == line['text'].index('seven') for m in line['marks']))

    def test_invalid_source_types_ranges_order_and_budget_fail_before_worker(self):
        cases = []
        for field, value in [('text', None), ('start_tick', True), ('end_tick', 0), ('marks', {}), ('unknown', 1), ('text', '\ud800')]:
            s = source(); s['lines'][0][field] = value; cases.append(s)
        s = source(); s['lines'].append(copy.deepcopy(s['lines'][0])); cases.append(s)
        s = source(); s['lines'][0]['marks'] = [{'index': 0, 'start_tick': 500}, {'index': 1, 'start_tick': 500}]; cases.append(s)
        s = source('x' * 2001); cases.append(s)
        s = source('a' * 500, translation='b' * 500); cases.append(s)
        with patch('ai_ad_editor.subtitle_segments._worker') as worker:
            for s in cases:
                with self.subTest(value=repr(s)[:100]), self.assertRaises(AppError):
                    segment_source(s)
            worker.assert_not_called()

    def test_invalid_rules_do_not_start_worker(self):
        for rules in [{'maxCells': True}, {'maxChars': 0}, {'minMs': 9000}, {'cost': {'unknown': 1}},
                      {'weight': {'latin': float('nan')}}, {'unknown': 2}, {'msPerCell': -1}]:
            with self.subTest(rules=rules), self.assertRaises(AppError):
                checked_rules(rules)

    def test_correction_hash_and_identity_are_required(self):
        with self.assertRaises(AppError) as caught:
            checked_corrections({'expected_input_sha256': 'old', 'edits': []}, 'current', source())
        self.assertEqual(caught.exception.code, 'SUBTITLE_SEGMENT_STALE_INPUT')
        for edit in [{'line_id': 'missing', 'part': 0, 'text': 'a'}, {'line_id': 'ad', 'part': True, 'text': 'a'}]:
            with self.assertRaises(AppError):
                checked_corrections({'expected_input_sha256': 'a', 'edits': [edit]}, 'a', source())

    def test_node_injection_options_are_removed_before_real_worker(self):
        with patch.dict(os.environ, {'NODE_OPTIONS': '--require definitely-missing-injection.js', 'NODE_PATH': 'missing-injection-directory'}):
            self.assertEqual(len(segment_source(source())['pieces']), 3)

    def test_missing_node_and_changed_upstream_are_explicit_dependency_errors(self):
        with patch.dict(os.environ, {'AI_AD_EDITOR_NODE': 'nonexistent-node.exe'}):
            with self.assertRaises(AppError) as caught:
                segment_source(source())
            self.assertEqual(caught.exception.code, 'SUBTITLE_SEGMENT_NODE_UNAVAILABLE')
        with patch('ai_ad_editor.subtitle_segments.sha256_file', return_value='0' * 64):
            with self.assertRaises(AppError) as caught:
                segment_source(source())
            self.assertEqual(caught.exception.code, 'SUBTITLE_SEGMENT_SOURCE_CHANGED')

    def test_original_vendor_bytes_are_pinned(self):
        import ai_ad_editor.subtitle_segments as module
        path = Path(module.__file__).with_name('openfilm_subtitle_segments.mjs')
        self.assertEqual('sha256:' + hashlib.sha256(path.read_bytes()).hexdigest(), UPSTREAM['sha256'])

    def test_srt_asr_and_saved_report_input_retain_source_text(self):
        with tempfile.TemporaryDirectory(prefix='segment-load-') as folder:
            p = Path(folder)
            (p / 'input.srt').write_text('1\n00:00:01,000 --> 00:00:04,500\n' + TEXT + '\n', encoding='utf-8')
            s, _ = load_source(p / 'input.srt', TPS)
            self.assertEqual(s['lines'][0]['text'], TEXT)
            self.assertEqual(s['lines'][0]['start_tick'], TPS)
            atomic_write_json(p / 'asr.json', {'transcription': {'segments': [{'text': TEXT, 'start': 1, 'end': 4.5}]}})
            a, _ = load_source(p / 'asr.json', TPS)
            self.assertEqual(a, s)
            r = segment_source(a)
            atomic_write_json(p / 'result.json', r)
            same, rules = load_source(p / 'result.json', TPS)
            self.assertEqual(same, s)
            self.assertEqual(rules['maxCells'], 16)


class SubtitleSegmentCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='segment-cli-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '本地字幕项目'
        self.assertEqual(invoke('project', 'init', str(self.root))[0], 0)
        self.input = self.root / 'source.json'
        atomic_write_json(self.input, source())
        self.compose = self.root / 'track.json'
        atomic_write_json(self.compose, {'operations': [{'op': 'add_track', 'kind': 'subtitle', 'track_id': 'captions', 'order': 3}]})
        self.assertEqual(invoke('timeline', 'compose', '--project', str(self.root), '--input', str(self.compose))[0], 0)
        self.options = ['subtitle', 'segment', '--project', str(self.root), '--input', str(self.input),
                        '--output', 'assets/subtitles/segmented.json', '--apply', '--track-id', 'captions']

    def metadata(self):
        return {name: (self.root / name).read_bytes() for name in ('project.json', 'project.lock.json', 'rights-ledger.json')}

    def test_dry_run_has_no_output_metadata_or_snapshot_side_effect(self):
        before = self.metadata()
        files = {p.relative_to(self.root) for p in self.root.rglob('*') if p.is_file()}
        code, result = invoke(*self.options, '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(len(result['data']['plan']['pieces']), 3)
        self.assertEqual(self.metadata(), before)
        self.assertEqual({p.relative_to(self.root) for p in self.root.rglob('*') if p.is_file()}, files)

    def test_apply_registers_source_and_srt_assets_and_clip_rights(self):
        code, result = invoke(*self.options, '--timeline-start-tick', '90000')
        self.assertEqual(code, 0, result)
        assets = result['data']['registered_assets']
        self.assertEqual([a['kind'] for a in assets], ['generated', 'subtitle'])
        ledger = json.loads((self.root / 'rights-ledger.json').read_text(encoding='utf-8'))
        srt_record = next(r for r in ledger['records'] if r['asset_id'] == assets[1]['id'])
        self.assertEqual(srt_record['derived_from'], [assets[0]['id']])
        self.assertTrue(all(c['rights_dependencies'] == [{'rights_ref': assets[1]['id'], 'sha256': assets[1]['sha256']}] for c in result['data']['generated_clips']))
        self.assertEqual(result['data']['generated_clips'][0]['timeline_start_tick'], 90000)
        self.assertEqual(result['data']['generated_clips'][-1]['timeline_start_tick'] + result['data']['generated_clips'][-1]['duration_tick'], 405000)
        self.assertTrue(result['data']['before_snapshot']['snapshot_id'])
        self.assertEqual(invoke('validate', '--project', str(self.root))[0], 0)
        self.assertEqual(invoke('rights', 'check', '--project', str(self.root))[0], 7)

    def test_local_policy_accepts_actual_registered_outputs(self):
        code, result = invoke(*self.options)
        self.assertEqual(code, 0, result)
        code, result = invoke('policy', 'audit', '--project', str(self.root))
        self.assertEqual(code, 0, result)

    def test_formal_export_without_apply_registers_files_without_timeline_edit(self):
        code, result = invoke(*self.options[:-3])
        self.assertEqual(code, 0, result)
        self.assertFalse(result['data']['applied'])
        self.assertEqual(result['data']['generated_clips'], [])
        self.assertEqual(len(result['data']['registered_assets']), 2)

    def test_existing_files_are_never_overwritten(self):
        for suffix in ('srt', 'json'):
            path = self.root / f'assets/subtitles/segmented.{suffix}'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'keep existing bytes')
            before = self.metadata()
            code, _ = invoke(*self.options)
            self.assertNotEqual(code, 0)
            self.assertEqual(path.read_bytes(), b'keep existing bytes')
            self.assertEqual(self.metadata(), before)
            path.unlink()

    def test_overlap_requires_explicit_replace_and_locked_track_rejects(self):
        self.assertEqual(invoke(*self.options)[0], 0)
        next_options = list(self.options)
        next_options[next_options.index('--output') + 1] = 'assets/subtitles/next.json'
        before = self.metadata()
        code, result = invoke(*next_options)
        self.assertEqual(code, 2, result)
        self.assertEqual(result['errors'][0]['code'], 'SUBTITLE_SEGMENT_TRACK_OVERLAP')
        self.assertEqual(self.metadata(), before)
        self.assertEqual(invoke(*next_options, '--replace-track')[0], 0)
        p = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        next(t for t in p['sequences'][0]['tracks'] if t['id'] == 'captions')['locked'] = True
        atomic_write_json(self.root / 'project.json', p)
        next_options[next_options.index('--output') + 1] = 'assets/subtitles/locked.json'
        code, result = invoke(*next_options, '--replace-track')
        self.assertEqual(result['errors'][0]['code'], 'SUBTITLE_SEGMENT_TRACK_LOCKED')

    def test_idempotent_replay_does_not_register_duplicate_assets(self):
        code, first = invoke(*self.options, '--idempotency-key', 'segment-1')
        self.assertEqual(code, 0, first)
        before = self.metadata()
        code, second = invoke(*self.options, '--idempotency-key', 'segment-1')
        self.assertEqual(code, 0, second)
        self.assertEqual(second['operation_id'], first['operation_id'])
        self.assertEqual(self.metadata(), before)
        self.assertTrue(any(w['code'] == 'IDEMPOTENT_REPLAY' for w in second['warnings']))

    def test_changed_rule_file_cannot_replay_old_idempotency_key(self):
        rules = self.root / 'rules.json'
        atomic_write_json(rules, {'maxCells': 16})
        code, result = invoke(*self.options, '--rules', str(rules), '--idempotency-key', 'rules')
        self.assertEqual(code, 0, result)
        atomic_write_json(rules, {'maxCells': 12})
        code, result = invoke(*self.options, '--rules', str(rules), '--idempotency-key', 'rules')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['errors'][0]['code'], 'IDEMPOTENCY_CONFLICT')

    def test_changed_correction_file_cannot_replay_old_idempotency_key(self):
        changes = self.root / 'corrections.json'
        payload = {'expected_input_sha256': 'sha256:' + hashlib.sha256(self.input.read_bytes()).hexdigest(),
                   'edits': [{'line_id': 'ad', 'part': 1, 'text': '完全开放'}]}
        atomic_write_json(changes, payload)
        code, result = invoke(*self.options, '--corrections', str(changes), '--idempotency-key', 'correct')
        self.assertEqual(code, 0, result)
        payload['edits'][0]['text'] = '完全免费'
        atomic_write_json(changes, payload)
        code, result = invoke(*self.options, '--corrections', str(changes), '--idempotency-key', 'correct')
        self.assertEqual(result['errors'][0]['code'], 'IDEMPOTENCY_CONFLICT')

    def test_stale_input_and_remote_input_and_escaped_output_reject_before_execution(self):
        for flag, value in [('--expected-input-sha256', 'sha256:' + '0' * 64), ('--input', 'https://invalid.example/a.json'), ('--output', '../escape.json')]:
            opts = list(self.options)
            if flag in opts:
                opts[opts.index(flag) + 1] = value
            else:
                opts += [flag, value]
            before = self.metadata()
            code, _ = invoke(*opts)
            self.assertNotEqual(code, 0)
            self.assertEqual(self.metadata(), before)

    def test_late_operation_failure_cleans_both_files_and_restores_metadata(self):
        before = self.metadata()
        with patch('ai_ad_editor.cli._operation', side_effect=OSError('injected operation write failure')):
            code, result = invoke(*self.options)
        self.assertEqual(code, 9, result)
        self.assertEqual(result['errors'][0]['code'], 'SUBTITLE_SEGMENT_IO_FAILED')
        self.assertEqual(self.metadata(), before)
        self.assertFalse((self.root / 'assets/subtitles/segmented.json').exists())
        self.assertFalse((self.root / 'assets/subtitles/segmented.srt').exists())

    def test_validation_failure_restores_candidate_ledger_and_files(self):
        before = self.metadata()
        with patch('ai_ad_editor.cli.validate_project', return_value={'ok': False, 'errors': [{'code': 'injected'}]}):
            code, result = invoke(*self.options)
        self.assertEqual(result['errors'][0]['code'], 'SUBTITLE_SEGMENT_APPLY_INVALID')
        self.assertEqual(self.metadata(), before)
        self.assertFalse((self.root / 'assets/subtitles/segmented.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'Native Windows file sharing contract')
    def test_actual_input_cannot_be_rewritten_while_worker_plans(self):
        from ai_ad_editor.subtitle_segments import _worker
        observed = []
        def checked(request):
            with self.assertRaises(PermissionError):
                self.input.write_text('changed during planning', encoding='utf-8')
            observed.append(True)
            return _worker(request)
        with patch('ai_ad_editor.subtitle_segments._worker', side_effect=checked):
            code, result = invoke(*self.options)
        self.assertEqual(code, 0, result)
        self.assertEqual(observed, [True])
        self.assertEqual(json.loads(self.input.read_text(encoding='utf-8')), source())

    def test_source_parent_asset_hash_and_rights_dependencies(self):
        caption = self.root / 'original.srt'
        caption.write_text('1\n00:00:00,000 --> 00:00:03,500\n' + TEXT + '\n', encoding='utf-8')
        code, ingested = invoke('media', 'ingest', '--project', str(self.root), '--input', str(caption))
        self.assertEqual(code, 0, ingested)
        asset = ingested['data']['asset']
        code, result = invoke(*self.options, '--source-asset-id', asset['id'])
        self.assertEqual(code, 0, result)
        self.assertEqual(result['data']['plan']['parent_rights_refs'], [asset['rights_ref']])
        copied = self.root / asset['uri']
        copied.write_text('changed source after registration', encoding='utf-8')
        options = list(self.options)
        options[options.index('--output') + 1] = 'assets/subtitles/hash-reject.json'
        code, result = invoke(*options, '--source-asset-id', asset['id'], '--replace-track')
        self.assertEqual(result['errors'][0]['code'], 'SUBTITLE_SEGMENT_SOURCE_INVALID')
        self.assertFalse((self.root / 'assets/subtitles/hash-reject.json').exists())

    def test_native_package_roundtrip_preserves_report_srt_and_clip_dependencies(self):
        code, result = invoke(*self.options)
        self.assertEqual(code, 0, result)
        archive = self.root / 'exports/subtitles.aevpkg.zip'
        code, exported = invoke('convert', 'export', '--project', str(self.root), '--output', str(archive), '--target-format', 'package')
        self.assertEqual(code, 0, exported)
        restored = self.root.parent / 'restored'
        code, imported = invoke('convert', 'import', '--input', str(archive), '--output', str(restored))
        self.assertEqual(code, 0, imported)
        p = json.loads((restored / 'project.json').read_text(encoding='utf-8'))
        for asset in result['data']['registered_assets']:
            found = next(a for a in p['assets'] if a['id'] == asset['id'])
            self.assertEqual('sha256:' + hashlib.sha256((restored / found['uri']).read_bytes()).hexdigest(), asset['sha256'])
        track = next(t for t in p['sequences'][0]['tracks'] if t['id'] == 'captions')
        self.assertEqual([c['rights_dependencies'] for c in track['clips']], [c['rights_dependencies'] for c in result['data']['generated_clips']])

    def test_real_render_encodes_visible_text_from_segmented_clips(self):
        atomic_write_json(self.input, source('Local captions, local edits, local output.', 180000))
        code, result = invoke(*self.options)
        self.assertEqual(code, 0, result)
        p = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        p['settings']['timebase']['display_fps'] = {'num': 4, 'den': 1}
        for track in p['sequences'][0]['tracks']:
            for clip in track.get('clips', []):
                if 'subtitle' in clip:
                    clip['subtitle']['style']['fontsize'] = 18
        atomic_write_json(self.root / 'project.json', p)
        output = self.root / 'renders/subtitles.mp4'
        code, rendered = invoke('render', '--project', str(self.root), '--output', str(output), '--profile', 'custom', '--width', '320', '--height', '180')
        self.assertEqual(code, 0, rendered)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True).stdout
        self.assertEqual(len(raw), 320 * 180 * 3)
        self.assertGreater(sum(v > 100 for v in raw), 50)


if __name__ == '__main__':
    unittest.main()
