"""Native lossless chunk order, keyframe seeking, offline cache and rollback."""
from fractions import Fraction
import json
from pathlib import Path
import shutil
import threading
import unittest
from unittest.mock import patch

from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor.reverse_video_clock import reverse_intervals
from ai_ad_editor import reverse_video_clock as clock
from ai_ad_editor import reverse_cache as cache
from ai_ad_editor.utils import sha256_file
from ai_ad_editor.video_clock import working_clock
import test_cfr_boundaries as helpers

class ReverseChunkTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp
    run_native=helpers.CFRBoundaryTests.run_native
    source=helpers.CFRBoundaryTests.source

    def job(self,source,*,first=10170,end=100170,chunk_frames=5,decoder=None):
        value=json.loads(self.run_native([ffprobe_path(),'-v','error','-select_streams','v:0',
            '-show_entries','stream=time_base','-of','json',source]))
        native=value['streams'][0]['time_base']
        _,working=working_clock(Fraction(native),'30000/1001',90000)
        with patch.object(clock,'MAX_SELECTED_BUFFER_BYTES',chunk_frames*helpers.W*helpers.H*16):
            _,_,_,metadata=reverse_intervals(source,first,end,90000,working['working_time_base'],
                expected_time_base=native,decoder=decoder)
        return cache.plan(self.root,source,'sha256:'+sha256_file(source),metadata,decoder=decoder)

    def execute(self,job,**kw):
        return cache.execute(self.root,job,self.root/'renders/.tmp/reverse-test',**kw)

    def decode(self,path,*,pixel_format='rgba',decoder=None):
        return self.run_native([ffmpeg_path(),'-v','error','-noautorotate',
            *(['-c:v',decoder] if decoder else []),'-i',path,'-map','0:v:0','-fps_mode','passthrough',
            '-f','rawvideo','-pix_fmt',pixel_format,'pipe:1'])

    def test_plan_is_read_only_and_preserves_original_interval_clock_separately(self):
        path,_,_=self.source();job=self.job(path)
        self.assertFalse((self.root/'cache/reverse-video').exists())
        self.assertTrue(job['recipe']['source_working_clock_applied_by_renderer'])
        self.assertFalse(job['recipe']['cache_pts_are_original_source_pts'])
        self.assertEqual(job['recipe']['frames'],26)

    def test_native_CFR_reverse_chunks_keep_every_selected_pixel(self):
        path,colors,_=self.source();job=self.job(path)
        result=self.execute(job)
        expected=b''.join(bytes(colors[i])*(helpers.W*helpers.H) for i in range(27,1,-1))
        self.assertEqual(self.decode(job['output']),expected)
        self.assertEqual(result['chunk_frames'],[5,5,5,5,5,1])

    def test_native_VFR_chunks_keep_frames_without_average_fps_resampling(self):
        path,colors,_=self.source(count=12,vfr=[0,33,101,188,195,441,499,800,1002,1221,1600,1800])
        job=self.job(path,chunk_frames=2);result=self.execute(job)
        expected=b''.join(bytes(colors[i])*(helpers.W*helpers.H) for i in range(8,1,-1))
        self.assertEqual(self.decode(job['output']),expected)
        self.assertEqual(sum(result['chunk_frames']),7)

    def test_nonzero_demux_origin_seeks_and_trims_native_absolute_PTS(self):
        source,colors,_=self.source();path=self.work/'offset.nut'
        self.run_native([ffmpeg_path(),'-v','error','-i',source,'-output_ts_offset','5.117123',
            '-fps_mode','passthrough','-enc_time_base','filter','-c:v','ffv1','-pix_fmt','bgra',path])
        job=self.job(path);self.execute(job)
        expected=b''.join(bytes(colors[i])*(helpers.W*helpers.H) for i in range(27,1,-1))
        self.assertEqual(self.decode(job['output']),expected)

    def test_H264_B_frame_keyframe_preroll_matches_actual_decoded_source(self):
        source,_,_=self.source();path=self.work/'gop.mp4'
        self.run_native([ffmpeg_path(),'-v','error','-i',source,'-an','-c:v','libx264','-g','12',
            '-bf','3','-pix_fmt','yuv420p',path])
        original=self.decode(path);size=helpers.W*helpers.H*4
        expected=b''.join(original[i*size:(i+1)*size] for i in range(27,1,-1))
        job=self.job(path);self.execute(job)
        self.assertEqual(self.decode(job['output']),expected)

    def test_10bit_native_planes_keep_nonzero_low_bits(self):
        source,_,_=self.source();path=self.work/'deep.nut'
        self.run_native([ffmpeg_path(),'-v','error','-i',source,'-an','-vf',
            'format=yuv444p10le,lutyuv=y=val+1:u=val+2:v=val+3','-c:v','ffv1','-pix_fmt','yuv444p10le',path])
        original=self.decode(path,pixel_format='yuv444p10le');size=helpers.W*helpers.H*6
        self.assertTrue(any(original[index]&3 for index in range(0,len(original),2)))
        job=self.job(path);self.execute(job)
        expected=b''.join(original[i*size:(i+1)*size] for i in range(27,1,-1))
        self.assertEqual(self.decode(job['output'],pixel_format='yuv444p10le'),expected)

    def test_native_VP9_alpha_decoder_preserves_all_alpha_bytes(self):
        source,_,_=self.source();path=self.work/'alpha.webm'
        self.run_native([ffmpeg_path(),'-v','error','-i',source,'-an','-vf','colorchannelmixer=aa=0.75',
            '-c:v','libvpx-vp9','-lossless','1','-auto-alt-ref','0','-pix_fmt','yuva420p',path])
        original=self.decode(path,decoder='libvpx-vp9');size=helpers.W*helpers.H*4
        self.assertTrue(any(a<255 for a in original[3::4]))
        job=self.job(path,decoder='libvpx-vp9');self.execute(job)
        expected=b''.join(original[i*size:(i+1)*size] for i in range(27,1,-1))
        self.assertEqual(self.decode(job['output']),expected)

    def test_ready_cache_hit_does_not_encode_or_decode_original_source(self):
        source,_,_=self.source();job=self.job(source);self.execute(job)
        before=Path(job['output']).read_bytes();calls=[];real=cache._capture
        def capture(command,**kw):calls.append(command);return real(command,**kw)
        with patch.object(cache,'_capture',side_effect=capture):result=self.execute(job)
        self.assertEqual(result['status'],'cache-hit');self.assertEqual(result['new_encodings'],0)
        self.assertEqual(result['new_source_decodes'],0)
        self.assertTrue(calls and all(command[0]==job['recipe']['artifacts']['ffprobe']['path'] for command in calls))
        self.assertEqual(Path(job['output']).read_bytes(),before)

    def test_corrupt_cache_rejects_and_preserves_modified_bytes(self):
        source,_,_=self.source();job=self.job(source);self.execute(job)
        output=Path(job['output']);output.write_bytes(output.read_bytes()+b'corrupt')
        before=output.read_bytes()
        with self.assertRaises(AppError) as caught:self.execute(job)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_CORRUPT')
        self.assertEqual(output.read_bytes(),before)

    def test_changed_source_rejects_before_any_worker(self):
        source,_,_=self.source();job=self.job(source);source.write_bytes(source.read_bytes()+b'changed')
        with patch.object(cache,'_capture',side_effect=AssertionError('must not execute')):
            with self.assertRaises(AppError) as caught:self.execute(job)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_INPUT_CHANGED')
        self.assertFalse(Path(job['output']).exists())

    def test_invalid_or_nonobject_receipt_rejects_with_structured_error(self):
        source,_,_=self.source();job=self.job(source);self.execute(job)
        for data in (b'{broken json',b'[]',b'null'):
            with self.subTest(data=data):
                Path(job['receipt']).write_bytes(data)
                with self.assertRaises(AppError) as caught:self.execute(job)
                self.assertEqual(caught.exception.code,'REVERSE_CACHE_CORRUPT')
                self.assertEqual(Path(job['receipt']).read_bytes(),data)

    def test_invalid_plan_output_cannot_escape_project_cache(self):
        source,_,_=self.source();job=self.job(source);job['output']=str(self.work/'outside.nut')
        with self.assertRaises(AppError) as caught:self.execute(job)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_PLAN_INVALID')
        self.assertFalse((self.work/'outside.nut').exists())

    def test_insufficient_disk_rejects_before_any_worker(self):
        source,_,_=self.source();job=self.job(source)
        with patch.object(cache.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(1,1,0)):
            with self.assertRaises(AppError) as caught:self.execute(job)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_DISK_SPACE')
        self.assertFalse(Path(job['output']).exists())

    def test_cancellation_before_start_does_not_create_cache(self):
        source,_,_=self.source();job=self.job(source);marker=self.work/'cancel';marker.touch()
        with patch.object(cache,'_capture',side_effect=AssertionError('must not execute')):
            with self.assertRaises(AppError) as caught:self.execute(job,cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')
        self.assertFalse(Path(job['output']).exists())

    def test_cancellation_between_chunks_rolls_back_staging(self):
        source,_,_=self.source();job=self.job(source);marker=self.work/'cancel';real=cache._capture
        def capture(command,**kw):
            result=real(command,**kw)
            if '-c:v' in command and 'ffv1' in command:marker.touch()
            return result
        with patch.object(cache,'_capture',side_effect=capture):
            with self.assertRaises(AppError) as caught:self.execute(job,cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')
        self.assertFalse(Path(job['output']).exists())
        self.assertFalse(list((self.root/'renders/.tmp/reverse-test').glob('reverse-chunks-*')))

    def test_active_native_worker_cancel_terminates_its_own_process(self):
        marker=self.work/'cancel';output=self.work/'cancelled.nut';children=[];real=cache.subprocess.Popen
        def capture(*args,**kw):
            process=real(*args,**kw);children.append(process);return process
        timer=threading.Timer(.3,marker.touch);timer.start()
        try:
            with patch.object(cache.subprocess,'Popen',side_effect=capture):
                with self.assertRaises(AppError) as caught:
                    cache._capture([ffmpeg_path(),'-v','error','-re','-f','lavfi','-i','testsrc2=size=32x18:rate=25',
                        '-t','30','-an','-c:v','ffv1',str(output)],cwd=self.work,cancel_file=marker)
            self.assertEqual(caught.exception.code,'CANCELLED')
            self.assertTrue(children and all(p.poll() is not None for p in children))
        finally:timer.cancel();timer.join(timeout=2)

if __name__=='__main__':unittest.main()
