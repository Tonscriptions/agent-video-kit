from __future__ import annotations
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ad_editor import cli, contact_sheet as contact
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project
from ai_ad_editor.utils import sha256_file


def invoke(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = cli.main(list(args))
    return code, json.loads(stream.getvalue())


class ContactSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='native-contact-sheet-')
        cls.folder = Path(cls.temp.name)
        cls.frames = []
        for n in range(4):
            cls.frames.append(bytes(v for y in range(48) for x in range(64)
                for v in (10 + n * 50, x * 3, y * 5, (0, 64, 128, 255)[x//16])))
        cls.source = cls.make_video('normal')
        cls.offset = cls.make_video('offset', ['-output_ts_offset', '2'])
        cls.long_offset = cls.make_video('long-offset', ['-output_ts_offset', '1200'])
        cls.vfr = cls.make_video('vfr', ['-vf', "settb=1/1000,setpts='if(eq(N,0),0,if(eq(N,1),200,if(eq(N,2),700,1100)))'", '-enc_time_base', 'filter'])
        cls.sar = cls.make_video('sar', ['-vf', 'setsar=2'])

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    @classmethod
    def make_video(cls, name, options=()):
        output = cls.folder / (name + '.mkv')
        command = [ffmpeg_path(), '-hide_banner', '-v', 'error', '-nostdin', '-y',
            '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '64x48', '-r', '4', '-i', 'pipe:0',
            *options, '-fps_mode', 'passthrough', '-c:v', 'ffv1', '-pix_fmt', 'bgra', str(output)]
        result = subprocess.run(command, input=b''.join(cls.frames), capture_output=True, timeout=30)
        if result.returncode: raise AssertionError(result.stderr.decode('utf8', 'replace'))
        return output

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='case-', dir=self.folder))
        self.output = self.work / 'sheet'

    def plan(self, source=None, **options):
        return contact.plan_contact_sheet(source or self.source, width=64, height=48, **options)

    def test_non_grid_anchors_select_actual_later_source_frames(self):
        plan = self.plan(times=[0, .26, .75])
        report = contact.execute_contact_sheet(plan, self.output)
        self.assertEqual([r['relative_seconds'] for r in report['frames']], [0, .5, .75])
        for row, index in zip(report['frames'], (0, 2, 3)):
            with Image.open(self.output / row['path']) as image:
                self.assertEqual(image.convert('RGBA').tobytes(), self.frames[index])
            self.assertEqual(row['rgba_sha256'], 'sha256:' + hashlib.sha256(self.frames[index]).hexdigest())
        self.assertTrue(report['process_cleanup']['all_children_reaped'])

    def test_four_panels_match_independent_integer_alpha_composition(self):
        report = contact.execute_contact_sheet(self.plan(times=[.5]), self.output)
        frame = report['frames'][0]
        with Image.open(self.output / 'contact.png') as image:
            for panel in frame['panels']:
                pixels = image.crop((panel['x'], panel['y'], panel['x']+64, panel['y']+48)).tobytes()
                expected = bytearray()
                for y in range(48):
                    for x in range(64):
                        rgba = self.frames[2][(y*64+x)*4:(y*64+x+1)*4]
                        alpha = rgba[3]
                        gray = 255 if panel['view'] == 'light' else 0
                        if panel['view'] == 'checker': gray = 192 if (x//12+y//12)%2 else 96
                        expected.extend([alpha]*3 if panel['view'] == 'alpha' else
                                        [(v*alpha+gray*(255-alpha)+127)//255 for v in rgba[:3]])
                self.assertEqual(pixels, bytes(expected), panel['view'])
                self.assertEqual(panel['rgb_sha256'], 'sha256:'+hashlib.sha256(pixels).hexdigest())

    def test_vfr_anchors_record_actual_pts_without_assuming_cfr(self):
        report = contact.execute_contact_sheet(self.plan(self.vfr, times=[.01, .3, .8]), self.output)
        self.assertEqual([r['relative_seconds'] for r in report['frames']], [.2, .7, 1.1])
        for row, n in zip(report['frames'], (1, 2, 3)):
            self.assertEqual(row['rgba_sha256'], 'sha256:'+hashlib.sha256(self.frames[n]).hexdigest())

    def test_nonzero_origin_even_sampling_uses_video_relative_range(self):
        plan = self.plan(self.offset, count=4)
        self.assertEqual(plan['times'], [0, .25, .5, .75])
        report = contact.execute_contact_sheet(plan, self.output)
        self.assertEqual([r['relative_seconds'] for r in report['frames']], plan['times'])
        self.assertEqual([r['source_pts'] for r in report['frames']], [2000,2250,2500,2750])

    def test_large_timestamp_uses_integer_pts_and_rational_timebase(self):
        report = contact.execute_contact_sheet(self.plan(self.long_offset, times=[.26]), self.output)
        self.assertEqual(report['frames'][0]['source_pts_seconds_rational'], '2401/2')
        self.assertEqual(report['frames'][0]['relative_seconds'], .5)

    def test_frame_resizing_is_bounded_and_alpha_is_not_flattened(self):
        plan = contact.plan_contact_sheet(self.source, times=[0], width=32, height=32)
        report = contact.execute_contact_sheet(plan, self.output)
        self.assertEqual((report['frames'][0]['width'], report['frames'][0]['height']), (32,24))
        self.assertEqual(report['frames'][0]['alpha_extrema'], [0,255])
        self.assertTrue(plan['resample'])

    def test_sample_aspect_ratio_becomes_display_geometry(self):
        report = contact.execute_contact_sheet(self.plan(self.sar, times=[0]), self.output)
        self.assertEqual((report['frames'][0]['width'], report['frames'][0]['height']), (64,24))

    def test_static_png_has_one_frame_and_exact_rgba(self):
        source = self.work/'still.png'; Image.frombytes('RGBA',(64,48),self.frames[0]).save(source)
        plan = self.plan(source)
        self.assertEqual(plan['times'], [0])
        report = contact.execute_contact_sheet(plan, self.output)
        self.assertEqual(report['frames'][0]['rgba_sha256'],'sha256:'+hashlib.sha256(self.frames[0]).hexdigest())

    def test_explicit_order_and_duplicate_anchors_remain_explicit(self):
        report = contact.execute_contact_sheet(self.plan(times=[.75,0,.75]),self.output)
        self.assertEqual([r['relative_seconds'] for r in report['frames']],[.75,0,.75])
        self.assertEqual(report['frames'][0]['rgba_sha256'],report['frames'][2]['rgba_sha256'])

    def test_invalid_numbers_ranges_and_views_reject_without_output(self):
        for options in ({'count':33},{'count':True},{'times':[float('nan')]},{'times':[-1]},
                        {'times':[1]},{'times':[]},{'times':[0],'end':.5},{'start':.7,'end':.6},
                        {'end':2},{'views':[]},{'views':['alpha','alpha']},{'views':['unknown']}):
            with self.subTest(options=options), self.assertRaises(AppError): self.plan(**options)
        self.assertFalse(self.output.exists())

    def test_canvas_limit_rejects_before_encoding(self):
        with self.assertRaises(AppError) as caught:
            contact.plan_contact_sheet(self.source,count=32,width=640,height=640,columns=8)
        self.assertEqual(caught.exception.code,'CONTACT_CANVAS_LIMIT')
        self.assertFalse(self.output.exists())

    def test_actual_concat_container_is_not_trusted_as_single_media(self):
        source=self.work/'spoof.png'
        source.write_text("ffconcat version 1.0\nfile '"+self.source.as_posix()+"'\n",encoding='utf8')
        with self.assertRaises(AppError) as caught: self.plan(source,times=[0])
        self.assertEqual(caught.exception.code,'CONTACT_CONTAINER_UNSUPPORTED')

    def test_changed_source_after_plan_is_rejected_before_frame_process(self):
        source=self.work/'changed.mkv';source.write_bytes(self.source.read_bytes());plan=self.plan(source,times=[0])
        data=source.read_bytes();stamp=source.stat().st_mtime_ns
        source.write_bytes(data[:-1]+bytes([data[-1]^1]));os.utime(source,ns=(stamp,stamp))
        with patch.object(contact.BrowserProcessJob,'start') as start, self.assertRaises(AppError) as caught:
            contact.execute_contact_sheet(plan,self.output)
        self.assertEqual(caught.exception.code,'CONTACT_INPUT_CHANGED');start.assert_not_called()
        self.assertFalse(self.output.exists());self.assertEqual(list(self.work.glob('.sheet-*')),[])

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir();sentinel=self.output/'owned-by-user';sentinel.write_bytes(b'keep')
        with self.assertRaises(AppError):contact.execute_contact_sheet(self.plan(times=[0]),self.output)
        self.assertEqual(sentinel.read_bytes(),b'keep')

    def test_precancel_cleans_without_frame_process(self):
        plan=self.plan(times=[0]);cancel=self.work/'cancel';cancel.touch()
        with patch.object(contact.BrowserProcessJob,'start') as start, self.assertRaises(AppError) as caught:
            contact.execute_contact_sheet(plan,self.output,cancel_file=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED');start.assert_not_called()
        self.assertFalse(self.output.exists());self.assertEqual(list(self.work.glob('.sheet-*')),[])

    def test_cancel_after_real_native_process_start_reaps_owned_children(self):
        plan=self.plan(times=[0,.5]);cancel=self.work/'cancel'
        real=contact.BrowserProcessJob
        class CancelAfterStart(real):
            def start(job,*args,**kwargs):
                process=super().start(*args,**kwargs);cancel.touch();return process
        with patch.object(contact,'BrowserProcessJob',CancelAfterStart),self.assertRaises(AppError) as caught:
            contact.execute_contact_sheet(plan,self.output,cancel_file=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED')
        cleanup=caught.exception.diagnostics['process_cleanup']
        self.assertTrue(cleanup['seen_pids']);self.assertTrue(cleanup['all_children_reaped'])
        self.assertEqual(cleanup['active_after_cleanup'],[]);self.assertFalse(self.output.exists())

    def test_encoded_frame_write_failure_leaves_no_partial_bundle(self):
        plan=self.plan(times=[0])
        with patch.object(contact,'atomic_write_json',side_effect=OSError('controlled disk full')),self.assertRaises(AppError) as caught:
            contact.execute_contact_sheet(plan,self.output)
        self.assertEqual(caught.exception.code,'CONTACT_WRITE_FAILED')
        self.assertFalse(self.output.exists());self.assertEqual(list(self.work.glob('.sheet-*')),[])

    def test_cli_dry_run_no_author_mutation_and_actual_output_records_operation(self):
        root,project=create_project(self.work/'project');before=(root/'project.json').read_bytes()
        argv=['media','contact-sheet','--project',str(root),'--input',str(self.source),'--output','validation/contact',
              '--at-seconds','0','--width','64','--height','48']
        code,reply=invoke(*argv,'--dry-run');self.assertEqual(code,0);self.assertEqual(reply['status'],'planned')
        self.assertFalse((root/'validation/contact').exists());self.assertEqual((root/'project.json').read_bytes(),before)
        code,reply=invoke(*argv);self.assertEqual(code,0,reply)
        self.assertTrue(Path(reply['data']['contact']).is_file());self.assertFalse(reply['data']['quality_accepted'])
        self.assertEqual((root/'project.json').read_bytes(),before)
        self.assertEqual(reply['data']['manifest_sha256'],'sha256:'+sha256_file(Path(reply['data']['manifest'])))

    def test_cli_rejects_external_output_before_probe(self):
        root,_=create_project(self.work/'project')
        with patch.object(contact,'plan_contact_sheet') as plan:
            code,reply=invoke('media','contact-sheet','--project',str(root),'--input',str(self.source),'--output',str(self.work/'external'))
        self.assertNotEqual(code,0);plan.assert_not_called();self.assertFalse((self.work/'external').exists())


if __name__ == '__main__':unittest.main()
