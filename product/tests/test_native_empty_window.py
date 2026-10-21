"""Actual empty video intervals preserve the visible underlying author canvas."""
from __future__ import annotations
import copy
from array import array
from fractions import Fraction
import hashlib
import json
import unittest
from unittest.mock import patch
from PIL import Image
from test_magnetic_reorder import invoke
from ai_ad_editor.media import ffmpeg_path, ffprobe_path
from ai_ad_editor.project import save_project
from ai_ad_editor.errors import AppError
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor import reverse_video_clock as clocks
import test_cfr_boundaries as helpers


class NativeEmptyWindowTests(unittest.TestCase):
    setUp = helpers.CFRBoundaryTests.setUp
    run_native = helpers.CFRBoundaryTests.run_native
    source = helpers.CFRBoundaryTests.source
    project = helpers.CFRBoundaryTests.project
    render = helpers.CFRBoundaryTests.render

    def empty_window(self, *, prefix=False, reverse=False, nested=False, audible=False):
        background=self.work/'background.png'
        Image.new('RGBA',(helpers.W,helpers.H),(12,210,75,255)).save(background)
        code,value=invoke('media','ingest','--project',self.root,'--input',background,'--asset-id','background')
        self.assertEqual(code,0,value)
        path, _, _ = self.source(count=8, container='mkv', audio_tail=True)
        if audible:
            audible_path=self.work/'audible.mkv'
            self.run_native([ffmpeg_path(),'-v','error','-i',path,'-f','lavfi','-i',
                'aevalsrc=0.2*sin(2*PI*440*t)|0.17*sin(2*PI*731*t):s=48000:d=2',
                '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','pcm_f32le',audible_path])
            path=audible_path
        if prefix:
            delayed = self.work / 'delayed.mkv'
            self.run_native([ffmpeg_path(), '-v', 'error', '-i', path, '-filter_complex',
                '[0:v]setpts=PTS+1/TB[v]', '-map', '[v]', '-map', '0:a:0', '-t', '2',
                '-fps_mode', 'passthrough', '-enc_time_base', 'filter', '-c:v', 'ffv1',
                '-pix_fmt', 'bgra', '-c:a', 'pcm_s16le', delayed])
            path = delayed
        probe = json.loads(self.run_native([ffprobe_path(), '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_streams', '-show_format', '-show_entries',
            'frame=pts:stream=time_base:format=start_time,duration', '-of', 'json', path]))
        points = [int(frame['pts']) * Fraction(probe['streams'][0]['time_base']) for frame in probe['frames']]
        self.assertEqual(len(points), 8)
        self.assertEqual(points[0], Fraction(1 if prefix else 0))
        self.assertEqual(Fraction(probe['format']['start_time']), 0)
        self.assertGreaterEqual(Fraction(probe['format']['duration']), Fraction(3, 2))
        left = 0 if prefix else 90000
        right = left + 45000
        project, root, clip = self.project(path, start=9900, duration=45000,
                                         source_in=left, source_out=right, patch={'reverse': reverse})
        if audible:
            root['tracks'][1]['clips']=[{**copy.deepcopy(clip),'id':'clip_audio'}]
        if nested:
            child = copy.deepcopy(root)
            child['id'] = 'child'
            child['duration_tick'] = 180000
            for track in child['tracks']:
                track['id'] = 'child_' + track['id']
            leaf = child['tracks'][0]['clips'][0]
            leaf.update(id='leaf', timeline_start_tick=0, duration_tick=180000,
                        source_in_tick=0, source_out_tick=180000, reverse=False)
            if audible:
                child['tracks'][1]['clips']=[{**copy.deepcopy(leaf),'id':'leaf_audio'}]
                root['tracks'][1]['clips']=[]
            root['tracks'][0]['clips'] = [{'id': 'parent', 'sequence_id': 'child',
                'timeline_start_tick': 9900, 'duration_tick': 45000,
                'source_in_tick': left, 'source_out_tick': right, 'reverse': reverse,
                'speed_curve': {'keyframes': [{'at_tick': 0, 'speed': 1.},
                                             {'at_tick': 45000, 'speed': 1.}]}}]
            project['sequences'].append(child)
        root['tracks'][0]['order']=1
        root['tracks'].append({'id':'background','kind':'video','order':0,'clips':[{
            'id':'background','asset_id':'background','timeline_start_tick':0,
            'duration_tick':135000,'source_in_tick':0,'source_out_tick':135000}]})
        save_project(self.root, project)
        reference = copy.deepcopy(project)
        reference['sequences'][0]['tracks'][0]['clips'] = []
        expected, _, _ = self.render(reference, reference['sequences'][0])
        self.assertNotEqual(expected[0][:4], bytes((0, 0, 0, 255)), 'The underlying canvas must expose opaque-black substitutes.')
        actual, _, _ = self.render(project, root)
        self.assertEqual(actual, expected, 'A source window without video display intervals must leave the underlying canvas visible.')
        if audible:
            inputs,graph,_,_=build_filter_graph(self.root,project,root)
            actual_audio=self.run_native([ffmpeg_path(),'-v','error','-filter_complex_threads','1',
                *inputs,'-filter_complex',graph,'-map','[aout]','-f','f32le','-c:a','pcm_f32le','pipe:1',
                '-map','[vout]','-f','null','NUL'],cwd=self.root)
            source_audio=self.run_native([ffmpeg_path(),'-v','error','-i',path,'-map','0:a:0',
                '-ar','48000','-ac','2','-f','f32le','-c:a','pcm_f32le','pipe:1'])
            sample_start=0 if prefix else 48000
            core=source_audio[sample_start*8:(sample_start+24000)*8]
            self.assertEqual(len(core),24000*8)
            self.assertGreater(max(abs(x) for x in array('f',core)),.1)
            if reverse:core=b''.join(core[i:i+8] for i in range(len(core)-8,-1,-8))
            expected_audio=bytes(5280*8)+core+bytes((72000-5280-24000)*8)
            self.assertEqual(len(actual_audio),len(expected_audio))
            self.assertEqual(hashlib.sha256(actual_audio).hexdigest(),hashlib.sha256(expected_audio).hexdigest(),
                'The empty video selection must retain its complete, independently decoded stereo PCM selection.')

    def test_direct_forward_audio_tail_without_video_is_empty(self):
        self.empty_window()

    def test_direct_reverse_audio_tail_without_video_is_empty(self):
        self.empty_window(reverse=True)

    def test_nested_forward_audio_tail_without_video_is_empty(self):
        self.empty_window(nested=True)

    def test_nested_reverse_audio_tail_without_video_is_empty(self):
        self.empty_window(nested=True, reverse=True)

    def test_direct_forward_before_delayed_video_is_empty(self):
        self.empty_window(prefix=True)

    def test_direct_reverse_before_delayed_video_is_empty(self):
        self.empty_window(prefix=True, reverse=True)

    def test_nested_forward_before_delayed_video_is_empty(self):
        self.empty_window(prefix=True, nested=True)

    def test_nested_reverse_before_delayed_video_is_empty(self):
        self.empty_window(prefix=True, nested=True, reverse=True)

    def test_direct_reverse_empty_tail_preserves_all_audio_samples(self):
        self.empty_window(reverse=True,audible=True)

    def test_direct_reverse_empty_prefix_preserves_all_audio_samples(self):
        self.empty_window(prefix=True,reverse=True,audible=True)

    def test_nested_forward_empty_tail_preserves_all_audio_samples(self):
        self.empty_window(nested=True,audible=True)

    def test_nested_forward_empty_prefix_preserves_all_audio_samples(self):
        self.empty_window(prefix=True,nested=True,audible=True)

    def test_nested_reverse_empty_tail_preserves_all_audio_samples(self):
        self.empty_window(nested=True,reverse=True,audible=True)

    def test_nested_reverse_empty_prefix_preserves_all_audio_samples(self):
        self.empty_window(prefix=True,nested=True,reverse=True,audible=True)

    def unknown_video_eof(self,reverse):
        path,_,_=self.source(count=8,container='mkv',audio_tail=True)
        points,durations,stream,format_info=clocks.probe_frames(path)
        durations=array('q',durations);durations[-1]=0
        with patch.object(clocks,'probe_frames',return_value=(points,durations,stream,format_info)):
            arguments=(path,90000,135000,90000)
            with self.assertRaises(AppError) as caught:
                if reverse:clocks.reverse_intervals(*arguments,'1/90000',expected_time_base=stream['time_base'])
                else:clocks.forward_intervals(*arguments,expected_time_base=stream['time_base'])
        self.assertEqual(caught.exception.code,'REVERSE_VIDEO_CLOCK_INVALID' if reverse else 'NESTED_NATIVE_CLOCK_INVALID')
        self.assertIn('no known native duration',caught.exception.cause)

    def test_unknown_final_duration_cannot_be_treated_as_empty_forward(self):
        self.unknown_video_eof(False)

    def test_unknown_final_duration_cannot_be_treated_as_empty_reverse(self):
        self.unknown_video_eof(True)


if __name__ == '__main__':
    unittest.main()
