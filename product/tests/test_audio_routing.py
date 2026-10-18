"""Encoded PCM, independent linear samples, and separately wired DSP checks."""
from __future__ import annotations

import array
import copy
import hashlib
import json
import math
import subprocess
import unittest
from pathlib import Path

import test_audio_buses as fixtures
from ai_ad_editor.audio_routing import plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.project import load_project, save_project

TPS, SR = fixtures.TPS, fixtures.SR


def ramp(prop, left, right, interpolation='linear'):
    return {'property': prop, 'keyframes': [
        {'at_tick': 0, 'value': left, 'interpolation': interpolation},
        {'at_tick': 2*TPS, 'value': right}]}


class NamedAudioRoutingTests(fixtures.AudioBusFixture):
    def routing(self, *, tracks=None, buses=None, master=None, seq='seq_main'):
        value = {'version': 1, 'tracks': tracks or [], 'buses': buses or []}
        if master is not None:
            value['master'] = master
        self.ops.append({'op': 'update_sequence', 'sequence_id': seq, 'patch': {'audio_routing': value}})
        return value

    def detector_reference(self, main, detector, options):
        # Independent graph wiring, same FFmpeg DSP implementation. Neither
        # side is an independent algorithm/subjective audio-quality reference.
        a, b = self.base/'main.f32', self.base/'detector.f32'
        a.write_bytes(array.array('f', main).tobytes()); b.write_bytes(array.array('f', detector).tobytes())
        command = ['ffmpeg', '-v', 'error']
        for p in (a, b):
            command += ['-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', str(p)]
        command += ['-filter_complex', '[0:a]aformat=sample_fmts=fltp,asetnsamples=n=1024:p=0[a];'
                    '[1:a]aformat=sample_fmts=fltp,asetnsamples=n=1024:p=0[b];'
                    '[a][b]sidechaincompress='+options+'[out]', '-map', '[out]', '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1']
        raw = subprocess.run(command, capture_output=True, check=True).stdout
        result = array.array('f'); result.frombytes(raw)
        return list(result)

    def test_explicit_default_routes_preserve_float_sum_and_author_project(self):
        self.tone(); self.track('seq_main', 'second'); self.tone(track='second', name='other')
        self.routing()
        actual, _, manifest, _ = self.render()
        self.close_pcm(actual, [a+b for a, b in zip(self.pcm['tone'], self.pcm['other'])])
        routing = next(i for i in manifest['inputs'] if i.get('kind') == 'sequence-audio-routing')
        self.assertEqual(routing['execution_passes'], 1)
        self.assertEqual(routing['output_samples'], 2*SR)
        self.assertFalse(routing['automatic_limiter'])

    def test_two_tracks_share_multilevel_buses_and_master_gain(self):
        self.tone(); self.track('seq_main', 'second'); self.tone(track='second', name='other')
        self.routing(tracks=[{'track_id': t, 'output': 'sub'} for t in ('track_audio_1', 'second')],
                     buses=[{'id': 'sub', 'output': 'parent', 'audio': {'volume': .5}},
                            {'id': 'parent', 'audio': {'volume': .25}}], master={'audio': {'volume': .5}})
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [(a+b)/16 for a, b in zip(self.pcm['tone'], self.pcm['other'])])

    def test_pre_and_post_sends_fan_out_without_changing_dry_gain(self):
        self.tone()
        self.ops.append({'op': 'update_track', 'track_id': 'track_audio_1', 'patch': {'audio': {'volume': .5}}})
        self.routing(tracks=[{'track_id': 'track_audio_1', 'sends': [
            {'bus_id': 'return', 'tap': 'pre_fader', 'gain': .4},
            {'bus_id': 'return', 'tap': 'post_fader', 'gain': .6}]}],
            buses=[{'id': 'return', 'audio': {'volume': .25}}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [v*.675 for v in self.pcm['tone']])

    def test_pre_fader_is_after_track_compressor_and_before_volume(self):
        self.tone()
        self.ops.append({'op': 'update_track', 'track_id': 'track_audio_1', 'patch': {'audio': {
            'volume': .2, 'compressor': {'threshold': .1, 'ratio': 4, 'attack': 1, 'release': 50}}}})
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None, 'sends': [{'bus_id': 'return', 'tap': 'pre_fader'}]}],
                     buses=[{'id': 'return'}])
        actual, _, _, _ = self.render()
        expected = self.reference_filter(self.pcm['tone'], 'acompressor=threshold=0.1:ratio=4:attack=1:release=50')
        self.close_pcm(actual, expected)

    def test_shared_bus_compressor_receives_sum_once(self):
        self.tone(); self.track('seq_main', 'cancel', volume=.5); self.tone(track='cancel', name='negative')
        self.routing(tracks=[{'track_id': t, 'output': 'shared'} for t in ('track_audio_1', 'cancel')],
                     buses=[{'id': 'shared', 'audio': {'compressor': {'threshold': .1, 'ratio': 4, 'attack': 1, 'release': 50}}}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, self.reference_filter([v*.5 for v in self.pcm['tone']],
                                                    'acompressor=threshold=0.1:ratio=4:attack=1:release=50'))

    def test_track_bus_master_and_send_automation_use_sequence_samples(self):
        self.tone(name='dc')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None,
            'keyframes': [ramp('audio.volume', .25, 1)], 'sends': [{'bus_id': 'fx',
            'keyframes': [{'at_tick': 0, 'value': 0, 'interpolation': 'ease_out'}, {'at_tick': 2*TPS, 'value': .5}]}]}],
            buses=[{'id': 'fx', 'keyframes': [ramp('audio.volume', .5, 1)]}], master={'audio': {'volume': .75}})
        actual, _, _, _ = self.render()
        expected = []
        for n in range(2*SR):
            p = n/(2*SR)
            gain = (.25+.75*p)*(.5*(1-(1-p)**2))*(.5+.5*p)*.75
            expected.extend([self.pcm['dc'][2*n]*gain]*2)
        self.close_pcm(actual, expected)

    def test_static_pan_preserves_independent_stereo_through_buses(self):
        self.tone(name='stereo')
        self.ops.append({'op': 'update_track', 'track_id': 'track_audio_1', 'patch': {'audio': {'pan': .5}}})
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': 'balance'}],
            buses=[{'id': 'balance', 'audio': {'pan': -.5}}], master={'audio': {'pan': .25}})
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [v*(.375 if n%2 == 0 else .5) for n, v in enumerate(self.pcm['stereo'])])

    def test_pan_automation_and_bus_fade_are_sample_evaluated(self):
        self.tone(name='stereo')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': 'balance'}],
            buses=[{'id': 'balance', 'audio': {'fade_in': 2}, 'keyframes': [ramp('audio.pan', -1, 1)]}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [v*(n//2/(2*SR))*(1-max(2*(n//2/(2*SR))-1, 0) if n%2 == 0 else
                                    1+min(2*(n//2/(2*SR))-1, 0)) for n, v in enumerate(self.pcm['stereo'])])

    def test_hold_and_bezier_send_points_keep_independent_channels(self):
        self.tone(name='dc')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None, 'sends': [
            {'bus_id': 'fx', 'gain': .3, 'keyframes': [
                {'at_tick': 0, 'value': 0, 'interpolation': 'hold'},
                {'at_tick': TPS, 'value': .5, 'interpolation': 'bezier', 'control_points': [0, 0, 1, 1]},
                {'at_tick': 2*TPS, 'value': 1}]}]}], buses=[{'id': 'fx'}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [v*(0 if n//2 < SR else .5+.5*(n//2-SR)/SR) for n, v in enumerate(self.pcm['dc'])])

    def test_bus_mute_silences_pre_fader_sends_and_detector(self):
        self.tone(); self.track('seq_main', 'music'); self.tone(track='music', name='other')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': 'muted'}, {'track_id': 'music', 'output': 'music'}],
            buses=[{'id': 'muted', 'audio': {'mute': True}, 'sends': [{'bus_id': 'fx', 'tap': 'pre_fader'}]},
                   {'id': 'fx'}, {'id': 'music', 'sidechain': {'bus_id': 'muted', 'tap': 'pre_fader'}}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, self.pcm['other'])

    def test_solo_prunes_dry_bypass_and_unrelated_downstream_inputs(self):
        self.tone(); self.track('seq_main', 'unrelated'); self.tone(track='unrelated', name='other')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'sends': [{'bus_id': 'focus', 'gain': .5}]},
                             {'track_id': 'unrelated', 'output': 'sum'}],
            buses=[{'id': 'focus', 'audio': {'solo': True}, 'output': 'sum'}, {'id': 'sum'}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [v*.5 for v in self.pcm['tone']])

    def test_solo_keeps_full_detector_context_with_non_audible_voice(self):
        self.tone(); self.track('seq_main', 'music'); self.tone(track='music', name='other')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': 'detector'}, {'track_id': 'music', 'output': 'music'}],
            buses=[{'id': 'detector', 'output': None}, {'id': 'music', 'audio': {'solo': True},
                    'sidechain': {'bus_id': 'detector', 'compressor': {'threshold': .05, 'ratio': 8, 'attack': 1, 'release': 50}}}])
        actual, _, manifest, _ = self.render()
        self.close_pcm(actual, self.detector_reference(self.pcm['other'], self.pcm['tone'],
                       'threshold=0.05:ratio=8:attack=1:release=50'))
        entry = next(i for i in manifest['inputs'] if i.get('kind') == 'sequence-audio-routing')
        self.assertTrue(entry['unpruned_detector_context']); self.assertEqual(entry['execution_passes'], 2)

    def test_track_pre_fader_detector_is_independent_of_its_output_volume(self):
        self.tone(); self.track('seq_main', 'music'); self.tone(track='music', name='other')
        self.ops.append({'op': 'update_track', 'track_id': 'track_audio_1', 'patch': {'audio': {'volume': .1}}})
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None}, {'track_id': 'music', 'output': 'music'}],
            buses=[{'id': 'music', 'sidechain': {'track_id': 'track_audio_1', 'tap': 'pre_fader',
                    'compressor': {'threshold': .05, 'ratio': 8, 'attack': 1, 'release': 50}}}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, self.detector_reference(self.pcm['other'], self.pcm['tone'],
                       'threshold=0.05:ratio=8:attack=1:release=50'))

    def test_disconnected_sources_are_drained_and_absent_detector_is_full_length_zero(self):
        self.tone(); self.track('seq_main', 'empty')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': 'music'}],
            buses=[{'id': 'music', 'sidechain': {'track_id': 'empty'}}, {'id': 'zzz_disconnected', 'output': None}])
        actual, _, _, _ = self.render()
        self.close_pcm(actual, self.pcm['tone'])

    def test_empty_graph_and_muted_master_have_exact_silence(self):
        self.routing(master={'audio': {'mute': True}}, buses=[{'id': 'no_input', 'audio': {'reverb': {}}}])
        actual, _, _, _ = self.render()
        self.assertEqual(max(map(abs, actual)), 0)

    def test_rendered_named_nodes_pass_local_policy_without_uri_exemptions(self):
        self.tone(); self.track('seq_main', 'music'); self.tone(track='music', name='other')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None}, {'track_id': 'music', 'output': 'fx'}],
            buses=[{'id': 'fx', 'sidechain': {'track_id': 'track_audio_1'}}])
        self.render()
        result=self.call('policy', 'audit', '--project', self.root)
        self.assertTrue(result['data']['ok'])

    def test_audio_only_routed_child_finishes_compressor_and_gain_before_outer_reverse(self):
        self.sequence('child'); self.tone('child', 'child_audio_1')
        self.routing(seq='child', tracks=[{'track_id': 'child_audio_1', 'output': 'local'}],
            buses=[{'id': 'local', 'audio': {'compressor': {'threshold': .1, 'ratio': 4, 'attack': 1, 'release': 50}},
                    'keyframes': [ramp('audio.volume', 0, 1)]}])
        self.group('child', reverse=True)
        actual, _, manifest, _ = self.render()
        processed = self.reference_filter(self.pcm['tone'], 'acompressor=threshold=0.1:ratio=4:attack=1:release=50')
        frames = [processed[2*n:2*n+2] for n in range(2*SR)]
        expected = [v*n/(2*SR) for n, frame in reversed(list(enumerate(frames))) for v in frame]
        self.close_pcm(actual, expected)
        surface = next(i for i in manifest['inputs'] if i.get('kind') == 'sequence-inline-surface')
        self.assertEqual(surface['audio_path'], 'complete-authored-child-bus')
        self.assertTrue(any(i.get('kind') == 'sequence-audio-routing' for i in surface['inputs']))

    def test_two_instances_have_distinct_time_placement_and_no_author_internal_assets(self):
        self.sequence('child'); self.tone('child', 'child_audio_1')
        self.routing(seq='child', buses=[], tracks=[{'track_id': 'child_audio_1', 'keyframes': [ramp('audio.volume', 0, 1)]}])
        self.group('child'); self.group('child', timeline_start_tick=2*TPS)
        actual, _, _, _ = self.render(duration_tick=4*TPS)
        block = [v*(n//2/(2*SR)) for n, v in enumerate(self.pcm['tone'])]
        self.close_pcm(actual, block+block)

    def test_nested_routing_trim_preserves_child_author_gain_phase(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', name='dc')
        self.routing(seq='child', tracks=[{'track_id': 'child_audio_1', 'keyframes': [ramp('audio.volume', 0, 1)]}])
        self.group('child', source_in_tick=TPS, duration_tick=TPS)
        actual, _, _, _ = self.render()
        self.close_pcm(actual, [v*(.5+n//2/(2*SR)) for n, v in enumerate(self.pcm['dc'][2*SR:])]+[0.]*(2*SR))

    def test_invalid_cycle_compose_is_atomic_and_dry_run_does_not_write(self):
        self.tone(); self.compose(); self.ops=[]
        path = self.root/'project.json'; before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.routing(buses=[{'id': 'a', 'output': 'b'}, {'id': 'b', 'sends': [{'bus_id': 'a', 'gain': 0}]}])
        result = self.compose(expected=2)
        self.assertIn('AUDIO_ROUTING_CYCLE', json.dumps(result))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.ops=[]; self.routing(buses=[{'id': 'a'}])
        changes = self.base/'changes.json'; atomic_write_json(changes, {'operations': self.ops})
        self.call('timeline', 'compose', '--project', self.root, '--input', changes, '--dry-run')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_nested_routed_freeze_inserts_silence_after_authored_bus_processing(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', name='dc')
        self.routing(seq='child', tracks=[{'track_id': 'child_audio_1', 'keyframes': [ramp('audio.volume', 0, 1)]}])
        self.group('child', duration_tick=3*TPS, freeze={'at_tick': TPS, 'duration_tick': TPS, 'audio_mode': 'silence'})
        actual, _, _, _ = self.render(duration_tick=3*TPS)
        block = [v*(n//2/(2*SR)) for n, v in enumerate(self.pcm['dc'])]
        self.close_pcm(actual, block[:2*SR]+[0.]*(2*SR)+block[2*SR:])

    def test_nested_routed_continue_freeze_keeps_original_audio_then_pads_tail(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', name='dc')
        self.routing(seq='child', tracks=[{'track_id': 'child_audio_1', 'keyframes': [ramp('audio.volume', 0, 1)]}])
        self.group('child', duration_tick=3*TPS, freeze={'at_tick': TPS, 'duration_tick': TPS, 'audio_mode': 'continue'})
        actual, _, _, _ = self.render(duration_tick=3*TPS)
        block = [v*(n//2/(2*SR)) for n, v in enumerate(self.pcm['dc'])]
        self.close_pcm(actual, block+[0.]*(2*SR))

    def test_presentation_window_selects_complete_child_mix_and_keeps_bus_gain_phase(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', name='dc')
        self.routing(seq='child', buses=[{'id': 'local', 'keyframes': [ramp('audio.volume', 0, 1)]}],
                     tracks=[{'track_id': 'child_audio_1', 'output': 'local'}])
        self.group('child', reverse=True)
        cid = self.ops[-1]['id']
        self.ops.append({'op': 'trim_clip', 'clip_id': cid, 'start_tick': TPS//2,
                         'end_tick': 3*TPS//2, 'timeline_start_tick': 0})
        actual, _, _, _ = self.render()
        block = [v*(n//2/(2*SR)) for n, v in enumerate(self.pcm['dc'])]
        reverse = [v for n in reversed(range(2*SR)) for v in block[2*n:2*n+2]]
        self.close_pcm(actual, reverse[SR:3*SR]+[0.]*(2*SR))

    def decode(self, path):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                              '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'], capture_output=True, check=True).stdout
        values = array.array('f'); values.frombytes(raw)
        return list(values)

    def test_curved_parent_matches_materialized_completed_child_not_per_leaf_effects(self):
        self.sequence('child'); self.tone('child', 'child_audio_1')
        self.ops.append({'op': 'append_clip', 'sequence_id': 'child', 'track_id': 'child_video_1',
                         'id': 'child_picture', 'asset_id': 'picture', 'source_in_tick': 0,
                         'source_out_tick': 2*TPS, 'duration_tick': 2*TPS})
        self.routing(seq='child', buses=[{'id': 'local', 'audio': {'compressor': {'threshold': .1, 'ratio': 4, 'attack': 1, 'release': 50}},
                                         'keyframes': [ramp('audio.volume', .2, 1)]}],
                     tracks=[{'track_id': 'child_audio_1', 'output': 'local'}])
        duration = round(2*math.log(2)*TPS)
        self.ops.append({'op': 'trim_clip', 'clip_id': 'background', 'end_tick': duration})
        self.group('child', duration_tick=duration, speed_curve={'keyframes': [
            {'at_tick': 0, 'speed': 1}, {'at_tick': 2*TPS, 'speed': 2}]})
        actual, _, _, _ = self.render(duration_tick=duration)
        self.ops=[]
        materialized = self.root/'renders/completed-child.mkv'
        self.call('render', '--project', self.root, '--sequence-id', 'child', '--output', materialized)
        self.call('media', 'ingest', '--project', self.root, '--input', materialized, '--asset-id', 'completed_child')
        _, p = load_project(self.root)
        child = next(s for s in p['sequences'] if s['id'] == 'child')
        child['audio_routing'] = {'version': 1}
        child['tracks'] = [{'id': 'child_audio_1', 'kind': 'audio', 'order': 0, 'clips': [{
            'id': 'completed', 'asset_id': 'completed_child', 'timeline_start_tick': 0,
            'duration_tick': 2*TPS, 'source_in_tick': 0, 'source_out_tick': 2*TPS}]}]
        save_project(self.root, p)
        reference = self.root/'renders/materialized-reference.mkv'
        self.call('render', '--project', self.root, '--output', reference)
        self.close_pcm(actual, self.decode(reference))

    def test_fragment_expands_scope_remaps_track_detectors_and_preserves_samples(self):
        self.tone(); self.track('seq_main', 'music'); self.tone(track='music', name='other')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None}, {'track_id': 'music', 'output': 'fx'}],
            buses=[{'id': 'fx', 'sidechain': {'track_id': 'track_audio_1', 'tap': 'pre_fader'}}])
        expected, _, _, _ = self.render()
        request = self.base/'save.json'
        atomic_write_json(request, {'id': 'routing', 'version': 1, 'sequence_id': 'seq_main', 'clip_ids': ['background']})
        library = self.base/'library'
        result = self.call('fragment', 'save', '--project', self.root, '--library', library, '--input', request)
        self.assertEqual(len(result['data']['fragment']['selection']['expanded']), 2)
        target = self.base/'target'; self.call('project', 'init', target)
        _, source = load_project(self.root); _, p = load_project(target)
        p['settings'] = copy.deepcopy(source['settings']); save_project(target, p)
        atomic_write_json(request, {'id': 'routing', 'version': 1, 'sequence_id': 'seq_main', 'track_id': 'track_video_1', 'at_tick': 0})
        self.call('fragment', 'apply', '--project', target, '--library', library, '--input', request)
        _, p = load_project(target)
        imported = next(s for s in p['sequences'] if s.get('audio_routing'))
        self.assertNotEqual(imported['audio_routing']['buses'][0]['sidechain']['track_id'], 'track_audio_1')
        output = target/'renders/fragment.mkv'; self.call('render', '--project', target, '--output', output)
        self.close_pcm(self.decode(output), expected)

    def test_package_roundtrip_preserves_graph_automation_and_real_pcm(self):
        self.tone(name='stereo')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': 'fx'}],
            buses=[{'id': 'fx', 'keyframes': [ramp('audio.volume', .25, .75), ramp('audio.pan', -.5, .5)]}])
        expected, _, _, _ = self.render()
        package = self.base/'routing.zip'; target = self.base/'unpacked'
        self.call('convert', 'export', '--project', self.root, '--target-format', 'package', '--output', package)
        self.call('convert', 'import', '--input', package, '--output', target)
        _, a = load_project(self.root); _, b = load_project(target)
        self.assertEqual(a['sequences'][0]['audio_routing'], b['sequences'][0]['audio_routing'])
        output = target/'renders/roundtrip.mkv'; self.call('render', '--project', target, '--output', output)
        self.close_pcm(self.decode(output), expected)

    def test_external_exports_explicitly_report_unmapped_audio_routing(self):
        self.tone(); self.routing(buses=[{'id': 'fx'}]); self.compose()
        for format, suffix in (('otio', 'otio'), ('kdenlive-xml', 'mlt'), ('jianying-draft-json', 'json')):
            output = self.base/('external.'+suffix)
            result = self.call('convert', 'export', '--project', self.root, '--target-format', format, '--output', output)
            report = json.loads(json.dumps(result))
            self.assertIn('sequence.audio_routing', json.dumps(report))
            self.assertIn('Unsupported', json.dumps(report))

    def test_unequal_input_packets_and_late_voice_do_not_pad_a_truncated_sidechain_tail(self):
        self.tone(source_in_tick=TPS, duration_tick=TPS, timeline_start_tick=TPS)
        self.track('seq_main', 'music'); self.tone(track='music', name='other')
        self.routing(tracks=[{'track_id': 'track_audio_1', 'output': None}, {'track_id': 'music', 'output': 'music'}],
            buses=[{'id': 'music', 'sidechain': {'track_id': 'track_audio_1',
                'compressor': {'threshold': .05, 'ratio': 8, 'attack': 1, 'release': 50}}}])
        actual, _, _, _ = self.render()
        detector = [0.]*(2*SR)+self.pcm['tone'][2*SR:]
        self.close_pcm(actual, self.detector_reference(self.pcm['other'], detector,
                       'threshold=0.05:ratio=8:attack=1:release=50'))
        self.assertGreater(max(map(abs, actual[-4096:])), .001)


class AudioRoutingContractTests(unittest.TestCase):
    def sequence(self):
        return {'id': 'seq', 'duration_tick': 2*TPS, 'tracks': [{'id': 'audio', 'kind': 'audio', 'clips': []}],
                'audio_routing': {'version': 1, 'buses': [{'id': 'a'}, {'id': 'b'}]}}

    def invalid(self, edit, code='AUDIO_ROUTING_INVALID'):
        value = self.sequence(); edit(value['audio_routing'])
        with self.assertRaises(AppError) as caught:
            plan(value)
        self.assertEqual(caught.exception.code, code)

    def test_missing_references_and_duplicates_are_rejected(self):
        for field in ('output', 'sends', 'sidechain'):
            with self.subTest(field=field):
                self.invalid(lambda r: r['buses'][0].update({field: 'absent' if field == 'output' else
                    [{'bus_id': 'absent'}] if field == 'sends' else {'track_id': 'absent'}}), 'AUDIO_ROUTING_REFERENCE_INVALID')
        self.invalid(lambda r: r['buses'].append({'id': 'a'}))
        self.invalid(lambda r: r.update(tracks=[{'track_id': 'audio'}, {'track_id': 'audio'}]), 'AUDIO_ROUTING_REFERENCE_INVALID')

    def test_output_send_and_detector_cycles_include_zero_gain_edges(self):
        for field in ('output', 'sends', 'sidechain'):
            with self.subTest(field=field):
                self.invalid(lambda r: r['buses'][0].update({field: 'a' if field == 'output' else
                    [{'bus_id': 'a', 'gain': 0}] if field == 'sends' else {'bus_id': 'a'}}), 'AUDIO_ROUTING_CYCLE')

    def test_strict_automation_rejects_unknown_properties_times_and_controls(self):
        cases = [ramp('opacity', 0, 1), ramp('audio.volume', 0, 5), ramp('audio.pan', -2, 1),
                 {'property': 'audio.volume', 'keyframes': [{'at_tick': True, 'value': 1}]},
                 {'property': 'audio.volume', 'keyframes': [{'at_tick': 1, 'value': 1}, {'at_tick': 0, 'value': 1}]},
                 {'property': 'audio.volume', 'keyframes': [{'at_tick': 0, 'value': 1, 'interpolation': 'bezier', 'control_points': [0, 2]}]},
                 {'property': [], 'keyframes': []}]
        for case in cases:
            with self.subTest(case=case):
                self.invalid(lambda r: r['buses'][0].update(keyframes=[case]))

    def test_unknown_fields_invalid_types_injection_and_nonfinite_are_rejected(self):
        cases = [lambda r: r.update(version=True), lambda r: r.update(provider='remote'),
                 lambda r: r['buses'][0].update(audio={'volume': float('nan')}),
                 lambda r: r['buses'][0].update(audio={'pan': 'stereo|c0=c1'}),
                 lambda r: r['buses'][0].update(audio={'compressor': {'ratio': 99}}),
                 lambda r: r['buses'][0].update(audio={'reverb': {'delays': '1;anullsrc'}}),
                 lambda r: r['buses'][0].update(sidechain={'bus_id': 'b', 'track_id': 'audio'}),
                 lambda r: r['buses'][0].update(sends=[{'bus_id': 'b', 'tap': []}]),
                 lambda r: r.update(master={'audio': {'solo': False}})]
        for edit in cases:
            with self.subTest(edit=cases.index(edit)):
                self.invalid(edit)

    def test_node_edge_and_automation_work_budgets_reject_before_execution(self):
        self.invalid(lambda r: r.update(buses=[{'id': 'b'+str(n)} for n in range(127)]), 'AUDIO_ROUTING_BUDGET_EXCEEDED')
        self.invalid(lambda r: r['buses'][0].update(sends=[{'bus_id': 'b'} for _ in range(512)]), 'AUDIO_ROUTING_BUDGET_EXCEEDED')
        self.invalid(lambda r: r.update(buses=[{'id': 'b'+str(n), 'keyframes': [{'property': 'audio.volume', 'keyframes':
            [{'at_tick': i, 'value': 1} for i in range(64)]}]} for n in range(17)]), 'AUDIO_ROUTING_BUDGET_EXCEEDED')

    def test_names_are_local_and_plan_does_not_modify_author_data(self):
        value = self.sequence(); value['audio_routing']['buses'][0]['id']='audio'
        before = copy.deepcopy(value); graph = plan(value)
        self.assertIn('track/audio', graph['nodes']); self.assertIn('bus/audio', graph['nodes'])
        self.assertEqual(value, before)

    def test_collision_lane_clones_linear_routes_without_reusing_different_bus(self):
        import test_magnetic_reorder as edit
        from ai_ad_editor.edit_planner import build_edit_plan
        value = edit.project()
        sequence = value['sequences'][0]
        sequence['tracks'] += [edit.track('voice', [edit.clip('bed', 0, 27), edit.clip('rider', 31, 38)], 'audio', 1),
                               edit.track('free', [], 'audio', 2)]
        sequence['audio_routing'] = {'version': 1, 'tracks': [{'track_id': 'voice', 'output': 'fx',
            'keyframes': [ramp('audio.volume', .2, 1)]}], 'buses': [{'id': 'fx'}]}
        # Scale the shared helper's author keyframes to its ten-tick clock.
        sequence['audio_routing']['tracks'][0]['keyframes'][0]['keyframes'][-1]['at_tick'] = 20
        result, report = build_edit_plan(value, 'seq', edit.request(('d',), options={'linkage': True}))
        target = edit.positions(result)['rider'][0]
        self.assertNotIn(target, ('voice', 'free'))
        rows = result['sequences'][0]['audio_routing']['tracks']
        self.assertEqual({k: v for k, v in rows[-1].items() if k != 'track_id'},
                         {k: v for k, v in rows[0].items() if k != 'track_id'})
        self.assertEqual(rows[-1]['track_id'], target)
        plan(result['sequences'][0])

    def test_collision_rejects_splitting_named_detector_or_tone_state(self):
        import test_magnetic_reorder as edit
        from ai_ad_editor.edit_planner import build_edit_plan
        for mode in ('detector', 'tone', 'sidechain'):
            value = edit.project(); sequence = value['sequences'][0]
            sequence['tracks'].append(edit.track('voice', [edit.clip('bed', 0, 27), edit.clip('rider', 31, 38)], 'audio', 1,
                audio={'compressor': {'ratio': 2}} if mode == 'tone' else {}))
            sequence['audio_routing'] = {'version': 1, 'buses': [{'id': 'fx'}], 'tracks': [{'track_id': 'voice'}]}
            if mode == 'detector':
                sequence['audio_routing']['buses'][0]['sidechain'] = {'track_id': 'voice'}
            elif mode == 'sidechain':
                sequence['audio_routing']['tracks'][0]['sidechain'] = {'bus_id': 'fx'}
                sequence['audio_routing']['buses'][0]['output'] = None
            with self.subTest(mode=mode), self.assertRaises(AppError) as caught:
                build_edit_plan(value, 'seq', edit.request(('d',), options={'linkage': True}))
            self.assertEqual(caught.exception.code, 'EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED')

    def test_collision_does_not_reuse_an_empty_track_that_drives_another_detector(self):
        import test_magnetic_reorder as edit
        from ai_ad_editor.edit_planner import build_edit_plan
        value=edit.project();sequence=value['sequences'][0]
        sequence['tracks'] += [edit.track('voice', [edit.clip('bed',0,27),edit.clip('rider',31,38)], 'audio',1),
                               edit.track('empty_detector', [], 'audio',2)]
        sequence['audio_routing']={'version':1,'buses':[{'id':'fx','output':None,'sidechain':{'track_id':'empty_detector'}}]}
        result,report=build_edit_plan(value,'seq',edit.request(('d',),options={'linkage':True}))
        self.assertNotEqual(edit.positions(result)['rider'][0],'empty_detector')
        self.assertEqual(next(t for t in result['sequences'][0]['tracks'] if t['id']=='empty_detector')['clips'],[])
