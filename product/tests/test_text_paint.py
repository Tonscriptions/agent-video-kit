from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest

from PIL import Image

import test_word_highlight as fixture
from ai_ad_editor.errors import AppError
from ai_ad_editor.cli import main
from ai_ad_editor.project import asset_map
from ai_ad_editor.render import _compiled_subtitle_filter
from ai_ad_editor.utils import atomic_write_json

W, H, FPS, TPS = 320, 180, 24, 90000


class TextPaintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.WordHighlightTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixture.WordHighlightTests.tearDownClass.__func__(cls)

    call = fixture.WordHighlightTests.call
    render = fixture.WordHighlightTests.render

    def setUp(self):
        fixture.WordHighlightTests.setUp(self)
        self.background = None
        self.layer_opacity = None

    def prepare(self, subtitle, **options):
        fixture.WordHighlightTests.prepare(self, subtitle, **options)
        if self.background is not None:
            image = self.base / f'background-{self.serial}.png'
            Image.new('RGB', (W, H), self.background).save(image)
            self.call('media', 'ingest', '--project', self.root, '--input', image, '--asset-id', 'solid')
            path = self.base / f'background-change-{self.serial}.json'
            atomic_write_json(path, {'operations': [{'op': 'update_clip', 'track_id': 'track_video_1',
                'clip_id': 'video', 'patch': {'asset_id': 'solid'}}]})
            self.call('timeline', 'compose', '--project', self.root, '--input', path)
        if self.layer_opacity is not None:
            path = self.base / f'opacity-change-{self.serial}.json'
            atomic_write_json(path, {'operations': [{'op': 'update_clip', 'clip_id': 'title',
                'patch': {'transform': {'opacity': self.layer_opacity}}}]})
            self.call('timeline', 'compose', '--project', self.root, '--input', path)

    def title(self, color='0x4080c0@0.5', **style):
        return {'text': 'HHHH', 'style': {'font_asset_id': 'local_font', 'fontsize': 48,
                'fontcolor': color, 'box': False, 'x': '30', 'y': '80', **style}}

    def raw(self, subtitle):
        project = json.loads((self.template / 'project.json').read_text(encoding='utf-8-sig'))
        warnings = []
        graph, metadata = _compiled_subtitle_filter(self.template, subtitle, warnings,
            {'id': 'raw', 'timeline_start_tick': 0, 'duration_tick': TPS},
            0., 1., TPS, str(FPS), asset_map(project), independent=True)
        result = subprocess.run(['ffmpeg', '-v', 'error', '-filter_complex_threads', '1', '-f', 'lavfi',
            '-i', f'color=c=black:s={W}x{H}:r={FPS}:d=1,format=rgba,lutrgb=a=0',
            '-vf', graph, '-frames:v', str(FPS), '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'],
            cwd=self.template, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        self.assertEqual(len(result.stdout), W * H * 4 * FPS)
        return [Image.frombytes('RGBA', (W, H), result.stdout[i:i+W*H*4])
                for i in range(0, len(result.stdout), W*H*4)], metadata, warnings

    def solid(self, image):
        alpha = max(image.getchannel('A').getdata())
        return alpha, [p for p in image.getdata() if p[3] == alpha]

    def test_half_opacity_is_not_squared(self):
        frames, _, _ = self.raw(self.title('white@0.5'))
        alpha, pixels = self.solid(frames[4])
        self.assertLessEqual(abs(alpha - 127), 1)
        self.assertTrue(all(min(p[:3]) >= 253 for p in pixels))

    def test_arbitrary_rgb_stays_straight(self):
        frames, _, _ = self.raw(self.title())
        alpha, pixels = self.solid(frames[4])
        self.assertLessEqual(abs(alpha - 127), 1)
        self.assertLessEqual(max(abs(p[c] - value) for p in pixels for c, value in enumerate((64, 128, 192))), 2)

    def test_color_alpha_endpoints_and_quarters(self):
        for value, expected in [('0', 0), ('0.125', 31), ('0.25', 63), ('0.75', 191), ('1', 255)]:
            with self.subTest(alpha=value):
                frames, _, _ = self.raw(self.title('red@' + value))
                alpha, _ = self.solid(frames[3])
                self.assertLessEqual(abs(alpha - expected), 1)

    def test_hex_alpha_and_named_color_agree(self):
        first, _, _ = self.raw(self.title('0xff000080'))
        second, _, _ = self.raw(self.title('red@0x80'))
        self.assertEqual(first[4].tobytes(), second[4].tobytes())
        alpha, pixels = self.solid(first[4])
        self.assertLessEqual(abs(alpha - 128), 1)
        self.assertTrue(all(p[0] >= 253 and max(p[1:3]) <= 1 for p in pixels))

    def test_glyph_coverage_multiplies_authored_alpha_once(self):
        control, _, _ = self.raw(self.title('white'))
        actual, _, _ = self.raw(self.title('0x4080c0@0.5'))
        errors = [abs(a[3] - b[3] * 127/255) for a, b in zip(actual[5].getdata(), control[5].getdata())]
        self.assertLessEqual(max(errors), 2)
        edges = [a for a, b in zip(actual[5].getdata(), control[5].getdata()) if 40 < b[3] < 220 and a[3] > 15]
        self.assertGreater(len(edges), 20)
        self.assertLessEqual(max(abs(a[c] - v) for a in edges for c, v in enumerate((64, 128, 192))), 2)

    def test_box_alpha_has_independent_coverage(self):
        frames, _, _ = self.raw(self.title('white@0', box=True, boxcolor='0x204060@0.5', boxborderw=10))
        alpha, pixels = self.solid(frames[4])
        self.assertLessEqual(abs(alpha - 127), 1)
        self.assertGreater(len(pixels), 500)
        self.assertLessEqual(max(abs(p[c] - v) for p in pixels for c, v in enumerate((32, 64, 96))), 2)

    def test_border_and_shadow_alpha_are_not_squared(self):
        for extra in [dict(borderw=4, bordercolor='red@0.5'),
                      dict(shadowx=8, shadowy=6, shadowcolor='red@0.5')]:
            with self.subTest(component=extra):
                frames, _, _ = self.raw(self.title('white@0', **extra))
                alpha, pixels = self.solid(frames[4])
                self.assertLessEqual(abs(alpha - 127), 1)
                self.assertTrue(all(p[0] >= 253 and max(p[1:3]) <= 1 for p in pixels))

    def test_overlapping_style_components_follow_source_over(self):
        style = dict(box=True, boxborderw=9, boxcolor='blue@0.5', borderw=4,
                     bordercolor='green@0.5', shadowx=6, shadowy=5, shadowcolor='red@0.5')
        actual, _, _ = self.raw(self.title('white@0.5', **style))
        # Opaque component controls expose actual glyph geometry. Independent
        # source-over arithmetic supplies color/opacity truth for all overlaps.
        masks = []
        for component in ('boxcolor', 'shadowcolor', 'bordercolor', 'fontcolor'):
            values = {**style, 'boxcolor': 'black@0', 'shadowcolor': 'black@0', 'bordercolor': 'black@0'}
            title = self.title('black@0', **values)
            title['style'][component] = 'white'
            image, _, _ = self.raw(title)
            masks.append(list(image[5].getchannel('A').getdata()))
        maximum = 0
        for i, pixel in enumerate(actual[5].getdata()):
            rgb, alpha = [0., 0., 0.], 0.
            for mask, color in zip(masks, [(0, 0, 255), (255, 0, 0), (0, 128, 0), (255, 255, 255)]):
                a = mask[i]/255 * 127/255
                rgb = [c*a + value*(1-a) for c, value in zip(color, rgb)]
                alpha = a + alpha*(1-a)
            if alpha > .05:
                expected = [v/alpha for v in rgb] + [alpha*255]
                maximum = max(maximum, max(abs(p-v) for p, v in zip(pixel, expected)))
        self.assertLessEqual(maximum, 5)

    def test_fade_multiplies_color_alpha_after_painting(self):
        title = self.title('white@0.5')
        title['animation'] = {'type': 'fade_in', 'duration': 1.}
        frames, _, _ = self.raw(title)
        alpha, pixels = self.solid(frames[12])
        self.assertLessEqual(abs(alpha - 63.5), 1.5)
        self.assertTrue(all(min(p[:3]) >= 253 for p in pixels))

    def test_word_active_alpha_replaces_base_color(self):
        title = self.title('white', active_color='red@0.5')
        title['text'] = 'HH   HH'
        title['word_timing'] = [{'text': 'HH', 'start': .1, 'end': .5},
                                {'text': 'HH', 'start': .5, 'end': .9}]
        frames, _, _ = self.raw(title)
        for index, left in [(5, True), (16, False)]:
            selected = [(x, frames[index].getpixel((x, y))) for y in range(70, H) for x in range(W)
                        if frames[index].getpixel((x, y))[0] > 250 and frames[index].getpixel((x, y))[1] < 3
                        and frames[index].getpixel((x, y))[3] > 120]
            self.assertGreater(len(selected), 30)
            self.assertLessEqual(max(abs(p[3]-127) for _, p in selected), 2)
            mean = sum(x for x, _ in selected)/len(selected)
            self.assertTrue(mean < 110 if left else mean > 110)

    def test_multiline_color_uses_the_same_coverage(self):
        title = self.title('white', y='20', fontsize=40, line_spacing=12)
        title['text'] = 'HHHH\nHHHH'
        control, _, _ = self.raw(title)
        title['style']['fontcolor'] = '0x4080c0@0.25'
        actual, metadata, _ = self.raw(title)
        self.assertEqual(metadata['text_layout']['line_count'], 2)
        self.assertLessEqual(max(abs(a[3] - b[3]*63/255) for a,b in zip(actual[4].getdata(), control[4].getdata())), 2)
        visible = [p for p in actual[4].getdata() if p[3] > 40]
        self.assertGreater(len(visible), 100)
        self.assertLessEqual(max(abs(p[c]-v) for p in visible for c,v in enumerate((64,128,192))), 2)

    def check_composite(self, *, independent, opacity=1.):
        for background in [(12, 28, 44), (220, 232, 244)]:
            self.background = background
            blank = self.title('white'); blank['text'] = ' '
            underlying, _ = self.render(blank, independent=independent)
            opaque, _ = self.render(self.title('white'), independent=independent)
            self.layer_opacity = opacity if opacity != 1. else None
            actual, result = self.render(self.title(), independent=independent)
            self.layer_opacity = None
            errors = []
            for base, white, painted in zip(underlying[5].getdata(), opaque[5].getdata(), actual[5].getdata()):
                coverage = max(0., min(1., sum((w-b)/max(1, 255-b) for b,w in zip(base,white))/3))
                alpha = coverage*127/255*opacity
                expected = [c*alpha + b*(1-alpha) for b,c in zip(base,(64,128,192))]
                errors.extend(abs(x-y) for x,y in zip(painted,expected))
            self.assertLessEqual(max(errors), 5)
            records = json.loads(self.output.with_suffix('.mp4.manifest.json').read_text(encoding='utf-8-sig'))
            self.assertIn('straight-component-source-over', json.dumps(records))

    def test_encoded_independent_color_over_dark_and_light(self):
        self.check_composite(independent=True)

    def test_encoded_inline_color_over_dark_and_light(self):
        self.check_composite(independent=False)

    def test_layer_opacity_multiplies_authored_color_alpha(self):
        self.check_composite(independent=True, opacity=.5)

    def test_invalid_and_random_colors_rejected_without_author_mutation(self):
        for color in ('not-a-color', 'random'):
            title = self.title(color)
            self.prepare(title)
            project = (self.root/'project.json').read_bytes()
            ledger = (self.root/'rights-ledger.json').read_bytes()
            with self.assertRaises(AppError) as raised:
                self.raw(title)
            self.assertIn(raised.exception.code, ('SUBTITLE_COLOR_INVALID', 'SUBTITLE_COLOR_NONDETERMINISTIC'))
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(['render', '--project', str(self.root), '--output', str(self.output)])
            self.assertEqual(code, 2, stream.getvalue())
            self.assertIn(json.loads(stream.getvalue())['errors'][0]['code'],
                          ('SUBTITLE_COLOR_INVALID', 'SUBTITLE_COLOR_NONDETERMINISTIC'))
            self.assertEqual(project, (self.root/'project.json').read_bytes())
            self.assertEqual(ledger, (self.root/'rights-ledger.json').read_bytes())
            self.assertFalse(self.output.exists())
