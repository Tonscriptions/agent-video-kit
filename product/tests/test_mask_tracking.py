from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.mask_tracking import ENGINE, observations, prepare
from ai_ad_editor.project import project_transaction
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, sha256_file


def invoke(*args):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        code = main(list(map(str, args)))
    return code, json.loads(capture.getvalue())


class MaskObservationTests(unittest.TestCase):
    def fixture(self):
        report = {'frames': [{'frame': i, 'selected_pixels': 10, 'bbox_normalized': [.1*i, .2, .1*i+.2, .6]} for i in range(4)]}
        plan = {'mask_plan': {'video': {'fps': '4'}, 'scene_cut_frames': []}, 'mask_source_start_seconds': 0.,
                'range': {'start_seconds': 0., 'end_seconds': 1.}, 'step_frames': 1, 'max_samples': 600, 'ticks_per_second': 90000}
        return report, plan

    def test_encoded_geometry_and_terminal_clock_are_not_stretched(self):
        report, plan = self.fixture(); frames, metrics = observations(report, plan)
        self.assertEqual([f['at_tick'] for f in frames], [0, 22500, 45000, 67500, 90000])
        self.assertAlmostEqual(frames[-1]['x'], .4)
        self.assertEqual(frames[-1]['measurement'], 'terminal-hold')
        self.assertEqual(metrics['terminal_holds'], 1)

    def test_non_grid_range_boundaries_interpolate_real_box_coordinates(self):
        report, plan = self.fixture(); plan['range'] = {'start_seconds': .125, 'end_seconds': .625}
        frames, metrics = observations(report, plan)
        self.assertAlmostEqual(frames[0]['x'], .15); self.assertAlmostEqual(frames[-1]['x'], .35)
        self.assertEqual(frames[-1]['at_tick'], 45000)
        self.assertEqual(metrics['boundary_interpolations'], 2)

    def test_source_origin_offset_keeps_source_seconds_and_local_ticks(self):
        report, plan = self.fixture(); plan['mask_source_start_seconds'] = 2.
        plan['range'] = {'start_seconds': 2.25, 'end_seconds': 2.75}
        frames, _ = observations(report, plan)
        self.assertEqual(frames[0]['at_seconds'], 2.25); self.assertEqual(frames[0]['at_tick'], 0)
        self.assertAlmostEqual(frames[0]['x'], .2)

    def test_sampling_budget_preserves_both_range_endpoints(self):
        report, plan = self.fixture(); plan['max_samples'] = 2
        frames, metrics = observations(report, plan)
        self.assertEqual([f['at_seconds'] for f in frames], [0., 1.])
        self.assertTrue(metrics['sampling_reduced_to_budget'])

    def test_even_unsampled_empty_frame_rejects_continuous_track(self):
        report, plan = self.fixture(); plan['step_frames'] = 4
        report['frames'][2].update(selected_pixels=0, bbox_normalized=None)
        with self.assertRaises(AppError) as error: observations(report, plan)
        self.assertEqual(error.exception.code, 'MASK_TRACK_EMPTY_SELECTION')

    def test_empty_frame_outside_requested_range_is_not_used(self):
        report, plan = self.fixture(); plan['range']['end_seconds'] = .5
        report['frames'][3].update(selected_pixels=0, bbox_normalized=None)
        self.assertEqual(observations(report, plan)[0][-1]['at_seconds'], .5)

    def test_scene_endpoint_never_interpolates_toward_next_scene(self):
        report, plan = self.fixture(); plan['mask_plan']['scene_cut_frames'] = [2]
        plan['range']['end_seconds'] = .5
        frames, metrics = observations(report, plan)
        self.assertAlmostEqual(frames[-1]['x'], .2)
        self.assertEqual(metrics['scene_boundary_holds'], 1)
        plan['range'] = {'start_seconds': .3, 'end_seconds': .4}
        frames, metrics = observations(report, plan)
        self.assertTrue(all(abs(f['x']-.2) < 1e-9 for f in frames))
        self.assertEqual(metrics['scene_boundary_holds'], 2)

    def test_project_tick_collisions_fail_instead_of_duplicate_keys(self):
        report, plan = self.fixture(); plan['ticks_per_second'] = 1
        with self.assertRaises(AppError) as error: observations(report, plan)
        self.assertEqual(error.exception.code, 'MASK_TRACK_TIMEBASE_COLLISION')


class FailureDiagnosticTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def test_only_explicit_versioned_failed_diagnostic_survives_rollback(self):
        with tempfile.TemporaryDirectory(prefix='failure-diagnostic-') as raw:
            root=Path(raw)/'project'; self.assertEqual(invoke('project','init',root)[0],0)
            before=(root/'project.json').read_bytes(); target=root/'validation/failed.json'; unrelated=root/'validation/unrelated.json'
            with self.assertRaises(AppError):
                with project_transaction(root,command='test.failed'):
                    (root/'project.json').write_text('{}',encoding='utf-8')
                    atomic_write_json(target,{'report_version':'1','status':'failed'})
                    atomic_write_json(unrelated,{'report_version':'1','status':'failed'})
                    raise AppError('FAILED','failure',exit_code=2,path=str(target))
            self.assertEqual((root/'project.json').read_bytes(),before)
            self.assertTrue(target.is_file()); self.assertFalse(unrelated.exists())
            self.assertFalse((root/'operations/project-transaction.json').exists())

    def test_success_or_unversioned_report_does_not_escape_rollback(self):
        with tempfile.TemporaryDirectory(prefix='failure-diagnostic-gate-') as raw:
            root=Path(raw)/'project'; self.assertEqual(invoke('project','init',root)[0],0)
            target=root/'validation/report.json'; original=b'{"original": true}\n'; target.write_bytes(original)
            for payload in [{'report_version':'1','status':'succeeded'},{'status':'failed'}]:
                with self.subTest(payload=payload), self.assertRaises(AppError):
                    with project_transaction(root,command='test.failed'):
                        atomic_write_json(target,payload)
                        raise AppError('FAILED','failure',exit_code=2,path=str(target))
                self.assertEqual(target.read_bytes(),original)

    def test_non_file_error_path_cannot_mask_original_failure(self):
        with tempfile.TemporaryDirectory(prefix='failure-diagnostic-path-') as raw:
            root=Path(raw)/'project'; self.assertEqual(invoke('project','init',root)[0],0)
            before=(root/'project.json').read_bytes()
            with self.assertRaises(AppError) as error:
                with project_transaction(root,command='test.failed'):
                    (root/'project.json').write_text('{}',encoding='utf-8')
                    raise AppError('ORIGINAL','original failure',exit_code=2,path='invalid\0path')
            self.assertEqual(error.exception.code,'ORIGINAL')
            self.assertEqual((root/'project.json').read_bytes(),before)


class MaskTrackingCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mask-track-'); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base/'project'
        self.source = self.base/'source.mov'; self.mask = self.base/'mask.mov'
        source = bytearray(); mask = bytearray()
        for index in range(8):
            for y in range(48):
                for x in range(64):
                    selected = 8+index*2 <= x < 24+index*2 and 10 <= y < 34
                    source.extend((225, 225, 225, 255) if selected else (18, 40, 70, 255))
                    mask.extend((80, 120, 160, 255 if selected else 0))
        self.mask_bytes = bytes(mask)
        for path, data in [(self.source, source), (self.mask, mask)]:
            result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '64x48', '-r', '8', '-i', 'pipe:0', '-an', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(path)], input=data, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.call('project', 'init', self.root)
        for path, name in [(self.source, 'source'), (self.mask, 'mask')]:
            self.call('media', 'ingest', '--project', self.root, '--input', path, '--asset-id', name)
        marker = self.base/'marker.png'; Image.new('RGBA', (8,8), (255,0,0,255)).save(marker)
        self.call('media', 'ingest', '--project', self.root, '--input', marker, '--asset-id', 'marker')
        value = self.project(); value['settings']['canvas'].update(width=64, height=48)
        value['settings']['timebase']['display_fps'] = {'num': 8, 'den': 1}
        value['sequences'][0]['duration_tick'] = 90000
        atomic_write_json(self.root/'project.json', value)
        self.compose([{'op': 'append_clip', 'track_id': 'track_video_1', 'id': 'source_clip', 'asset_id': 'source', 'source_in_tick': 0, 'source_out_tick': 90000},
                      {'op': 'add_track', 'track_id': 'labels', 'kind': 'video', 'order': 3},
                      {'op': 'append_clip', 'track_id': 'labels', 'id': 'label', 'asset_id': 'marker', 'source_in_tick': 0, 'source_out_tick': 90000, 'duration_tick': 90000, 'transform': {'scale': .08}}])

    def call(self, *args):
        code, value = invoke(*args); self.assertEqual(code, 0, value); return value

    def project(self): return json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))

    def compose(self, changes):
        path = self.base/'changes.json'; atomic_write_json(path, {'operations': changes})
        return self.call('timeline', 'compose', '--project', self.root, '--input', path)

    def track(self, *args):
        return invoke('media', 'track', '--project', self.root, '--asset-id', 'source', '--mask-asset-id', 'mask', *args)

    def bind(self, *args):
        return invoke('media', 'track-bind', '--project', self.root, '--asset-id', 'source', '--mask-asset-id', 'mask', '--target-track-id', 'labels', '--target-clip-id', 'label', *args)

    def reframe(self, *args):
        return invoke('media', 'reframe', '--project', self.root, '--asset-id', 'source', '--mask-asset-id', 'mask', '--track-id', 'track_video_1', '--clip-id', 'source_clip', '--target-aspect', '.75', *args)

    def test_real_encoded_mask_report_and_read_only_metadata(self):
        before = [(self.root/n).read_bytes() for n in ['project.json', 'rights-ledger.json']]
        code, value = self.track('--step-frames', '1', '--output', 'validation/track.json')
        self.assertEqual(code, 0, value); result = value['data']['result']
        self.assertEqual(result['engine'], ENGINE); self.assertEqual(len(result['frames']), 9)
        self.assertAlmostEqual(result['frames'][0]['x'], 16/64)
        self.assertAlmostEqual(result['frames'][-1]['x'], 30/64)
        self.assertEqual(result['frames'][-2]['at_tick'], 78750)
        self.assertEqual(result['frames'][-1]['at_tick'], 90000)
        self.assertIn('not-model-confidence', result['confidence_semantics'])
        self.assertEqual(before, [(self.root/n).read_bytes() for n in ['project.json', 'rights-ledger.json']])

    def test_three_dry_runs_preflight_without_decode_or_report(self):
        with patch('ai_ad_editor.mask_tracking.review', side_effect=AssertionError('dry run decoded')):
            for command in [self.track, self.bind, self.reframe]:
                with self.subTest(command=command.__name__):
                    path = self.root/'validation'/f'{command.__name__}.json'
                    code, value = command('--dry-run', '--output', path)
                    self.assertEqual(code, 0, value); self.assertEqual(value['status'], 'planned')
                    self.assertIsNotNone(value['data']['mask_plan']); self.assertFalse(path.exists())

    def test_input_mode_options_and_report_overwrite_are_rejected(self):
        for args in [('--roi', '0,0,1,1'), ('--object-id', '2'), ('--all-objects',), ('--search-radius', '10'),
                     ('--max-width', '320'), ('--output', self.root/'project.json'), ('--output', 'validation/wrong.mov'),
                     ('--mask-source-start-seconds', 'nan'), ('--max-samples', '1'), ('--mask-budget-mib', '0')]:
            with self.subTest(args=args): self.assertEqual(self.track(*args)[0], 2)

    def test_bad_clock_coverage_and_declared_scene_cut_fail_preflight(self):
        for args in [('--start-seconds', '-1'), ('--end-seconds', '2'), ('--mask-source-start-seconds', '.5'), ('--mask-scene-cut-frame', '4')]:
            with self.subTest(args=args): self.assertEqual(self.track(*args)[0], 2)
        code, value = self.track('--start-seconds', '.25', '--end-seconds', '1', '--mask-source-start-seconds', '.25')
        self.assertEqual(code, 0, value); self.assertEqual(value['data']['result']['frames'][0]['at_seconds'], .25)

    def test_failed_expectations_preserve_report_and_do_not_apply(self):
        path = self.root/'validation/checks.json'
        atomic_write_json(path, {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': [{'frame': 0, 'points': [{'x': .95, 'y': .5, 'expected': 'selected'}]}]})
        before = [(self.root/n).read_bytes() for n in ['project.json', 'rights-ledger.json']]
        code, value = self.bind('--apply', '--mask-expectations', path, '--output', 'validation/failed.json')
        self.assertEqual(code, 2, value)
        failed = json.loads((self.root/'validation/failed.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(failed['error']['code'], 'MASK_TRACK_EXPECTATION_FAILED')
        self.assertEqual(len(failed['mask_review']['failed_points']), 1)
        self.assertEqual(before, [(self.root/n).read_bytes() for n in ['project.json', 'rights-ledger.json']])
        self.assertEqual(self.track('--mask-expectations', path, '--output', path)[0], 2)

    def test_empty_unsampled_encoded_frame_is_failed_with_report(self):
        empty = bytearray(self.mask_bytes)
        for at in range(2*64*48*4+3, 3*64*48*4, 4): empty[at] = 0
        path = self.base/'empty.mov'
        result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '64x48', '-r', '8', '-i', 'pipe:0', '-an', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(path)], input=empty, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.call('media', 'ingest', '--project', self.root, '--input', path, '--asset-id', 'empty')
        code, value = invoke('media', 'track', '--project', self.root, '--asset-id', 'source', '--mask-asset-id', 'empty', '--step-frames', '4', '--output', 'validation/empty.json')
        self.assertEqual(code, 2, value)
        self.assertEqual(value['errors'][0]['code'], 'MASK_TRACK_EMPTY_SELECTION')
        self.assertTrue((self.root/'validation/empty.json').exists())

    def test_source_and_mask_tamper_and_missing_rights_fail(self):
        project = self.project(); assets = {a['id']: a for a in project['assets']}
        ingested = self.root/assets['mask']['uri']; original = ingested.read_bytes(); ingested.write_bytes(original+b'x')
        self.assertEqual(self.track()[0], 6)
        ingested.write_bytes(original)
        ledger = json.loads((self.root/'rights-ledger.json').read_text(encoding='utf-8-sig'))
        self.assertIsInstance(ledger, dict)
        # A registered mask cannot borrow an unrelated active rights record.
        assets['mask']['rights_ref'] = 'missing_rights'; atomic_write_json(self.root/'project.json', project)
        self.assertEqual(self.track()[0], 7)

    def test_binding_keeps_source_and_mask_rights_and_renders_tracking(self):
        code, value = self.bind('--step-frames', '1', '--source-track-id', 'track_video_1', '--source-clip-id', 'source_clip', '--apply')
        self.assertEqual(code, 0, value); project = self.project()
        label = next(t for t in project['sequences'][0]['tracks'] if t['id'] == 'labels')['clips'][0]
        self.assertIn('tracking_binding', label)
        self.assertEqual({r['rights_ref'] for r in label['rights_dependencies']}, {'source', 'mask'})
        self.assertEqual(label['tracking_binding']['observations'][-1]['at_seconds'], 1.)
        self.call('validate', '--project', self.root)
        target = self.root/'renders/bound.mp4'
        self.call('render', '--project', self.root, '--output', target)
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(target), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True).stdout
        self.assertEqual(len(decoded), 8*64*48*3)
        centers = []
        for index in [0, 4, 7]:
            pixels = decoded[index*64*48*3:(index+1)*64*48*3]; xs=[];ys=[]
            for y in range(48):
                for x in range(64):
                    r,g,b = pixels[(y*64+x)*3:(y*64+x)*3+3]
                    if r > 160 and g < 90 and b < 90: xs.append(x);ys.append(y)
            self.assertTrue(xs); centers.append((sum(xs)/len(xs),sum(ys)/len(ys)))
        for index, center in zip([0,4,7], centers):
            self.assertLessEqual(abs(center[0]-(16+2*index)), 2)
            self.assertLessEqual(abs(center[1]-22), 2)
        self.assertEqual(invoke('render', '--project', self.root, '--output', self.root/'renders/blocked.mp4', '--publish')[0], 7)

    def test_reframe_uses_mask_and_inherits_its_rights(self):
        code, value = self.reframe('--apply')
        self.assertEqual(code, 0, value); plan = value['data']['plan']
        self.assertEqual(plan['engine'], 'local-reframe-from-mask-bbox-v1')
        self.assertNotIn('local_template_tracking_can_drift_on_occlusion_scale_change_or_scene_cut', plan['warnings'])
        clip = next(t for t in self.project()['sequences'][0]['tracks'] if t['id']=='track_video_1')['clips'][0]
        self.assertEqual({r['rights_ref'] for r in clip['rights_dependencies']}, {'source','mask'})
        self.assertIn('crop.x', [k['property'] for k in clip['keyframes']])

    def test_explicit_luma_and_decode_budget_preflight(self):
        path = self.base/'luma.mkv'
        data = self.mask_bytes[3::4]
        subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','gray','-s','64x48','-r','8','-i','pipe:0','-an','-c:v','ffv1',str(path)], input=data, capture_output=True, check=True)
        self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','luma')
        args = ('media','track','--project',self.root,'--asset-id','source','--mask-asset-id','luma')
        self.assertEqual(invoke(*args)[0],2)
        code,value = invoke(*args,'--mask-channel','luma','--step-frames','1')
        self.assertEqual(code,0,value)
        self.assertAlmostEqual(value['data']['result']['frames'][4]['x'],24/64)
        with patch('ai_ad_editor.mask_tracking.review',side_effect=AssertionError('budget failure decoded')):
            self.assertEqual(self.track('--mask-max-frames','7')[0],2)
            self.assertEqual(invoke('media','reframe','--project',self.root,'--asset-id','source','--mask-asset-id','mask','--track-id','track_video_1','--clip-id','source_clip','--start-seconds','nan')[0],2)

    def test_aspect_and_source_probe_mismatch_are_rejected(self):
        path = self.base/'square.mov'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(self.mask),'-vf','scale=48:48','-c:v','qtrle','-pix_fmt','argb',str(path)],capture_output=True,check=True)
        self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','square')
        code,value = invoke('media','track','--project',self.root,'--asset-id','source','--mask-asset-id','square')
        self.assertEqual(code,2,value); self.assertEqual(value['errors'][0]['code'],'MASK_TRACK_ASPECT_MISMATCH')
        project = self.project(); next(a for a in project['assets'] if a['id']=='source')['probe']['video']['width']=128
        atomic_write_json(self.root/'project.json',project)
        self.assertEqual(self.track()[0],6)

    def test_display_sar_reports_but_rejects_unsupported_apply_geometry(self):
        for name,source in [('wide_source',self.source),('wide_mask',self.mask)]:
            path = self.base/(name+'.mov')
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-vf','setsar=2','-c:v','qtrle','-pix_fmt','argb',str(path)],capture_output=True,check=True)
            self.call('media','ingest','--project',self.root,'--input',path,'--asset-id',name)
        args = ('--project',self.root,'--asset-id','wide_source','--mask-asset-id','wide_mask')
        code,value = invoke('media','track',*args)
        self.assertEqual(code,0,value); self.assertEqual(value['data']['result']['source_display'],{'width':128.,'height':48.})
        project=self.project(); next(t for t in project['sequences'][0]['tracks'] if t['id']=='track_video_1')['clips'][0]['asset_id']='wide_source'
        atomic_write_json(self.root/'project.json',project)
        code,value=invoke('media','track-bind',*args,'--target-track-id','labels','--target-clip-id','label','--source-track-id','track_video_1','--source-clip-id','source_clip','--apply')
        self.assertEqual(code,2,value); self.assertEqual(value['errors'][0]['code'],'MASK_TRACK_RENDER_GEOMETRY_UNSUPPORTED')
        self.assertEqual(invoke('media','reframe',*args,'--track-id','track_video_1','--clip-id','source_clip','--apply')[0],2)

    def test_source_changed_during_decode_is_rejected_with_diagnostic(self):
        from ai_ad_editor.mask_review import review as actual_review
        asset=next(a for a in self.project()['assets'] if a['id']=='source'); source=self.root/asset['uri']
        def altered(root,plan):
            result=actual_review(root,plan); source.write_bytes(source.read_bytes()+b'changed'); return result
        before=(self.root/'project.json').read_bytes()
        with patch('ai_ad_editor.mask_tracking.review',side_effect=altered):
            code,value=self.track('--output','validation/source-changed.json')
        self.assertEqual(code,6,value); self.assertEqual(value['errors'][0]['code'],'MASK_TRACK_SOURCE_CHANGED')
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertEqual(json.loads((self.root/'validation/source-changed.json').read_text(encoding='utf-8'))['status'],'failed')

    def test_binding_rights_and_observations_survive_portable_package(self):
        self.assertEqual(self.bind('--source-track-id','track_video_1','--source-clip-id','source_clip','--apply')[0],0)
        package=self.base/'portable.zip'; imported=self.base/'imported'
        self.call('convert','export','--project',self.root,'--target-format','package','--output',package)
        self.call('convert','import','--input',package,'--output',imported)
        value=json.loads((imported/'project.json').read_text(encoding='utf-8-sig'))
        label=next(t for t in value['sequences'][0]['tracks'] if t['id']=='labels')['clips'][0]
        self.assertEqual({r['rights_ref'] for r in label['rights_dependencies']},{'source','mask'})
        self.assertEqual(label['tracking_binding']['observations'][-1]['at_seconds'],1.)
        self.call('validate','--project',imported)
        self.assertEqual(invoke('render','--project',imported,'--output',imported/'renders/blocked.mp4','--publish')[0],7)

    def test_alpha_label_fit_preserves_underlying_video_in_padding(self):
        path=self.base/'alpha-video.mov'
        subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-i',str(self.base/'marker.png'),'-t','1','-r','8','-c:v','qtrle','-pix_fmt','argb',str(path)],capture_output=True,check=True)
        self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','alpha_video')
        for asset in ['marker','alpha_video']:
            with self.subTest(asset=asset):
                self.compose([{'op':'update_clip','track_id':'labels','clip_id':'label','patch':{'asset_id':asset,'transform':{'scale':.5}}}])
                output=self.root/f'renders/alpha-label-{asset}.mp4'; self.call('render','--project',self.root,'--output',output)
                raw=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
                # Square label fits to 48x48 then scales by 0.5; its 4px side padding must reveal the source.
                white=raw[(24*64+17)*3:(24*64+17)*3+3]; navy=raw[(24*64+46)*3:(24*64+46)*3+3]
                self.assertGreater(min(white),180,white)
                self.assertGreater(navy[2],40,navy)
                self.assertLess(navy[0],60,navy)


if __name__ == '__main__': unittest.main()
