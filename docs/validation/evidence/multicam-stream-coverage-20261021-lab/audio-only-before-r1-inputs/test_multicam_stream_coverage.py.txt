"""Use actual video display intervals rather than a longer audio/container tail."""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.multicam import _video_coverage, build_switch_segments
from ai_ad_editor.native_video_index import IndexContext
from ai_ad_editor.project import load_project, save_project
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.reverse_video_clock import probe_frames
from ai_ad_editor.utils import sha256_file
import test_cfr_boundaries as helpers
from test_magnetic_reorder import invoke


def sync(left, right, *, version='0.3.0'):
    return {'sync_version': version, 'reference_asset_id': 'reference',
        'sources': [{'asset_id': 'reference'}, {'asset_id': 'camera'}],
        'offsets': [
            {'asset_id': 'reference', 'relative_delay_seconds': 0.,
                'evidence': {'duration_seconds': 2., 'video_coverage': {'start_seconds': 0., 'end_seconds': 2.}}},
            {'asset_id': 'camera', 'relative_delay_seconds': 0.,
                'evidence': {'duration_seconds': 2., 'video_coverage': {'start_seconds': left, 'end_seconds': right}}}]}


class MulticamStreamCoverageTests(unittest.TestCase):
    def plan(self, report, left=0., right=2., **options):
        return build_switch_segments(report, end_seconds=2., switch_plan=[
            {'camera_asset_id': 'camera', 'start_seconds': left, 'end_seconds': right}], **options)

    def test_default_rejects_audio_tail_after_last_video_interval(self):
        with self.assertRaises(AppError) as caught:
            self.plan(sync(0., .32))
        self.assertEqual(caught.exception.code, 'MULTICAM_SOURCE_SHORTFALL')

    def test_trim_keeps_the_actual_video_end_without_slowing(self):
        rows, _ = self.plan(sync(0., .32), source_shortfall='trim')
        self.assertEqual((rows[0]['source_out_seconds'], rows[0]['duration_seconds'], rows[0]['speed']), (.32, .32, 1.))

    def test_default_rejects_audio_prefix_before_first_video_interval(self):
        with self.assertRaises(AppError) as caught:
            self.plan(sync(1., 1.32))
        self.assertEqual(caught.exception.code, 'MULTICAM_SOURCE_SHORTFALL')

    def test_trim_preserves_both_native_video_edges_and_original_reference_position(self):
        rows, _ = self.plan(sync(1., 1.32), source_shortfall='trim')
        row = rows[0]
        self.assertEqual((row['timeline_start_seconds'], row['duration_seconds']), (1., .32))
        self.assertEqual((row['source_in_seconds'], row['source_out_seconds'], row['speed']), (1., 1.32, 1.))

    def test_wholly_empty_video_range_refuses_all_policies_even_though_audio_exists(self):
        for policy in ('reject', 'trim', 'stretch'):
            with self.subTest(policy=policy):
                with self.assertRaises(AppError) as caught:
                    self.plan(sync(0., .32), left=1., right=1.5, source_shortfall=policy)
                self.assertEqual(caught.exception.code, 'MULTICAM_SOURCE_RANGE_EMPTY')

    def test_complete_native_range_is_an_unchanged_unity_speed_control(self):
        rows, _ = self.plan(sync(0., 2.))
        row = rows[0]
        self.assertEqual((row['source_in_seconds'], row['source_out_seconds'], row['speed']), (0., 2., 1.))

    def test_current_protocol_refuses_missing_native_evidence(self):
        report = sync(0., 2.)
        del report['offsets'][1]['evidence']['video_coverage']
        with self.assertRaises(AppError) as caught:
            self.plan(report)
        self.assertEqual(caught.exception.code, 'MULTICAM_VIDEO_COVERAGE_UNKNOWN')

    def test_malformed_native_evidence_never_falls_back_to_container_duration(self):
        for left, right in ((0., float('nan')), (0., float('inf')), (-1., 1.), (1., 1.), (True, 2.)):
            with self.subTest(left=left, right=right):
                with self.assertRaises(AppError) as caught:
                    self.plan(sync(left, right))
                self.assertEqual(caught.exception.code, 'MULTICAM_VIDEO_COVERAGE_UNKNOWN')

    def test_explicit_stretch_clamps_to_first_video_frame_and_reports_changed_clock(self):
        rows, warnings = self.plan(sync(1., 1.32), source_shortfall='stretch')
        row = rows[0]
        self.assertEqual((row['source_in_seconds'], row['source_out_seconds'], row['speed']), (1., 1.32, .16))
        self.assertEqual(row['timeline_start_seconds'], 0.)
        self.assertIn('MULTICAM_SOURCE_CLOCK_CHANGED', [row['code'] for row in warnings])

    def test_legacy_container_only_function_input_is_explicitly_warned(self):
        report = sync(0., 2., version='0.2.0')
        del report['offsets'][1]['evidence']['video_coverage']
        rows, warnings = self.plan(report)
        self.assertEqual(rows[0]['coverage_basis'], 'legacy-container-duration')
        self.assertIn('MULTICAM_LEGACY_CONTAINER_COVERAGE', [row['code'] for row in warnings])

    def test_native_video_bounds_are_mapped_through_the_audio_relative_delay(self):
        report = sync(1., 1.32)
        report['offsets'][1]['relative_delay_seconds'] = .2
        rows, _ = self.plan(report, source_shortfall='trim')
        self.assertEqual((rows[0]['start_seconds'], rows[0]['end_seconds'], rows[0]['speed']), (.8, 1.12, 1.))


