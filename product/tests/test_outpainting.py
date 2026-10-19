from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np

import test_local_inpainting as inpaint_fixture
import test_local_matting as base_fixture
import test_local_vace as vace_fixture
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_outpainting import decoder_graph, extend_plan, geometry, valid_plan
from ai_ad_editor.local_inpainting import mask_unchanged, normalize_options, verify_adapter
from ai_ad_editor.local_matting import manifest_hash
from ai_ad_editor.runtime import configure_local_runtime

invoke = base_fixture.invoke


def echo_geometry(text):
    anchor = "atomic_write_json(Path(request['response']),response)"
    return text.replace(anchor, """
if 'outpainting' in request: response['outpainting']=request['outpainting'].copy()
if mode=='bad_outpaint':response['outpainting']['offset_x']+=1
if mode=='missing_outpaint':response.pop('outpainting',None)
""" + anchor)


class OutpaintingGeometryTests(unittest.TestCase):
    def plan(self):
        p = {'engine': 'torchscript-lama-local-v1',
             'video': {'width': 64, 'height': 48, 'source_stream_index': 0}, 'warnings': [],
             'inpainting': normalize_options(grow=0)}
        return extend_plan(p, width=81, height=65)

    def test_odd_center_and_explicit_edges_protect_the_whole_original(self):
        spec = geometry(64, 48, width=81, height=65)
        self.assertEqual((spec['offset_x'], spec['offset_y']), (8, 8))
        for x, y in ((0, 0), (17, 17), (0, 17), (17, 0)):
            s = geometry(64, 48, width=81, height=65, offset_x=x, offset_y=y)
            self.assertEqual((s['source_width'], s['source_height']), (64, 48))

    def test_no_crop_no_noop_no_negative_or_noninteger_geometry(self):
        for kw in ({'width': 64, 'height': 48}, {'width': 63, 'height': 65},
                   {'width': 81, 'height': 47}, {'width': 81, 'height': 65, 'offset_x': -1},
                   {'width': 81, 'height': 65, 'offset_y': 18},
                   {'width': True, 'height': 65}, {'width': 81, 'height': 65.},
                   {'width': 81, 'height': 65, 'offset_x': False}):
            with self.subTest(kw=kw), self.assertRaises(AppError): geometry(64, 48, **kw)

    def test_expanded_canvas_and_not_only_source_raster_has_a_budget(self):
        for width, height in ((8193, 64), (8192, 8192), (4097, 4097)):
            with self.subTest(width=width), self.assertRaises(AppError):
                geometry(64, 48, width=width, height=height)
        self.assertEqual(geometry(64, 48, width=4096, height=4096)['width'], 4096)

    def test_geometry_mask_identity_and_video_dimensions_are_bound_together(self):
        plan = self.plan()
        self.assertTrue(valid_plan(plan)); self.assertTrue(mask_unchanged(plan))
        for target, key, value in ((plan['outpainting'], 'offset_x', 9),
                                   (plan['mask'], 'sha256', 'sha256:'+'0'*64),
                                   (plan['mask'], 'channel', 'luma'),
                                   (plan['video'], 'width', 82)):
            old = target[key]; target[key] = value
            self.assertFalse(valid_plan(plan)); self.assertFalse(mask_unchanged(plan))
            target[key] = old

    def test_mask_growth_feather_and_incomplete_geometry_cannot_modify_the_original(self):
        plan = self.plan()
        for field, value in (('grow', 1), ('feather', 1.), ('threshold', .9)):
            p = copy.deepcopy(plan); p['inpainting'][field] = value
            self.assertFalse(valid_plan(p))
        for key in ('outpainting', 'mask'):
            p = copy.deepcopy(plan); p.pop(key)
            self.assertFalse(mask_unchanged(p))
        p = copy.deepcopy(plan); p['outpainting']['unreviewed'] = True
        self.assertFalse(valid_plan(p))

    def test_generated_mask_clock_shares_one_decoder_and_contains_no_extra_input(self):
        plan = self.plan(); graph = decoder_graph(plan, 'format=rgba')
        self.assertEqual(graph.count('[0:0]'), 1)
        self.assertNotIn('[1:', graph)
        self.assertIn('split=2', graph)
        self.assertIn('between(X,8,71)*between(Y,8,55)', graph)
        plan['outpainting']['offset_y'] = 1
        with self.assertRaises(AppError): decoder_graph(plan, 'format=rgba')


