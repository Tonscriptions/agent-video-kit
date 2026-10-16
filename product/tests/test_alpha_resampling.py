from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image, ImageDraw

from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json


class AlphaResamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'project'
        self.call('project', 'init', self.root)
        project = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        project['settings']['canvas'].update(width=120, height=80)
        project['settings']['timebase']['display_fps'] = {'num': 4, 'den': 1}
        project['sequences'][0]['duration_tick'] = 90000
        atomic_write_json(self.root/'project.json', project)
        self.compose([{'op': 'add_track', 'track_id': 'labels', 'kind': 'video', 'order': 2}])
        alpha = Image.new('L', (24, 24), 0)
        draw = ImageDraw.Draw(alpha)
        draw.ellipse((3, 3, 20, 20), fill=255)
        draw.line((0, 0, 23, 23), fill=128, width=2)
        self.alpha = alpha
        for name, hidden in [('black', (0, 0, 0)), ('green', (0, 255, 0))]:
            image = Image.new('RGBA', (24, 24), (*hidden, 0))
            image.paste((255, 0, 255, 255), mask=alpha.point(lambda a: 255 if a else 0))
            image.putalpha(alpha)
            image.save(self.base/f'{name}.png')
            self.call('media', 'ingest', '--project', self.root, '--input', self.base/f'{name}.png', '--asset-id', name)

    def call(self, *args):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            code = main(list(map(str, args)))
        value = json.loads(capture.getvalue())
        self.assertEqual(code, 0, value)
        return value

    def compose(self, operations):
        path = self.base/'changes.json'
        path.write_text(json.dumps({'operations': operations}), encoding='utf-8')
        self.call('timeline', 'compose', '--project', self.root, '--input', path)

    def render(self, asset, fit, *, animated=False):
        clip = {'asset_id': asset, 'source_in_tick': 0, 'source_out_tick': 90000, 'duration_tick': 90000,
                'transform': {'scale': .43}, 'crop': {'fit': fit}}
        if animated:
            clip['keyframes'] = [{'property': 'transform.scale', 'keyframes': [
                {'at_tick': 0, 'value': .43, 'interpolation': 'linear'},
                {'at_tick': 90000, 'value': .61, 'interpolation': 'linear'}]}]
        self.compose([{'op': 'append_clip', 'track_id': 'labels', 'id': asset+'_clip', **clip}])
        output = self.root/f'renders/{asset}-{fit}.mp4'
        self.call('render', '--project', self.root, '--output', output)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-map', '0:v:0', '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True).stdout
        self.assertEqual(len(raw), 4*120*80*3)
        self.compose([{'op': 'remove_clip', 'track_id': 'labels', 'clip_id': asset+'_clip'}])
        return raw

    def compare_hidden_rgb(self, fit, *, animated=False, video=False, palette=False):
        names = ['black', 'green']
        if video or palette:
            names = []
            for name in ['black', 'green']:
                target = self.base/f'{name}-converted.mov' if video else self.base/f'{name}-palette.png'
                if video:
                    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', str(self.base/f'{name}.png'), '-t', '1', '-r', '4', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(target)], capture_output=True, check=True)
                else:
                    original = Image.open(self.base/f'{name}.png').convert('RGBA')
                    indexed = Image.new('P', original.size)
                    indexed.putpalette([0, 255 if name == 'green' else 0, 0, 255, 0, 255, 255, 0, 255]+[0]*759)
                    indexed.putdata([0 if a == 0 else 1 if a == 255 else 2 for a in self.alpha.tobytes()])
                    indexed.save(target, transparency=bytes([0, 255, 128]))
                asset = name+'_converted'
                self.call('media', 'ingest', '--project', self.root, '--input', target, '--asset-id', asset)
                names.append(asset)
        first = self.render(names[0], fit, animated=animated)
        second = self.render(names[1], fit, animated=animated)
        differences = [abs(a-b) for a, b in zip(first, second)]
        self.assertEqual(max(differences), 0, 'Fully transparent RGB must not contaminate visible resampled pixels')
        self.assertGreater(max(first), 200)

    def test_png_fit_hidden_rgb_has_no_visible_influence(self):
        self.compare_hidden_rgb('fit')

    def test_png_fill_hidden_rgb_has_no_visible_influence(self):
        self.compare_hidden_rgb('fill')

    def test_png_stretch_hidden_rgb_has_no_visible_influence(self):
        self.compare_hidden_rgb('stretch')

    def test_animated_scale_hidden_rgb_has_no_visible_influence(self):
        self.compare_hidden_rgb('fit', animated=True)

    def test_alpha_video_hidden_rgb_has_no_visible_influence(self):
        self.compare_hidden_rgb('fit', video=True)

    def test_indexed_png_hidden_rgb_has_no_visible_influence(self):
        self.compare_hidden_rgb('fit', palette=True)


if __name__ == '__main__':
    unittest.main()