class NativeVideoCoverageClockTests(unittest.TestCase):
    def coverage(self, pts, durations, native='1/1000', origin='0', *, actual_hash=None):
        digest = 'f' * 64
        result = (array('q', pts), array('q', durations), {'time_base': native}, {'start_time': origin})
        with patch('ai_ad_editor.reverse_video_clock.probe_frames', return_value=result), \
                patch('ai_ad_editor.multicam.sha256_file', return_value=digest if actual_hash is None else actual_hash):
            return _video_coverage(Path('E:/native-video-coverage-unit-input'), 'sha256:' + digest)

    def test_fractional_display_intervals_preserve_exact_rational_end(self):
        row = self.coverage([0, 1001], [1001, 1001], native='1/30000')
        self.assertEqual((row['start_seconds_rational'], row['end_seconds_rational']), ('0', '1001/15000'))

    def test_nonzero_demux_origin_uses_the_same_native_tick_rounding_as_render(self):
        row = self.coverage([6117, 6397], [40, 40], origin='5.117123')
        self.assertEqual((row['start_seconds_rational'], row['end_seconds_rational']), ('1', '33/25'))
        self.assertEqual(row['demux_origin_native_pts'], 5117)

    def test_unknown_last_frame_duration_is_an_explicit_refusal(self):
        with self.assertRaises(AppError) as caught:
            self.coverage([0, 40], [40, 0])
        self.assertEqual(caught.exception.code, 'MULTICAM_VIDEO_COVERAGE_UNKNOWN')

    def test_invalid_native_time_base_is_an_explicit_refusal(self):
        with self.assertRaises(AppError) as caught:
            self.coverage([0, 40], [40, 40], native='0/1')
        self.assertEqual(caught.exception.code, 'MULTICAM_VIDEO_COVERAGE_UNKNOWN')

    def test_changed_source_digest_never_accepts_the_probed_intervals(self):
        with self.assertRaises(AppError) as caught:
            self.coverage([0, 40], [40, 40], actual_hash='0' * 64)
        self.assertEqual(caught.exception.code, 'MULTICAM_SOURCE_CHANGED')


