"""RGB point animation: actual native pixels, clock mapping and strict gates."""
from __future__ import annotations
import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor import curve_automation as cp
from ai_ad_editor.effect_automation import EffectAutomation, validate
from ai_ad_editor.effects import get_effect
from ai_ad_editor.errors import AppError
from ai_ad_editor.render import _effect_filters, build_filter_graph
from ai_ad_editor.project import create_project, load_project, save_project
import test_effect_automation as original
from test_magnetic_reorder import invoke
from PIL import Image


def effect(prop='all.1.y', left=.2, right=.8, *, kind='rgb_curves', parameters=None, end=90000):
    return {'type': kind, 'parameters': parameters or {'all': '0/0 0.5/0.5 1/1'},
            'keyframes': [{'property': prop, 'keyframes': [
                {'at_tick': 0, 'value': left, 'interpolation': 'linear'},
                {'at_tick': end, 'value': right, 'interpolation': 'linear'}]}]}


class CurvePointTests(unittest.TestCase):
    native = original.EffectAutomationNativeTests.native

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bind(self, value=None, *, rate='10', clip=None, start=0., compiler=None):
        clip = clip or {'id': 'c', 'timeline_start_tick': round(start*90000), 'duration_tick': 90000}
        compiler = compiler or EffectAutomation(self.root, rate, 90000)
        metadata, warnings = [], []
        chain = _effect_filters([value or effect()], warnings, 'c', root=self.root, clip=clip,
                                clip_start=start, automation=compiler, automation_meta=metadata)
        self.assertFalse(warnings)
        return chain, metadata[0], compiler

    def compare(self, value, reference, *, rate='10', clip=None, start=0.):
        chain, metadata, _ = self.bind(value, rate=rate, clip=clip, start=start)
        count = max(1, metadata['sampled_frames'])
        actual = self.native(','.join(chain), count=count, rate=rate)
        for i, frame in enumerate(actual):
            expected = self.native(reference(i/float(Fraction(rate))), count=1, rate=rate)[0]
            self.assertEqual(frame, expected, (i, metadata['parameters']))
        self.assertGreater(len(set(actual)), 1)
        return metadata

    def test_catalog_describes_coordinate_paths_without_inflating_scalar_engine(self):
        value = get_effect('rgb_curve')
        self.assertEqual(value['keyframe_engine'], cp.ENGINE)
        self.assertIn('red.<index>.x', value['keyframe_parameters'])
        self.assertEqual(value['keyframe_point_index']['maximum'], 255)

    def test_prefixes_and_master_alias_preserve_existing_all_semantics(self):
        for kind in ('curves', 'curve', 'rgb_curves', 'rgb_curve', 'channel_curves'):
            for prefix in ('effect.', 'parameters.', kind+'.', ''):
                self.assertEqual(validate(effect(prefix+'all.1.y', kind=kind)), [])
        value = effect('master.1.y', kind='curve')
        value['parameters'] = {'master': '0/0 0.5/0.5 1/1'}
        self.assertEqual(validate(value), [])
        value['keyframes'].append(copy.deepcopy(value['keyframes'][0])); value['keyframes'][1]['property'] = 'all.1.y'
        self.assertEqual(validate(value)[0]['code'], 'EFFECT_AUTOMATION_DUPLICATE_PROPERTY')

    def test_point_indices_and_channel_names_are_not_arbitrary_native_commands(self):
        for prop in ('all.-1.y', 'all.01.y', 'all.3.y', 'all.256.y', 'master.1.y', 'plot', 'all.1.z', 'red.1.y; plot x', 'all.x'):
            self.assertTrue(validate(effect(prop)), prop)
        self.assertTrue(validate(effect('red.1.y', kind='curves')))

    def test_static_points_reject_unsafe_nonfinite_crossing_and_bin_collision(self):
        for value in ('0/0; plot x', 'nan/0 1/1', '0/0 1e999/1', '0/0 0/1', '0.5/0 0.5001/1', '1/1 0/0', '', True):
            with self.subTest(value=value):
                self.assertEqual(validate(effect(parameters={'all': value}))[0]['code'], 'CURVE_AUTOMATION_POINTS_INVALID')

    def test_point_count_cap_and_single_point_native_constant(self):
        points = ' '.join(f'{min(1,(i+.25)/255):.6f}/0.5' for i in range(256))
        self.assertEqual(len(cp.parse_points(points)), 256)
        with self.assertRaises(AppError): cp.parse_points(points+' 1/1')
        value = effect('all.0.y', parameters={'all': '0.5/0.5'})
        self.compare(value, lambda t: f"curves=all='0.5/{.2+.6*t:.6f}'")

    def test_numeric_keyframe_contract_remains_strict(self):
        for field, bad in (('value', True), ('value', '0.5'), ('value', 1.1), ('at_tick', -1), ('at_tick', True), ('interpolation', 'smooth')):
            value = effect(); value['keyframes'][0]['keyframes'][0][field] = bad
            self.assertTrue(validate(value))
        self.assertTrue(validate(effect(end=90001), duration_tick=90000))

    def test_parameter_tracks_and_top_level_precedence(self):
        value = effect(); valid = value.pop('keyframes'); value['parameters']['keyframes'] = valid
        self.assertEqual(validate(value), [])
        value['keyframes'] = []
        self.assertEqual(cp.tracks(value), [])

    def test_disabled_invalid_effect_needs_no_runtime_or_command_file(self):
        value = effect('plot'); value['enabled'] = False
        self.assertEqual(validate(value), [])
        self.assertEqual(_effect_filters([value], [], 'c'), [])
        self.assertFalse((self.root/'cache').exists())

    def test_missing_native_option_is_a_hard_gate(self):
        with patch('ai_ad_editor.effect_automation.runtime_options', return_value=frozenset({'all', 'red'})):
            with self.assertRaises(AppError) as caught: self.bind()
        self.assertEqual(caught.exception.code, 'EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE')
        self.assertFalse((self.root/'cache').exists())

    def test_crossing_between_valid_author_keys_is_rejected_before_cache(self):
        value = effect('all.1.x', .4, .6)
        point = value['keyframes'][0]['keyframes'][0]
        point.update(interpolation='bezier', control_points=[10, 10])
        with self.assertRaises(AppError) as caught: self.bind(value)
        self.assertEqual(caught.exception.code, 'CURVE_AUTOMATION_POINTS_INVALID')
        self.assertFalse((self.root/'cache').exists())

    def test_shared_instance_sample_command_and_byte_quotas(self):
        for field, value in (('MAX_SAMPLES', 1), ('MAX_TARGETS', 0), ('MAX_COMMANDS', 1), ('MAX_BYTES', 1)):
            with self.subTest(field=field), patch('ai_ad_editor.effect_automation.'+field, value):
                with self.assertRaises(AppError) as caught: self.bind()
                self.assertEqual(caught.exception.code, 'EFFECT_AUTOMATION_BUDGET')
        compiler = EffectAutomation(self.root, '10', 90000); compiler.samples = 1_999_999
        with self.assertRaises(AppError): self.bind(compiler=compiler)

    def test_cache_hash_gate_and_root_unique_targets(self):
        _, a, compiler = self.bind(); _, b, _ = self.bind(compiler=compiler)
        self.assertNotEqual(a['target'], b['target']); self.assertEqual(compiler.targets, 2)
        (self.root/a['command_file']).write_text('tampered')
        with self.assertRaises(AppError) as caught: self.bind()
        self.assertEqual(caught.exception.code, 'EFFECT_AUTOMATION_CACHE_HASH_MISMATCH')

    def test_all_animation_keeps_explicit_static_red_and_exact_alpha(self):
        self.compare(effect(parameters={'all': '0/0 0.5/0.5 1/1', 'red': '0/0 0.5/0.7 1/1'}),
                     lambda t: f"curves=all='0/0 0.5/{.2+.6*t:.6f} 1/1':red='0/0 0.5/0.7 1/1'")

    def test_independent_rgb_and_x_coordinate_native_reference(self):
        value = effect('red.1.x', .3, .7)
        value['keyframes'] += effect('blue.1.y', .7, .3)['keyframes']
        self.compare(value, lambda t: f"curves=red='0/0 {(.3+.4*t):.6f}/0.5 1/1':green='0/0 0.5/0.5 1/1':blue='0/0 0.5/{.7-.4*t:.6f} 1/1'")

    def test_whole_channel_update_can_move_adjacent_x_points_together(self):
        value = effect('all.1.x', .3, .6, parameters={'all': '0/0 0.3/0.4 0.5/0.6 1/1'})
        value['keyframes'] += effect('all.2.x', .5, .8)['keyframes']
        meta = self.compare(value, lambda t: f"curves=all='0/0 {.3+.3*t:.6f}/0.4 {.5+.3*t:.6f}/0.6 1/1'")
        text = (self.root/meta['command_file']).read_text()
        self.assertNotIn(' all ', text); self.assertNotIn(' master ', text)
        self.assertEqual(meta['command_count'], 30)

    def test_hold_and_bezier_temporal_interpolation_with_recorded_clamp(self):
        value = effect(); value['keyframes'][0]['keyframes'][0]['interpolation'] = 'hold'
        chain, meta, _ = self.bind(value)
        frames = self.native(','.join(chain))
        self.assertEqual(len(set(frames)), 1); self.assertEqual(meta['command_count'], 3)
        value['keyframes'][0]['keyframes'][0].update(interpolation='bezier', control_points=[4, 4])
        _, meta, _ = self.bind(value)
        self.assertGreater(meta['clamped_parameter_samples'], 0)

    def test_fractional_rate_and_nonzero_start_use_actual_cfr_grid(self):
        _, meta, _ = self.bind(rate='30000/1001', start=.11)
        self.assertEqual(meta['frame_start'], 4); self.assertEqual(meta['sampled_frames'], 30)
        lines = (self.root/meta['command_file']).read_text().splitlines()
        self.assertEqual(float(lines[0].split()[0]), 0)
        self.assertAlmostEqual(float(lines[1].split()[0]), 4.5*1001/30000, places=11)

    def test_reverse_nested_author_map_uses_continuous_parameters(self):
        mapping = {'source_start': 0., 'source_end': 2., 'timeline_start': 0.,
                   'timeline_duration': 1., 'speed': 2., 'reverse': True, 'segments': [], 'curve_scale': 1.}
        clip = {'id': 'c', 'timeline_start_tick': 0, 'duration_tick': 90000,
                '_nested_keyframe_clock': {'maps': [mapping], 'authored_start': 0.}}
        self.compare(effect(end=180000), lambda t: f"curves=all='0/0 0.5/{.8-.6*t:.6f} 1/1'", clip=clip)

    def test_static_path_is_unchanged(self):
        self.assertEqual(_effect_filters([{'type': 'curves', 'master': '0/0 1/1'}], [], 'c'), ["curves=all='0/0 1/1'"])
        self.assertFalse((self.root/'cache').exists())


class CurvePointProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name); self.root = self.work/'project'
        _, project = create_project(self.root, name='curve')
        project['settings']['canvas'] = {'width': 32, 'height': 18, 'background': '#000000'}
        project['settings']['timebase'] = {'ticks_per_second': 90000, 'display_fps': {'num': 10, 'den': 1}}
        save_project(self.root, project)
        image = self.work/'in.png'; Image.new('RGBA', (32, 18), (77, 113, 201, 170)).save(image)
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', image)
        self.assertEqual(code, 0, result)
        self.project = load_project(self.root)[1]; self.sequence = self.project['sequences'][0]
        self.sequence['duration_tick'] = 90000
        self.clip = {'id': 'c', 'asset_id': result['data']['asset']['id'], 'timeline_start_tick': 0,
                     'source_in_tick': 0, 'source_out_tick': 90000, 'duration_tick': 90000, 'effects': [effect()]}
        self.sequence['tracks'][0]['clips'] = [self.clip]; save_project(self.root, self.project)

    def test_real_cli_validate_and_render_manifest(self):
        code, result = invoke('validate', '--project', self.root)
        self.assertEqual(code, 0, result)
        self.assertNotIn('EFFECT_KEYFRAME_PROPERTY_UNSUPPORTED', json.dumps(result))
        code, result = invoke('render', '--project', self.root, '--output', self.root/'renders/out.mkv')
        self.assertEqual(code, 0, result)
        manifest = json.loads(Path(result['data']['manifest']).read_bytes())
        self.assertTrue(any(x.get('kind') == 'curve-point-automation' for x in manifest['inputs']))

    def test_invalid_compose_does_not_mutate_author_project(self):
        before = (self.root/'project.json').read_bytes(); path = self.work/'edit.json'
        path.write_text(json.dumps({'operations': [{'op': 'update_clip', 'clip_id': 'c', 'patch': {'effects': [effect('plot')]}}]}))
        code, result = invoke('timeline', 'compose', '--project', self.root, '--input', path)
        self.assertNotEqual(code, 0, result); self.assertEqual((self.root/'project.json').read_bytes(), before)

    def test_nested_and_parent_and_adjustment_share_instance_budget(self):
        child = copy.deepcopy(self.sequence); child['id'] = 'child'; child['tracks'][0]['id'] = 'ct'; child['tracks'][0]['clips'][0]['id'] = 'inner'
        self.project['sequences'].append(child)
        self.sequence['tracks'][0]['clips'] = [{**self.clip, 'sequence_id': 'child', 'effects': [effect('red.1.y')]}]
        self.sequence['tracks'][0]['clips'][0].pop('asset_id')
        self.project['settings']['adjustments'] = [effect('all.1.y')]
        _, _, meta, warnings = build_filter_graph(self.root, self.project, self.sequence)
        self.assertEqual(sum(x.get('kind') == 'curve-point-automation' for x in meta), 3)
        budget = next(x for x in meta if x.get('kind') == 'effect-automation-budget')
        self.assertEqual(budget['targets'], 3)
        self.assertFalse(any('UNSUPPORTED' in x.get('code', '') for x in warnings))

    def test_presentation_window_keeps_original_point_clock(self):
        self.clip['duration_tick'] = 45000
        self.clip['presentation_window'] = {'version': 1, 'offset_tick': 45000, 'authored_duration_tick': 90000, 'authored_start_tick': 0}
        self.sequence['duration_tick'] = 45000
        _, _, meta, _ = build_filter_graph(self.root, self.project, self.sequence)
        window = next(x for x in meta if x.get('purpose') == 'clip-presentation-window')
        curve = next(x for x in window['inputs'] if x.get('kind') == 'curve-point-automation')
        self.assertEqual(curve['sampled_frames'], 10)
        self.assertEqual(window['source_first_frame'], 5)
        self.assertEqual(window['source_end_frame'], 10)


if __name__ == '__main__': unittest.main()
