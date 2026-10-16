from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import ImageChops
import test_word_highlight as fixture

W, H, FPS = 320, 180, 24


class TextAnimationCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.WordHighlightTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): fixture.WordHighlightTests.tearDownClass.__func__(cls)
    setUp = fixture.WordHighlightTests.setUp
    call = fixture.WordHighlightTests.call
    prepare = fixture.WordHighlightTests.prepare
    render = fixture.WordHighlightTests.render
    subtitle = fixture.WordHighlightTests.subtitle
    reject = fixture.WordHighlightTests.reject

    def title(self, text='HHHH', **style):
        return {'text': text, 'style': {'font_asset_id': 'local_font', 'fontsize': 24,
                'x': '30', 'y': '110', 'box': False, 'expansion': 'none', **style}}

    def max_error(self, actual, expected, channels=3):
        return max(value[1] for value in ImageChops.difference(actual, expected).getextrema()[:channels])

    def metadata(self, result):
        manifest=json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8-sig'))
        return next(value['subtitle_time_mapping'] for value in manifest['inputs'] if value.get('subtitle_time_mapping'))

    def same_geometry(self, animation, *, independent=True, in_style=False, text='FEATURE BENEFIT', **style):
        subtitle=self.subtitle(text, **{'fontsize':23, 'x':'20', 'y':'100', **style})
        if in_style: subtitle['style']['animation']=animation
        else: subtitle['animation']=animation
        control=copy.deepcopy(subtitle);control.pop('word_timing')
        expected,_=self.render(control, independent=independent)
        actual,result=self.render(subtitle, independent=independent)
        self.assertLessEqual(max(self.max_error(a,b,2) for a,b in zip(actual,expected)),3)
        self.assertNotIn('subtitle_word_animation',[item.get('feature') for item in result['data']['warnings']])
        return actual,result

    def test_word_fade_in_and_out_match_untimed_animation(self):
        for kind in ('fade_in','fade_out'):
            with self.subTest(kind=kind):self.same_geometry({'type':kind,'delay':.1,'duration':.65})

    def test_word_slides_share_the_animated_selection_origin(self):
        for direction in ('up','down','left','right'):
            with self.subTest(direction=direction):self.same_geometry({'type':'slide_'+direction,'duration':.6,'distance':35})

    def test_word_pop_and_bounce_apply_motion_and_alpha(self):
        for kind in ('pop','bounce'):
            with self.subTest(kind=kind):self.same_geometry({'type':kind,'delay':.05,'duration':.7,'distance':25})

    def test_word_rotation_retains_the_same_fade_and_pose(self):
        self.same_geometry({'type':'rotate','delay':.05,'duration':.8,'from_degrees':-12,'to_degrees':12})

    def test_style_animation_and_fixed_inline_highlight_compose(self):
        self.same_geometry({'type':'fade_in','duration':.7},independent=False,in_style=True)
        self.same_geometry({'type':'slide_left','duration':.7,'distance':30},independent=False)

    def test_word_typewriter_reveals_both_color_paints(self):
        for independent in (False,True):
            with self.subTest(independent=independent):
                _,result=self.same_geometry({'type':'typewriter','delay':.05,'duration':.75},independent=independent)
                evidence=self.metadata(result)['text_layout']['typing']
                self.assertEqual(evidence['engine'],'native-prefix-runtime-text')
                self.assertEqual(evidence['paint_count'],2)
                self.assertEqual(evidence['native_target_count'],2)
                self.assertGreater(evidence['command_count'],0)

    def test_later_plain_plan_keeps_an_earlier_word_command_file_intact(self):
        title=self.subtitle();title['animation']={'type':'typewriter','duration':.75}
        self.prepare(title)
        plan=self.call('render','--project',self.root,'--output',self.output,'--dry-run')['data']['plan']
        earlier=next(v['subtitle_time_mapping']['text_layout']['typing'] for v in plan['inputs'] if v.get('subtitle_time_mapping'))
        path=self.root/earlier['command_file'];original=path.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),earlier['command_file_sha256'])
        plain=copy.deepcopy(title);plain.pop('word_timing')
        change=self.base/'plain-plan.json';change.write_text(json.dumps({'operations':[
            {'op':'update_clip','track_id':'titles','clip_id':'title','patch':{'subtitle':plain}}]}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',change)
        self.call('render','--project',self.root,'--output',self.root/'renders/later.mp4','--dry-run')
        self.assertEqual(path.read_bytes(),original,'A later plan changed an earlier compiled command stream')

    def test_translucent_typewriter_updates_every_native_component(self):
        _,result=self.same_geometry({'type':'typewriter','delay':.05,'duration':.75},
            fontcolor='white@0.5',active_color='yellow@0.5',box=True,boxcolor='blue@0.3',
            borderw=2,bordercolor='green@0.6',shadowx=3,shadowy=4,shadowcolor='red@0.4')
        evidence=self.metadata(result)['text_layout']['typing']
        # Normal/active fills, outlines and shadows must all receive updates.
        self.assertEqual(evidence['native_target_count'],6)

    def test_multiline_typewriter_and_word_selection_share_baselines(self):
        self.same_geometry({'type':'typewriter','delay':.05,'duration':.75},
                           text='FEATURE\nBENEFIT',y='70',line_spacing=9)

    def test_prefix_kerning_matches_individually_authored_native_runs(self):
        text='AVATAR';delay=.05;duration=.7
        title=self.title(text,y='115-top_a');title['animation']={'type':'typewriter','delay':delay,'duration':duration}
        actual,_=self.render(title)
        prefixes={}
        for i in range(FPS):
            count=sum(i/FPS>=round(delay+j*duration/len(text),9) for j in range(len(text)))
            if count not in prefixes:prefixes[count]=self.render(self.title(text[:count],y='115-top_a'))[0]
            self.assertLessEqual(self.max_error(actual[i],prefixes[count][i]),3,(i,count))

    def reveal_components(self, text, *, style=None, has_space=False, without_pillow=False):
        title=self.title(text,**(style or {}));title['style'].pop('x',None)
        full,_=self.render(title)
        blank,_=self.render(self.title(''))
        mask=ImageChops.difference(full[-1],blank[-1])
        points={(x,y) for y in range(75,H) for x in range(W) if max(mask.getpixel((x,y)))>8}
        boxes=[]
        while points:
            seed=points.pop();stack=[seed];cluster=[seed]
            while stack:
                x,y=stack.pop()
                for neighbor in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if neighbor in points:points.remove(neighbor);stack.append(neighbor);cluster.append(neighbor)
            if len(cluster)>10:
                xs,ys=zip(*cluster);boxes.append((min(xs)-2,min(ys)-2,max(xs)+3,max(ys)+3))
        boxes.sort(key=lambda box:(box[1],box[0]));self.assertEqual(len(boxes),text.count('H'))
        delay,duration=.08,.75
        title['animation']={'type':'typewriter','delay':delay,'duration':duration}
        if without_pillow:
            with patch('ai_ad_editor.render._load_subtitle_font_metrics',return_value=None):actual,result=self.render(title)
        else:actual,result=self.render(title)
        steps=len(text.replace('\n',''))
        for frame in range(FPS):
            count=sum(frame/FPS>=round(delay+j*duration/steps,9) for j in range(steps))
            glyphs=min(count,4)+max(0,count-5) if has_space else count
            expected=blank[frame].copy()
            for box in boxes[:glyphs]:expected.paste(full[frame].crop(box),box[:2])
            self.assertLessEqual(self.max_error(actual[frame],expected),3,(frame,count,glyphs))
        return result

    def test_centered_typewriter_keeps_the_complete_paragraph_anchor(self):
        self.reveal_components('HHHH')

    def test_multiline_typewriter_preserves_real_line_baselines(self):
        self.reveal_components('HHHH\nHHHH',style={'y':'85','line_spacing':12})

    def test_soft_wrap_preserves_authored_space_timing(self):
        self.reveal_components('HHHH HHHH',style={'y':'85','line_spacing':12,'max_width':95},has_space=True)

    def test_typing_plate_is_one_complete_paragraph_plate(self):
        title=self.title('HHHH',box=True,boxcolor='0x2040ff@0.5',box_padding=8)
        plate=copy.deepcopy(title);plate['style']['fontcolor']='white@0'
        expected,_=self.render(plate)
        blank,_=self.render(self.title(''))
        title['animation']={'type':'typewriter','delay':.1,'duration':.8}
        actual,result=self.render(title)
        self.assertLessEqual(self.max_error(actual[0],blank[0]),3)
        # The area to the right of the first glyph must already contain the
        # complete plate, before later glyphs are typed.
        region=(60,103,95,109)
        self.assertGreater(self.max_error(expected[3].crop(region),blank[3].crop(region)),10)
        self.assertLessEqual(self.max_error(actual[3].crop(region),expected[3].crop(region)),3)
        self.assertEqual(self.metadata(result)['text_layout']['typing']['native_target_count'],1)

    def test_literal_command_delimiters_and_combining_graphemes(self):
        text="AV e\u0301,';\\Q% 2";delay=.05;duration=.7
        title=self.title(text,y='115-top_a');title['animation']={'type':'typing','delay':delay,'duration':duration}
        actual,result=self.render(title)
        # Authored graphemes are enumerated explicitly, independent of the
        # product segmenter and the command-token encoder.
        units=['A','V',' ','e\u0301',',',"'",';','\\','Q','%',' ','2']
        for frame in (0,2,5,8,12,18,23):
            count=sum(frame/FPS>=round(delay+j*duration/len(units),9) for j in range(len(units)))
            # Empty LF removes the subtitle raster altogether. Use the empty
            # text paint for the zero-prefix control to retain its conversions.
            control=self.title(''.join(units[:count])+'\n' if count else '',y='115-top_a')
            expected,_=self.render(control)
            self.assertLessEqual(self.max_error(actual[frame],expected[frame]),3,(frame,count))
        self.assertEqual(self.metadata(result)['text_layout']['typing']['grapheme_count'],len(units))

    def test_native_typing_keeps_layout_without_pillow_metrics(self):
        self.reveal_components('HHHH\nHHHH',style={'y':'85','line_spacing':12},without_pillow=True)

    def test_typewriter_planning_rejects_unimplemented_or_unsafe_semantics(self):
        cases=[(self.title('H'*513),'SUBTITLE_TYPEWRITER_BUDGET'),
               (self.title('HI',x='rand(0,10)'),'SUBTITLE_TYPEWRITER_POSITION_UNSUPPORTED'),
               (self.title('\u05e9\u05dc\u05d5\u05dd'),'SUBTITLE_TYPEWRITER_BIDI_UNSUPPORTED'),
               (self.title('HI\rTHERE'),'SUBTITLE_TYPEWRITER_CONTROL_UNSUPPORTED'),
               (self.title('HI',boxw=2),'SUBTITLE_TYPEWRITER_BOX_CLIP_UNSUPPORTED')]
        for title,code in cases:
            title['animation']={'type':'typewriter','duration':.7}
            with self.subTest(code=code):self.reject(title,code)

    def test_dynamic_inline_typewriter_keeps_an_explicit_limitation(self):
        title=self.title('HI');title['animation']={'type':'typewriter','duration':.5}
        self.prepare(title,independent=False,dynamic=True)
        result=self.call('render','--project',self.root,'--output',self.output)
        self.assertIn('subtitle_typewriter_dynamic_raster',[value.get('feature') for value in result['data']['warnings']])