class NativeMulticamStreamCoverageTests(unittest.TestCase):
    setUp = helpers.CFRBoundaryTests.setUp
    run_native = helpers.CFRBoundaryTests.run_native
    source = helpers.CFRBoundaryTests.source
    project = helpers.CFRBoundaryTests.project
    render = helpers.CFRBoundaryTests.render

    def pair(self, *, delayed=False):
        video, colors, _ = self.source(count=50)
        rng = random.Random(62731)
        gains = [.1 + .75 * rng.random() for _ in range(100)]
        pcm = array('f')
        for sample in range(96000):
            gain = gains[sample // 960]
            pcm.extend((gain * math.sin(2 * math.pi * 433 * sample / 48000),
                gain * math.sin(2 * math.pi * 739 * sample / 48000)))
        audio = self.work / 'source-audio.f32le'
        audio.write_bytes(pcm.tobytes())
        reference = self.work / 'reference.mkv'
        self.run_native([ffmpeg_path(), '-v', 'error', '-i', video, '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', audio,
            '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'pcm_f32le', reference])
        candidate = self.work / 'camera.mkv'
        expression = 'trim=start_frame=0:end_frame=8,setpts=PTS-STARTPTS' + ('+1/TB' if delayed else '')
        self.run_native([ffmpeg_path(), '-v', 'error', '-i', reference, '-filter_complex', '[0:v]' + expression + '[v]',
            '-map', '[v]', '-map', '0:a', '-c:v', 'ffv1', '-pix_fmt', 'bgra', '-c:a', 'copy', candidate])
        p, sequence, clip = self.project(reference, rate='25', start=0, duration=180000, source_out=180000)
        reference_id = clip['asset_id']
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', candidate)
        self.assertEqual(code, 0, result)
        camera_id = result['data']['asset']['id']
        p = load_project(self.root)[1]
        sequence = p['sequences'][0]
        sequence['duration_tick'] = 180000
        sequence['tracks'][0]['clips'] = []
        audio_track = next(track for track in sequence['tracks'] if track['kind'] == 'audio')
        audio_track['clips'] = [{'id': 'master_audio', 'asset_id': reference_id,
            'timeline_start_tick': 0, 'duration_tick': 180000, 'source_in_tick': 0, 'source_out_tick': 180000}]
        save_project(self.root, p)
        plan = self.root / 'camera-plan.json'
        plan.write_text(json.dumps([{'start_seconds': 0., 'end_seconds': 2., 'camera_asset_id': camera_id}]), encoding='utf8')
        common = ('media', 'multicam', '--project', self.root, '--source-asset-id', reference_id,
            '--source-asset-id', camera_id, '--reference-asset-id', reference_id,
            '--sample-rate', '8000', '--analysis-seconds', '2', '--max-offset-seconds', '.4',
            '--switch-plan', plan, '--start-seconds', '0', '--end-seconds', '2',
            '--track-id', sequence['tracks'][0]['id'], '--output', self.root / 'validation/coverage.json')
        return common, colors, pcm.tobytes()

    def test_real_container_with_long_audio_refuses_default_full_window_without_writes(self):
        common, _, _ = self.pair()
        before = (self.root / 'project.json').read_bytes()
        files = {path.relative_to(self.root).as_posix() for path in self.root.rglob('*') if path.is_file()}
        code, result = invoke(*common, '--apply', '--dry-run')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['errors'][0]['code'], 'MULTICAM_SOURCE_SHORTFALL')
        self.assertEqual((self.root / 'project.json').read_bytes(), before)
        self.assertEqual({path.relative_to(self.root).as_posix() for path in self.root.rglob('*') if path.is_file()}, files)

    def test_real_trim_reports_actual_video_end_instead_of_two_second_container(self):
        common, _, _ = self.pair()
        code, result = invoke(*common, '--source-shortfall', 'trim', '--dry-run')
        self.assertEqual(code, 0, result)
        row = result['data']['plan']['segments'][0]
        self.assertEqual((row['source_out_seconds'], row['duration_seconds'], row['speed']), (.32, .32, 1.))

    def verify_applied_trim(self, *, delayed):
        common, colors, pcm = self.pair(delayed=delayed)
        code, result = invoke(*common, '--source-shortfall', 'trim', '--apply', '--replace-track')
        self.assertEqual(code, 0, result)
        row = result['data']['plan']['segments'][0]
        start = 1. if delayed else 0.
        self.assertEqual((row['timeline_start_seconds'], row['source_in_seconds'], row['source_out_seconds'], row['speed']),
            (start, start, start + .32, 1.))
        p = load_project(self.root)[1]
        sequence = p['sequences'][0]
        self.assertEqual(sequence['duration_tick'], 180000)
        frames, _, _ = self.render(p, sequence)
        expected = [(0, 0, 0, 255)] * (25 if delayed else 0) + colors[:8] + [(0, 0, 0, 255)] * (17 if delayed else 42)
        self.assertEqual(frames, [bytes(color) * (helpers.W * helpers.H) for color in expected])
        inputs, graph, _, _ = build_filter_graph(self.root, p, sequence)
        actual_pcm = self.run_native([ffmpeg_path(), '-v', 'error', '-filter_complex_threads', '1', *inputs,
            '-filter_complex', graph, '-map', '[vout]', '-f', 'null', '-', '-map', '[aout]',
            '-c:a', 'pcm_f32le', '-ar', '48000', '-ac', '2', '-f', 'f32le', 'pipe:1'])
        self.assertEqual(actual_pcm, pcm)

    def test_real_tail_trim_keeps_every_video_frame_background_and_master_pcm(self):
        self.verify_applied_trim(delayed=False)

    def test_real_leading_trim_keeps_both_gaps_every_video_frame_and_master_pcm(self):
        self.verify_applied_trim(delayed=True)

    def warm_indexes(self):
        p = load_project(self.root)[1]
        context = IndexContext(self.root, persist=True)
        entries = []
        for asset in p['assets']:
            if asset['kind'] != 'video':
                continue
            source = Path(asset['uri'])
            if not source.is_absolute():
                source = self.root / source
            entries.append(context.acquire(source, 'sha256:' + sha256_file(source), probe_frames)[-1])
        self.assertEqual(len(entries), 2)
        return entries

    def test_real_dry_run_reads_verified_native_indexes_without_writes(self):
        common, _, _ = self.pair()
        self.warm_indexes()
        before = {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()}
        code, result = invoke(*common, '--source-shortfall', 'trim', '--dry-run')
        self.assertEqual(code, 0, result)
        for row in result['data']['plan']['sync']['offsets']:
            index = row['evidence']['video_coverage']['native_index']
            self.assertEqual((index['status'], index['source_index_decode_calls']), ('cache-hit', 0))
        self.assertEqual(before, {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()})

    def test_real_corrupt_native_index_refuses_without_author_writes_or_repair(self):
        common, _, _ = self.pair()
        entry = self.warm_indexes()[0]
        pts = Path(entry['path']) / 'pts.i64le'
        value = bytearray(pts.read_bytes())
        value[0] ^= 1
        pts.write_bytes(value)
        before = {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()}
        code, result = invoke(*common, '--apply', '--dry-run')
        self.assertEqual(code, 6, result)
        self.assertEqual(result['errors'][0]['code'], 'NATIVE_INDEX_CORRUPT')
        self.assertEqual(before, {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()})

    def test_unknown_video_eof_still_returns_audio_only_sync_diagnostics(self):
        common, _, _ = self.pair()
        command = list(common)
        index = command.index('--switch-plan')
        del command[index:index + 2]
        before = {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()}
        with patch('ai_ad_editor.multicam._video_coverage', side_effect=AppError('MULTICAM_VIDEO_COVERAGE_UNKNOWN', 'unknown last display duration', exit_code=2)):
            code, result = invoke(*command, '--dry-run')
        self.assertEqual(code, 0, result)
        plan = result['data']['plan']
        self.assertEqual(plan['segments'], [])
        self.assertFalse(plan['changed'])
        for row in plan['sync']['offsets']:
            self.assertEqual(row['evidence']['video_coverage']['status'], 'unknown')
        self.assertIn('MULTICAM_VIDEO_COVERAGE_UNKNOWN', [row['code'] for row in plan['warnings']])
        self.assertEqual(before, {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()})

    def test_unknown_video_eof_still_refuses_requested_switch_without_writes(self):
        common, _, _ = self.pair()
        before = {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()}
        with patch('ai_ad_editor.multicam._video_coverage', side_effect=AppError('MULTICAM_VIDEO_COVERAGE_UNKNOWN', 'unknown last display duration', exit_code=2)):
            code, result = invoke(*common, '--apply', '--dry-run')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['errors'][0]['code'], 'MULTICAM_VIDEO_COVERAGE_UNKNOWN')
        self.assertEqual(before, {path.relative_to(self.root).as_posix(): sha256_file(path) for path in self.root.rglob('*') if path.is_file()})


if __name__ == '__main__':
    unittest.main()