class NativeOutpaintingTests(unittest.TestCase):
    metadata = base_fixture.NativeMattingTests.metadata
    fake_command = base_fixture.NativeMattingTests.fake_command
    ingest = inpaint_fixture.NativeInpaintingTests.ingest
    register = inpaint_fixture.NativeInpaintingTests.register
    assert_clean_failure = inpaint_fixture.NativeInpaintingTests.assert_clean_failure

    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        inpaint_fixture.NativeInpaintingTests.setUp(self)
        self.worker.write_text(echo_geometry(self.worker.read_text(encoding='utf8')), encoding='utf8')

    def command(self):
        return ['media', 'outpaint', '--project', str(self.root), '--asset-id', self.asset_id,
                '--adapter-id', 'lama', '--derived-asset-id', 'repaired', '--width', '80', '--height', '64',
                '--apply', '--track-id', 'track_video_1', '--audio-track-id', 'track_audio_1']

    def decode(self, path, *, audio=False):
        if audio: return base_fixture.NativeMattingTests.decode(self, path, audio=True)
        data = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-an',
            '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True).stdout
        return np.frombuffer(data, np.uint8).reshape(-1, 64, 80, 4)

    def expected(self, *, x=8, y=8, frames=None):
        src = self.frames if frames is None else frames
        value = np.full((len(src), 64, 80, 4), 51, np.uint8); value[..., 3] = 255
        value[:, y:y+48, x:x+64] = src
        return value

    def test_dry_run_has_bound_geometry_rights_and_no_decoder_or_model(self):
        adapter = self.register(); before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as model:
            code, value = invoke(*self.command(), '--dry-run')
            self.assertEqual(code, 0, value); model.assert_not_called()
        self.assertEqual(value['command'], 'media.outpaint')
        self.assertTrue(mask_unchanged(value['data']['plan']))
        self.assertEqual(set(value['data']['rights_dependencies']), {self.asset_id, adapter['rights_ref']})
        self.assertEqual(value['data']['plan']['video']['width'], 80)
        self.assertEqual(self.metadata(), before); self.assertFalse(self.output.exists())

    def test_real_ffmpeg_protocol_preserves_all_original_rgba_and_pcm(self):
        adapter = self.register()
        with self.fake_command(): code, value = invoke(*self.command())
        self.assertEqual(code, 0, value)
        np.testing.assert_array_equal(self.decode(self.output), self.expected())
        np.testing.assert_array_equal(self.decode(self.output, audio=True), self.decode(self.source, audio=True))
        self.assertEqual(set(value['data']['rights']['derived_from']), {self.asset_id, adapter['rights_ref']})
        result = value['data']['outpainting']
        self.assertTrue(result['rgba_roundtrip_verified'])
        self.assertEqual(result['worker']['metrics']['mask_pixels'], 4*(80*64-64*48))
        for domain, action in (('policy', 'audit'), ('rights', 'check')):
            self.assertEqual(invoke(domain, action, '--project', str(self.root))[0], 7 if domain == 'rights' else 0)

    def test_source_rights_cannot_be_reused_for_different_content(self):
        from ai_ad_editor.rights import load_ledger, save_ledger
        self.register()
        ledger = load_ledger(self.root)
        record = next(r for r in ledger['records'] if r['asset_id'] == self.asset_id)
        record['sha256'] = 'sha256:'+'0'*64
        save_ledger(self.root, ledger); before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as model:
            code, value = invoke(*self.command(), '--dry-run')
            self.assertEqual(code, 7, value)
            self.assertIn('OUTPAINT_RIGHTS_DEPENDENCY_MISMATCH', json.dumps(value))
            model.assert_not_called()
        self.assertEqual(self.metadata(), before); self.assertFalse(self.output.exists())

    def test_asymmetric_edge_placement_does_not_crop(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.command(), '--offset-x', '16', '--offset-y', '0')
        self.assertEqual(code, 0, value)
        np.testing.assert_array_equal(self.decode(self.output), self.expected(x=16, y=0))

    def test_single_axis_extension_protects_pixels_at_the_canvas_edges(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.command(), '--height', '48')
        self.assertEqual(code, 0, value)
        raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.output), '-an',
            '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True).stdout
        frames = np.frombuffer(raw, np.uint8).reshape(4, 48, 80, 4)
        np.testing.assert_array_equal(frames[:, :, 8:72], self.frames)
        self.assertTrue(np.all(frames[:, :, :8, :3] == 51))
        self.assertEqual(value['data']['outpainting']['outpainting']['offset_y'], 0)

    def test_rotated_sar_source_is_scaled_before_the_protected_rectangle(self):
        sar, rotated = self.base/'sar.mov', self.base/'rotated.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.source), '-vf', 'setsar=2/1',
            '-c:v', 'qtrle', '-pix_fmt', 'argb', '-c:a', 'copy', str(sar)], capture_output=True, check=True)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-display_rotation:v:0', '90', '-i', str(sar),
            '-c', 'copy', str(rotated)], capture_output=True, check=True)
        self.asset_id = self.ingest(rotated); self.register()
        with self.fake_command(): code, value = invoke(*self.command(), '--height', '80', '--max-edge', '64')
        self.assertEqual(code, 0, value)
        expected = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(rotated), '-an',
            '-vf', 'scale=24:64:flags=lanczos,setsar=1,format=rgba', '-f', 'rawvideo', 'pipe:1'],
            capture_output=True, check=True).stdout
        actual = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.output), '-an',
            '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True).stdout
        expected = np.frombuffer(expected, np.uint8).reshape(4, 64, 24, 4)
        actual = np.frombuffer(actual, np.uint8).reshape(4, 80, 80, 4)
        np.testing.assert_array_equal(actual[:, 8:72, 28:52], expected)
        recipe = value['data']['asset']['source']['outpainting']
        self.assertEqual((recipe['geometry']['source_width'], recipe['geometry']['source_height']), (24, 64))
        self.assertEqual(invoke('validate', '--project', str(self.root))[0], 0)

    def test_source_range_and_nonzero_frame_identities_are_preserved(self):
        self.frames = self.frames.copy()
        for i in range(4): self.frames[i, ..., :3] = [40+i*40, 10+i, 20]
        path = self.base/'identities.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgba',
            '-s', '64x48', '-r', '8', '-i', 'pipe:0', '-i', str(self.source), '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'qtrle', '-pix_fmt', 'argb', '-c:a', 'copy', '-t', '0.5', str(path)],
            input=self.frames.tobytes(), capture_output=True, check=True)
        self.asset_id = self.ingest(path); self.register()
        with self.fake_command(): code, value = invoke(*self.command(), '--start-seconds', '.125', '--end-seconds', '.375')
        self.assertEqual(code, 0, value)
        np.testing.assert_array_equal(self.decode(self.output), self.expected(frames=self.frames[1:3]))
        original = self.decode(self.source, audio=True)
        np.testing.assert_array_equal(self.decode(self.output, audio=True), original[6000:18000])

    def test_invalid_canvas_placement_budget_and_role_never_launch_worker(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as model:
            for flags in (['--width', '63'], ['--height', '47'], ['--width', '64', '--height', '48'],
                          ['--offset-x', '-1'], ['--offset-y', '17'], ['--width', '8192', '--height', '8192']):
                code, value = invoke(*self.command(), *flags, '--dry-run')
                self.assertEqual(code, 2, value)
            model.assert_not_called()
        self.assertEqual(self.metadata(), before)

    def test_missing_or_changed_worker_geometry_rolls_back_output_and_metadata(self):
        self.register(); before = self.metadata()
        for mode in ('bad_outpaint', 'missing_outpaint', 'bad_rgba', 'bad_network', 'fail'):
            with self.subTest(mode=mode), self.fake_command(mode): code, value = invoke(*self.command())
            self.assertEqual(code, 6, value); self.assert_clean_failure(before)

    def test_pre_cancel_keeps_the_original_project_and_has_no_output(self):
        self.register(); before = self.metadata(); marker = self.base/'cancel'; marker.write_text('cancel')
        with self.fake_command(): code, value = invoke(*self.command(), '--cancel-file', str(marker))
        self.assertEqual(code, 8, value); self.assert_clean_failure(before)

    def test_no_audio_and_editable_recipe_survive_project_package(self):
        self.register(); command = self.command()
        index = command.index('--audio-track-id'); del command[index:index+2]
        with self.fake_command(): code, value = invoke(*command, '--no-audio')
        self.assertEqual(code, 0, value)
        recipe = value['data']['asset']['source']['outpainting']
        self.assertEqual(recipe['geometry']['source_width'], 64)
        self.assertFalse(value['data']['outpainting']['audio']['preserve'])
        package = self.base/'copy.aevpkg.zip'
        code, data = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'package', '--output', str(package))
        self.assertEqual(code, 0, data)
        target = self.base/'imported'
        code, data = invoke('convert', 'import', '--input', str(package), '--output', str(target))
        self.assertEqual(code, 0, data)
        project = json.loads((target/'project.json').read_bytes())
        asset = next(a for a in project['assets'] if a['id'] == 'repaired')
        self.assertEqual(asset['source']['outpainting'], recipe)

    def test_new_geometry_conflicts_with_idempotency_replay(self):
        self.register()
        with self.fake_command(): code, first = invoke(*self.command(), '--idempotency-key', 'outpaint-once')
        self.assertEqual(code, 0, first)
        with patch('ai_ad_editor.cli.matte_native') as worker:
            self.assertEqual(invoke(*self.command(), '--idempotency-key', 'outpaint-once')[0], 0)
            self.assertEqual(invoke(*self.command(), '--offset-x', '0', '--idempotency-key', 'outpaint-once')[0], 2)
            worker.assert_not_called()

    def test_missing_bound_outpaint_implementation_rejects_legacy_adapter(self):
        adapter = self.register()
        changed = copy.deepcopy(adapter)
        changed['artifacts'] = [a for a in changed['artifacts'] if a['role'] != 'outpaint']
        changed['sha256'] = manifest_hash(changed)
        self.assertFalse(verify_adapter(changed)['ok'])

    def test_corrupt_editable_recipe_is_rejected_even_with_a_recomputed_digest(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.command())
        self.assertEqual(code, 0, value)
        p = self.root/'project.json'; before = p.read_bytes(); original = json.loads(before)
        for mutation in ('raster', 'normalized_source', 'self_dependency', 'source_range', 'clock', 'unknown'):
            project = copy.deepcopy(original)
            asset = next(a for a in project['assets'] if a['id'] == 'repaired')
            recipe = asset['source']['outpainting']
            if mutation == 'raster': recipe['geometry']['width'] = 81
            elif mutation == 'normalized_source': recipe['geometry']['source_height'] = 47
            elif mutation == 'self_dependency':
                recipe['source_asset_id'] = 'repaired'; recipe['source_sha256'] = asset['sha256']
            elif mutation == 'source_range':
                recipe['range']['end_seconds'] = 2.; recipe['frames'] = 16
            elif mutation == 'clock': recipe['fps'] = '4'; recipe['frames'] = 2
            else: recipe['unreviewed'] = True
            recipe['sha256'] = 'sha256:'+hashlib.sha256(json.dumps({k:v for k,v in recipe.items() if k!='sha256'},
                ensure_ascii=True,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()
            p.write_text(json.dumps(project,ensure_ascii=False), encoding='utf8')
            code, result = invoke('validate', '--project', str(self.root))
            self.assertEqual(code, 2, result)
            self.assertIn('OUTPAINT_RECIPE_INVALID', [e['code'] for e in result['errors']])
        p.write_bytes(before)

    def test_fragment_reuse_remaps_source_ids_and_validates_the_new_recipe(self):
        from ai_ad_editor.project import create_project
        self.register()
        with self.fake_command(): code, value = invoke(*self.command())
        self.assertEqual(code, 0, value)
        original = value['data']['asset']['source']['outpainting']
        library = self.base/'library'
        request = self.base/'fragment.json'
        request.write_text(json.dumps({'id': 'expanded', 'version': 1, 'sequence_id': 'seq_main'}), encoding='utf8')
        code, value = invoke('fragment', 'save', '--project', str(self.root), '--library', str(library), '--input', str(request))
        self.assertEqual(code, 0, value)
        target, _ = create_project(self.base/'target')
        request.write_text(json.dumps({'id': 'expanded', 'version': 1, 'sequence_id': 'seq_main',
                                      'track_id': 'track_video_1', 'at_tick': 0, 'instance_id': 'reuse'}), encoding='utf8')
        code, value = invoke('fragment', 'apply', '--project', str(target), '--library', str(library), '--input', str(request))
        self.assertEqual(code, 0, value)
        project = json.loads((target/'project.json').read_bytes())
        asset = next(a for a in project['assets'] if a.get('source', {}).get('outpainting'))
        rebound = asset['source']['outpainting']
        self.assertNotEqual(rebound['source_asset_id'], original['source_asset_id'])
        self.assertNotEqual(rebound['sha256'], original['sha256'])
        self.assertEqual(rebound['source_sha256'], original['source_sha256'])
        self.assertEqual(asset['source']['derived_from'], [rebound['source_asset_id']])
        self.assertEqual(invoke('validate', '--project', str(target))[0], 0)
        self.assertEqual(invoke('rights', 'check', '--project', str(target))[0], 7)


class NativeVaceOutpaintingTests(unittest.TestCase):
    metadata = base_fixture.NativeMattingTests.metadata
    fake_command = base_fixture.NativeMattingTests.fake_command
    ingest = inpaint_fixture.NativeInpaintingTests.ingest
    register = vace_fixture.NativeVaceTests.register
    assert_clean_failure = vace_fixture.NativeVaceTests.assert_clean_failure

    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        vace_fixture.NativeVaceTests.setUp(self)
        self.worker.write_text(echo_geometry(self.worker.read_text(encoding='utf8')), encoding='utf8')

    def command(self):
        return ['media', 'outpaint', '--project', str(self.root), '--asset-id', self.asset_id,
                '--adapter-id', 'vace', '--derived-asset-id', 'repaired', '--width', '80', '--height', '64',
                '--prompt', 'Extend the quiet gradient background.', '--window-frames', '5', '--window-overlap', '2']

    def test_joint_plan_uses_the_expanded_raster_and_existing_budget(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as model:
            code, value = invoke(*self.command(), '--dry-run')
            self.assertEqual(code, 0, value); model.assert_not_called()
            self.assertTrue(mask_unchanged(value['data']['plan']))
            self.assertGreater(value['data']['plan']['owned_array_budget_bytes'], 80*64*4)
            code, value = invoke(*self.command(), '--width', '4096', '--height', '4096', '--dry-run')
            self.assertEqual(code, 2, value)
        self.assertEqual(self.metadata(), before)

    def test_joint_protocol_sees_new_raster_and_preserves_original_rgba(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.command())
        self.assertEqual(code, 0, value)
        result = value['data']['outpainting']
        data = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.output), '-an', '-pix_fmt', 'rgba',
            '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True).stdout
        frames = np.frombuffer(data, np.uint8).reshape(-1, 64, 80, 4)
        np.testing.assert_array_equal(frames[:, 8:56, 8:72], self.frames)
        self.assertEqual(result['worker']['model_execution']['window_input_shapes'], [[5, 64, 80]])
        self.assertEqual(result['worker']['metrics']['model_calls'], 1)

    def test_joint_geometry_response_and_gpu_contract_failure_roll_back(self):
        self.register(); before = self.metadata()
        for mode in ('bad_outpaint', 'missing_outpaint', 'bad_gpu_device'):
            with self.subTest(mode=mode), self.fake_command(mode): code, value = invoke(*self.command())
            self.assertEqual(code, 6, value); self.assert_clean_failure(before)


if __name__ == '__main__': unittest.main()
