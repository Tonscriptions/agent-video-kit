"""Actual empty video intervals preserve the visible underlying author canvas."""
from __future__ import annotations
import copy
from fractions import Fraction
import json
import unittest
from PIL import Image
from test_magnetic_reorder import invoke
from ai_ad_editor.media import ffmpeg_path, ffprobe_path
from ai_ad_editor.project import save_project
import test_cfr_boundaries as helpers


class NativeEmptyWindowTests(unittest.TestCase):
    setUp = helpers.CFRBoundaryTests.setUp
    run_native = helpers.CFRBoundaryTests.run_native
    source = helpers.CFRBoundaryTests.source
    project = helpers.CFRBoundaryTests.project
    render = helpers.CFRBoundaryTests.render

    def empty_window(self, *, prefix=False, reverse=False, nested=False):
        background=self.work/'background.png'
        Image.new('RGBA',(helpers.W,helpers.H),(12,210,75,255)).save(background)
        code,value=invoke('media','ingest','--project',self.root,'--input',background,'--asset-id','background')
        self.assertEqual(code,0,value)
        path, _, _ = self.source(count=8, container='mkv', audio_tail=True)
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
        if nested:
            child = copy.deepcopy(root)
            child['id'] = 'child'
            child['duration_tick'] = 180000
            for track in child['tracks']:
                track['id'] = 'child_' + track['id']
            leaf = child['tracks'][0]['clips'][0]
            leaf.update(id='leaf', timeline_start_tick=0, duration_tick=180000,
                        source_in_tick=0, source_out_tick=180000, reverse=False)
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


if __name__ == '__main__':
    unittest.main()
