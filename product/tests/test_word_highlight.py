from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from PIL import Image, ImageFont

import test_nested_time_mapping as fixture
from ai_ad_editor.cli import main
from ai_ad_editor.utils import atomic_write_json

W, H, FPS, TPS = 320, 180, 24, 90000


class WordHighlightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NestedTimeMappingTests.setUpClass.__func__(cls)
        cls.font_file = cls.fixture_root / 'local-aileron.ttf'
        cls.font_file.write_bytes(ImageFont.load_default(size=16).path.getvalue())

    @classmethod
    def tearDownClass(cls):
        fixture.NestedTimeMappingTests.tearDownClass.__func__(cls)

    call = fixture.NestedTimeMappingTests.call

    def setUp(self):
        fixture.NestedTimeMappingTests.setUp(self)
        self.call('media', 'ingest', '--project', self.root, '--input', self.font_file, '--asset-id', 'local_font')
        project = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        project['settings']['canvas'].update(width=W, height=H)
        project['sequences'][0]['duration_tick'] = TPS
        atomic_write_json(self.root/'project.json', project)
        self.template = self.root
        self.serial = 0

    def subtitle(self, text='FEATURE BENEFIT', **style):
        words = text.split()
        return {'text': text, 'style': {'font_asset_id': 'local_font', 'fontsize': 24,
                'x': '30', 'y': '110', 'box': False, **style},
                'word_timing': [{'text': word, 'start': .05+i*.8/len(words), 'end': .05+(i+1)*.8/len(words)} for i, word in enumerate(words)]}

    def prepare(self, subtitle, *, independent=True, dynamic=False):
        self.serial += 1
        self.root = self.base/f'case-{self.serial}'
        shutil.copytree(self.template, self.root)
        video = {'op': 'append_clip', 'track_id': 'track_video_1', 'id': 'video', 'asset_id': 'frames',
                 'source_in_tick': 0, 'source_out_tick': TPS, 'duration_tick': TPS}
        if dynamic:
            video['keyframes'] = [{'property': 'scale', 'keyframes': [{'at_tick': 0, 'value': .9, 'interpolation': 'linear'}, {'at_tick': TPS, 'value': 1., 'interpolation': 'linear'}]}]
        operations = [video]
        if independent:
            operations.extend([{'op': 'add_track', 'track_id': 'titles', 'kind': 'subtitle', 'order': 2},
                               {'op': 'append_clip', 'track_id': 'titles', 'id': 'title',
                                'generator': {'type': 'text'}, 'source_in_tick': 0, 'source_out_tick': TPS,
                                'duration_tick': TPS, 'subtitle': subtitle}])
        else:
            video['subtitle'] = subtitle
        path = self.base/f'changes-{self.serial}.json'
        atomic_write_json(path, {'operations': operations})
        self.call('timeline', 'compose', '--project', self.root, '--input', path)
        self.output = self.root/'renders/words.mp4'

    def render(self, subtitle, **options):
        self.prepare(subtitle, **options)
        before = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        ledger = (self.root/'rights-ledger.json').read_bytes()
        value = self.call('render', '--project', self.root, '--output', self.output,
                          '--crf', '0', '--pixel-format', 'yuv444p')
        after = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        self.assertEqual({k: before[k] for k in ('settings', 'assets', 'sequences')},
                         {k: after[k] for k in ('settings', 'assets', 'sequences')})
        self.assertEqual(ledger, (self.root/'rights-ledger.json').read_bytes())
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.output), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
                             capture_output=True, check=True).stdout
        self.assertEqual(len(raw), FPS*W*H*3)
        return [Image.frombytes('RGB', (W, H), raw[i:i+W*H*3]) for i in range(0, len(raw), W*H*3)], value

    def compare_geometry(self, subtitle, *, independent=True):
        reference = copy.deepcopy(subtitle)
        reference.pop('word_timing')
        base, _ = self.render(reference, independent=independent)
        frames, result = self.render(subtitle, independent=independent)
        # White and yellow have identical R/G. A lossless 4:4:4 delivery can
        # differ by at most 3 after RGB/YUV round trips, irrespective of time,
        # word identity or typography. Shifted/double-painted glyphs cannot.
        maximum = 0
        for a, b in zip(base, frames):
            for channel in ('R', 'G'):
                maximum = max(maximum, max(abs(x-y) for x, y in zip(a.getchannel(channel).tobytes(), b.getchannel(channel).tobytes())))
        self.assertLessEqual(maximum, 3, f'Glyph shape/position/opacity changed: {maximum}')
        self.assertGreater(sum(r > 90 and g > 90 and r-b > 15 and g-b > 15 for frame in frames for r,g,b in frame.crop((0,70,W,H)).getdata()), 30)
        return base, frames, result

    def test_same_color_highlight_never_repaints_antialiasing(self):
        subtitle = self.subtitle(active_color='white')
        reference = copy.deepcopy(subtitle); reference.pop('word_timing')
        base, _ = self.render(reference)
        frames, _ = self.render(subtitle)
        self.assertEqual([x.tobytes() for x in base], [x.tobytes() for x in frames])

    def test_inline_word_glyph_geometry(self):
        self.compare_geometry(self.subtitle(), independent=False)

    def test_default_center_keeps_the_whole_paragraph_anchor(self):
        subtitle = self.subtitle(); subtitle['style'].pop('x')
        _, frames, _ = self.compare_geometry(subtitle)
        centers = []
        for i in (4, 16):
            xs = [x for y in range(90,H) for x in range(W) if (lambda p: p[0]>170 and p[1]>145 and p[2]<100)(frames[i].getpixel((x,y)))]
            self.assertGreater(len(xs), 20); centers.append(sum(xs)/len(xs))
        self.assertLess(centers[0], W/2); self.assertGreater(centers[1], W/2)

    def test_multiline_descenders_and_right_alignment(self):
        base,frames,_=self.compare_geometry(self.subtitle('gyp   HI\nFEATURE   BENEFIT', x='22', y='88', fontsize=20,
                                            line_spacing=11, text_align='right+bottom', boxw=270, boxh=80))
        # A correct R/G outline alone cannot detect coloring the wrong glyph.
        # Locate the largest whitespace gap in the actual first control row.
        white=lambda x,y:min(base[4].getpixel((x,y)))>160
        rows=[y for y in range(70,H) if any(white(x,y) for x in range(W))]
        first=[rows[0]]
        for y in rows[1:]:
            if y-first[-1]>3:break
            first.append(y)
        columns=[x for x in range(W) if any(white(x,y) for y in first)]
        gaps=[];current=[]
        for x in range(columns[0],columns[-1]+1):
            if x not in columns:current.append(x)
            elif current:gaps.append(current);current=[]
        gap=max(gaps,key=len);split=gap[len(gap)//2]
        self.assertEqual(sum(base[4].getpixel((x,y))[2]-frames[4].getpixel((x,y))[2]>45
                             for y in first for x in range(split,W)),0)

    def test_plain_multiline_never_paints_a_newline_glyph(self):
        subtitle=self.subtitle('HH\nHH',x='30',y='80',line_spacing=12)
        subtitle.pop('word_timing')
        frames,_=self.render(subtitle)
        im=frames[5]
        selected=lambda x,y:min(im.getpixel((x,y)))>160
        ys=[y for y in range(70,H) if any(selected(x,y) for x in range(W))]
        lines=[]
        for y in ys:
            if not lines or y-lines[-1][-1]>3:lines.append([y])
            else:lines[-1].append(y)
        self.assertEqual(len(lines),2)
        for line in lines:
            xs=[x for x in range(W) if any(selected(x,y) for y in line)]
            groups=[]
            for x in xs:
                if not groups or x-groups[-1][-1]>1:groups.append([x])
                else:groups[-1].append(x)
            self.assertEqual(len(groups),2,'LF must not add a visible glyph')

    def test_multiline_box_and_alias_alignment(self):
        self.compare_geometry(self.subtitle('gyp   HI\nFEATURE   BENEFIT',x='10',y='70',fontsize=20,
                                            line_spacing=8,box=True,boxcolor='blue@0.3',box_padding=6,
                                            boxw=280,boxh=90,text_align='left+right+top+bottom',borderw=1))

    def test_wrapping_and_repeated_words_follow_source_lines(self):
        self.compare_geometry(self.subtitle('FEATURE  BENEFIT  FEATURE', x='24', y='76', fontsize=20,
                                            max_width=160, line_spacing=5, text_align='center', boxw=270))

    def test_wrapped_word_selection_never_leaks_into_the_next_row(self):
        subtitle=self.subtitle('HH HH HH',x='30',y='70',max_width=40,line_spacing=0)
        base,frames,_=self.compare_geometry(subtitle)
        for index,(control,frame) in enumerate(zip(base,frames)):
            selected=lambda x,y:min(control.getpixel((x,y)))>160
            ys=[y for y in range(65,H) if any(selected(x,y) for x in range(W))]
            lines=[]
            for y in ys:
                if not lines or y-lines[-1][-1]>3:lines.append([y])
                else:lines[-1].append(y)
            self.assertEqual(len(lines),3)
            for word,line in enumerate(lines):
                points=[(x,y) for y in line for x in range(W) if selected(x,y)]
                count=sum(control.getpixel((x,y))[2]-frame.getpixel((x,y))[2]>45 for x,y in points)
                entry=subtitle['word_timing'][word]
                expected=entry['start']<=index/FPS<entry['end']
                fraction=count/len(points)
                self.assertGreaterEqual(fraction,.98) if expected else self.assertLessEqual(fraction,.01)

    def test_combining_marks_and_literal_percent(self):
        self.compare_geometry(self.subtitle('Cafe\u0301 AV 50%', expansion='none'))

    def test_border_shadow_and_box_preserve_geometry(self):
        self.compare_geometry(self.subtitle(borderw=2, bordercolor='black', shadowx=3, shadowy=4,
                                            shadowcolor='black@0.6', box=True, boxcolor='blue@0.3', box_padding=7))

    def test_custom_time_position_and_fix_bounds(self):
        self.compare_geometry(self.subtitle(x='-4+12*t', y='170+2*sin(t)', fix_bounds=True))

    def test_translucent_foreground_is_not_painted_twice(self):
        self.compare_geometry(self.subtitle(fontcolor='white@0.65', active_color='yellow@0.65'))

    def test_active_opacity_can_replace_opaque_foreground(self):
        subtitle = self.subtitle('BENEFIT', active_color='white@0.25')
        subtitle['word_timing'][0].update(start=0., end=1.)
        reference = copy.deepcopy(subtitle); reference.pop('word_timing'); reference['style']['fontcolor']='white@0.25'
        base, _ = self.render(reference)
        frames, _ = self.render(subtitle)
        self.assertEqual([x.tobytes() for x in base], [x.tobytes() for x in frames])

    def test_a_timed_range_can_cross_a_newline(self):
        subtitle = self.subtitle('gyp HI\nFEATURE BENEFIT', y='86', fontsize=20, line_spacing=11)
        subtitle['word_timing'] = [{'text': 'HI\nFEATURE', 'start': .1, 'end': .8}]
        self.compare_geometry(subtitle)

    def test_explicit_repeated_start_char_leaves_first_word_untouched(self):
        subtitle = self.subtitle('AV   AV')
        subtitle['word_timing'] = [{'text': 'AV', 'start_char': 5, 'start': 0., 'end': 1.}]
        _, frames, _ = self.compare_geometry(subtitle)
        yellow = [(x,y) for y in range(90,H) for x in range(W) if (lambda p: p[0]>170 and p[1]>145 and p[2]<100)(frames[8].getpixel((x,y)))]
        self.assertGreater(min(x for x,y in yellow), 72)

    def test_native_layout_does_not_require_pillow_metrics(self):
        with patch('ai_ad_editor.render._load_subtitle_font_metrics', return_value=None):
            _, _, result = self.compare_geometry(self.subtitle())
        manifest = json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8-sig')) if isinstance(result['data'].get('manifest'), str) else json.loads(Path(str(self.output)+'.manifest.json').read_text(encoding='utf-8-sig'))
        metadata = [x['subtitle_time_mapping']['text_layout'] for x in manifest['inputs'] if x.get('subtitle_time_mapping', {}).get('text_layout')]
        self.assertTrue(metadata)
        self.assertEqual(metadata[0]['font_sha256'], hashlib.sha256(self.font_file.read_bytes()).hexdigest())

    def reject(self, subtitle, code):
        self.prepare(subtitle)
        project, ledger = (self.root/'project.json').read_bytes(), (self.root/'rights-ledger.json').read_bytes()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(['render', '--project', str(self.root), '--output', str(self.output), '--dry-run'])
        result = json.loads(output.getvalue())
        self.assertNotEqual(status, 0)
        self.assertIn(code, [x['code'] for x in result['errors']])
        self.assertFalse(self.output.exists())
        self.assertEqual(project, (self.root/'project.json').read_bytes())
        self.assertEqual(ledger, (self.root/'rights-ledger.json').read_bytes())

    def test_bidi_mapping_is_rejected_explicitly(self):
        self.reject(self.subtitle('\u05e9\u05dc\u05d5\u05dd HI'), 'SUBTITLE_WORD_BIDI_UNSUPPORTED')

    def test_split_grapheme_is_rejected_explicitly(self):
        subtitle = self.subtitle('Cafe\u0301')
        subtitle['word_timing'][0]['text']='Cafe'
        self.reject(subtitle, 'SUBTITLE_WORD_GRAPHEME_BOUNDARY')

    def test_internal_ligature_range_is_rejected_explicitly(self):
        subtitle = self.subtitle('office')
        subtitle['word_timing'][0]['text']='of'
        self.reject(subtitle, 'SUBTITLE_WORD_CLUSTER_LAYOUT_UNSUPPORTED')

    def test_dynamic_inline_keeps_a_visible_degradation(self):
        self.prepare(self.subtitle(), independent=False, dynamic=True)
        result = self.call('render', '--project', self.root, '--output', self.output)
        self.assertTrue(self.output.exists())
        self.assertIn('subtitle_word_dynamic_raster', [x.get('feature') for x in result['data']['warnings']])

    def test_word_animation_limitation_is_reported(self):
        subtitle = self.subtitle(); subtitle['animation']={'type':'fade_in', 'duration':.3}
        self.prepare(subtitle)
        result = self.call('render', '--project', self.root, '--output', self.output, '--dry-run')
        self.assertIn('subtitle_word_animation', [x.get('feature') for x in result['data']['plan']['warnings']])
