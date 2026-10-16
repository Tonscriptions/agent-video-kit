from __future__ import annotations

import bisect
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import unittest

from PIL import Image, ImageFont

import test_nested_time_mapping as fixture
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.project import ledger_file


TPS, FPS, WIDTH, HEIGHT = 90000, 24, 96, 64


def oracle_step(left=0., right=3.5, *, rates=(.6, 3.), mode='linear', reverse=False, start=0., handles=(.15, .05, .85, .7)):
    """Independent parametric trapezoidal quadrature, not product segments."""
    span = right-left
    xs, clocks = [], []
    previous = 0.
    total = 0.
    count = 16384
    for index in range(count+1):
        u = index/count
        if mode == 'bezier':
            x1,y1,x2,y2 = handles
            x = 3*(1-u)**2*u*x1+3*(1-u)*u*u*x2+u**3
            y = 3*(1-u)**2*u*y1+3*(1-u)*u*u*y2+u**3
            dx = 3*((1-u)**2*x1+2*(1-u)*u*(x2-x1)+u*u*(1-x2))
        else:
            x,dx = u,1.
            y = u*u if mode=='ease_in' else 1-(1-u)**2 if mode=='ease_out' else u
        integrand = span*dx/(rates[0]+(rates[1]-rates[0])*y)
        if index: total += (previous+integrand)/(2*count)
        xs.append(left+span*x);clocks.append(total);previous=integrand
    duration = round(total*TPS)/TPS
    return {'left':left,'right':right,'rates':rates,'mode':mode,'reverse':reverse,'start':start,
            'handles':handles,'xs':xs,'clocks':clocks,'duration':duration,'total':total}


def unmap(step, at):
    fraction = (at-step['start'])/step['duration']
    if step['reverse']: fraction = 1-fraction
    target = max(0.,min(1.,fraction))*step['total']
    i=max(1,min(len(step['clocks'])-1,bisect.bisect_left(step['clocks'],target)))
    a,b=step['clocks'][i-1:i+1]
    return step['xs'][i-1]+(step['xs'][i]-step['xs'][i-1])*(target-a)/max(1e-20,b-a)


class SubtitleClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NestedTimeMappingTests.setUpClass.__func__(cls)
        cls.font_file=cls.fixture_root/'aileron.ttf'
        # Pillow's bundled open Aileron is used only in private test fixtures.
        # Public examples supply a separately licensed local font explicitly.
        cls.font_file.write_bytes(ImageFont.load_default(size=16).path.getvalue())
        cls.font=ImageFont.truetype(str(cls.font_file),16)

    @classmethod
    def tearDownClass(cls):
        fixture.NestedTimeMappingTests.tearDownClass.__func__(cls)

    def setUp(self):
        fixture.NestedTimeMappingTests.setUp(self)
        self.case_number=0
        self.call('media','ingest','--project',self.root,'--input',self.font_file,'--asset-id','local_font')

    call=fixture.NestedTimeMappingTests.call

    def style(self, **values):
        return {'font_asset_id':'local_font','fontsize':16,'x':'10','y':'34','box':False,**values}

    def prepare_next(self):
        self.case_number+=1
        if self.case_number==1:return
        self.root=self.base/f'case_{self.case_number}'
        self.call('project','init',self.root)
        data=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        data['settings']['canvas'].update(width=WIDTH,height=HEIGHT)
        data['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        atomic_write_json(self.root/'project.json',data)
        self.call('media','ingest','--project',self.root,'--input',self.source,'--asset-id','frames')
        self.call('media','ingest','--project',self.root,'--input',self.font_file,'--asset-id','local_font')

    def case(self, parents=None, *, independent=False, animation=None, file_kind=None, time_base='sequence',
             transitions=None, leaf_reverse=False, text='AA BB', style=None, render=True):
        self.prepare_next()
        steps=[]
        source_duration=3.5
        for config in parents or [{}]:
            step=oracle_step(right=config.get('right',source_duration),**{k:v for k,v in config.items() if k!='right'})
            steps.append(step);source_duration=step['start']+step['duration']
        subtitle={'text':text,'style':style or self.style(active_color='yellow'),
                  'word_timing':[{'text':'AA','start':0.,'end':1.5},{'text':'BB','start':1.5,'end':3.}]} if animation is None and text=='AA BB' else {'text':text,'style':style or self.style()}
        if animation is not None:subtitle['animation']=animation
        operations=[{'op':'add_sequence','id':'child_0','duration_tick':round(3.5*TPS)}]
        leaf={'op':'append_clip','sequence_id':'child_0','track_id':'child_0_video_1','id':'leaf','asset_id':'frames',
              'timeline_start_tick':round(.25*TPS),'source_in_tick':0,'source_out_tick':3*TPS,
              'duration_tick':3*TPS,'reverse':leaf_reverse}
        if file_kind:
            offset=.25 if time_base=='sequence' else 0.
            self.cue_ranges=[(.2+offset,.8+offset),(1.6+offset,2.4+offset)]
            path=self.base/f'cues_{self.case_number}.{file_kind}'
            if file_kind=='srt':
                def clock(x):
                    ms=round(x*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
                path.write_text('\n\n'.join(f'{i+1}\n{clock(a)} --> {clock(b)}\nHHH' for i,(a,b) in enumerate(self.cue_ranges))+'\n',encoding='utf-8')
            else:
                def clock(x):return f'0:00:{x:05.2f}'
                header='[Script Info]\nScriptType: v4.00+\nPlayResX: 96\nPlayResY: 64\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Aileron,16,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,0,0,12,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
                path.write_text(header+''.join(f'Dialogue: 0,{clock(a)},{clock(b)},Default,,0,0,0,,HHH\n' for a,b in self.cue_ranges),encoding='utf-8')
            ingested=self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','cues')
            self.cue_uri=ingested['data']['asset']['uri']
            subtitle={'asset_uri':self.cue_uri,'asset_time_base':time_base,
                      'style':{'font_asset_id':'local_font','fontsize':54 if file_kind=='srt' else 16}}
        if independent:
            operations.extend([leaf,{'op':'add_track','sequence_id':'child_0','track_id':'titles','kind':'subtitle','order':2}])
            title={**leaf,'track_id':'titles','id':'title','generator':{'type':'text'},'subtitle':subtitle}
            title.pop('asset_id');title.pop('reverse',None)
            if transitions:title.update(transitions)
            operations.append(title)
        else:
            operations.append({**leaf,'subtitle':subtitle})
        current='child_0'
        for i,step in enumerate(steps):
            target='seq_main' if i==len(steps)-1 else f'child_{i+1}'
            if target!='seq_main':operations.append({'op':'add_sequence','id':target,'duration_tick':round((step['start']+step['duration'])*TPS)})
            keyframes=[{'at_tick':0,'speed':step['rates'][0],'interpolation':step['mode']},
                       {'at_tick':round((step['right']-step['left'])*TPS),'speed':step['rates'][1]}]
            if step['mode']=='bezier':keyframes[0]['control_points']=list(step['handles'])
            operations.append({'op':'append_sequence_clip','sequence_id':target,'track_id':'track_video_1' if target=='seq_main' else target+'_video_1',
                               'nested_sequence_id':current,'id':f'parent_{i}','source_in_tick':round(step['left']*TPS),
                               'source_out_tick':round(step['right']*TPS),'timeline_start_tick':round(step['start']*TPS),
                               'duration_tick':round(step['duration']*TPS),'speed_curve':{'keyframes':keyframes},'reverse':step['reverse']})
            current=target
        changes=self.base/f'changes_{self.case_number}.json'
        changes.write_text(json.dumps({'operations':operations}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',changes)
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        project['sequences'][0]['duration_tick']=round(source_duration*TPS)
        atomic_write_json(self.root/'project.json',project)
        self.steps=steps;self.output=self.root/'renders/captions.mp4'
        self.plan=self.call('render','--project',self.root,'--output',self.output,'--dry-run')['data']['plan']
        if not render:return []
        canonical=lambda p:json.dumps({k:p[k] for k in ['assets','settings','sequences']},sort_keys=True)
        before=canonical(project);ledger=ledger_file(self.root).read_bytes()
        self.call('render','--project',self.root,'--output',self.output)
        after=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(before,canonical(after))
        self.assertEqual(ledger,ledger_file(self.root).read_bytes())
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(self.output),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
        frame_bytes=WIDTH*HEIGHT*3
        self.assertEqual(len(raw)%frame_bytes,0)
        frames=[Image.frombytes('RGB',(WIDTH,HEIGHT),raw[i:i+frame_bytes]) for i in range(0,len(raw),frame_bytes)]
        self.assertGreater(len(frames),8)
        return frames

    def author_time(self, i):
        at=i/FPS
        for step in reversed(self.steps):at=unmap(step,at)
        if sum(s['reverse'] for s in self.steps)%2:at-=.5/TPS
        return at

    def visible(self, i):
        at=i/FPS
        for step in reversed(self.steps):
            if not step['start']<=at<step['start']+step['duration']:return False
            at=unmap(step,at)
        return .25<=self.author_time(i)<3.25

    def check_words(self, frames):
        split=10+self.font.getlength('AA ')
        rows=[]
        for i,image in enumerate(frames):
            counts=[0,0]
            for y in range(26,HEIGHT):
                for x in range(WIDTH):
                    r,g,b=image.getpixel((x,y))
                    if r>150 and g>130 and b<100:counts[x>=split]+=1
            local=self.author_time(i)-.25
            active=self.visible(i) and .0<=local<3.
            expected=(0 if local<1.5 else 1) if active else None
            observed=0 if counts[0]>6 else 1 if counts[1]>6 else None
            self.assertFalse(counts[0]>6 and counts[1]>6,(i,counts))
            rows.append((i,local,expected,observed,counts))
        mismatches=[r for r in rows if r[2]!=r[3]]
        self.assertFalse(mismatches,mismatches[:12])

    def check_cues(self, frames, time_base):
        errors=[]
        for i,image in enumerate(frames):
            at=self.author_time(i)
            cue=at-.25 if time_base=='clip' else at
            expected=self.visible(i) and any(a<=cue<b for a,b in self.cue_ranges)
            count=sum(r>160 and g>160 and b>160 for r,g,b in image.crop((0,23,WIDTH,HEIGHT)).getdata())
            if (count>4)!=expected:errors.append((i,at,expected,count))
        self.assertFalse(errors,errors[:12])

    def test_subtitle_clock_inline_linear_word_highlights(self):
        self.check_words(self.case())

    def test_subtitle_clock_inline_eased_word_highlights(self):
        self.check_words(self.case([{'mode':'ease_in'}]))

    def test_subtitle_clock_reverse_half_open_word_boundary(self):
        self.check_words(self.case([{'rates':(1.,1.),'reverse':True}]))

    def test_subtitle_clock_leaf_reverse_keeps_presentation_word_timing(self):
        self.check_words(self.case([{'mode':'ease_out','reverse':True}],leaf_reverse=True))

    def test_subtitle_clock_two_nonlinear_ancestors_and_double_reverse(self):
        self.check_words(self.case([{'mode':'bezier','reverse':True},{'rates':(.8,2.),'mode':'ease_out','reverse':True}]))

    def test_subtitle_clock_nonzero_trim_and_output_start_preserve_phase(self):
        self.check_words(self.case([{'left':.8,'right':2.7,'start':.23,'mode':'ease_in','reverse':True}]))

    def test_subtitle_clock_independent_words_and_final_visibility_window(self):
        for config in [{'mode':'ease_in'},{'rates':(1.,1.),'reverse':True}]:
            with self.subTest(config=config):self.check_words(self.case([config],independent=True))

    def test_subtitle_clock_typewriter_prefix_matches_original_time(self):
        for independent in [False,True]:
            frames=self.case([{'mode':'ease_in','reverse':True}],independent=independent,text='HHHH',
                             animation={'type':'typewriter','delay':.1,'duration':2.4})
            advance=self.font.getlength('H')
            errors=[]
            for i,image in enumerate(frames):
                local=self.author_time(i)-.25
                expected=sum(local>=.1+j*.6 for j in range(4)) if 0<=local<3 else 0
                observed=0
                for j in range(4):
                    region=image.crop((round(10+j*advance),29,round(10+(j+1)*advance),HEIGHT))
                    if sum(r>165 and g>165 and b>165 for r,g,b in region.getdata())>4:observed+=1
                if expected!=observed:errors.append((i,local,expected,observed))
            self.assertFalse(errors,errors[:12])

    def text_luma(self, image):
        return sum(.2126*r+.7152*g+.0722*b for r,g,b in image.crop((4,25,WIDTH,HEIGHT)).getdata())-self.luma_base

    def opaque_reference(self, independent):
        blank=self.case([{'rates':(1.,1.)}],independent=independent,text='')
        self.luma_base=0.
        self.luma_base=self.text_luma(blank[24])
        control=self.case([{'rates':(1.,1.)}],independent=independent,text='HHHH')
        return self.text_luma(control[24])

    def test_subtitle_clock_fade_animation_uses_authored_duration(self):
        for kind,independent in [('fade_in',False),('fade_out',True)]:
            reference=self.opaque_reference(independent)
            frames=self.case([{'mode':'ease_in','reverse':True}],independent=independent,text='HHHH',
                             animation={'type':kind,'duration':1.8})
            errors=[]
            for i,image in enumerate(frames):
                local=self.author_time(i)-.25
                if not .03<local<2.97:continue
                expected=max(0.,min(1.,local/1.8 if kind=='fade_in' else (3-local)/1.8))
                observed=self.text_luma(image)/reference
                if abs(expected-observed)>.065:errors.append((i,expected,observed))
            self.assertFalse(errors,errors[:12])

    def test_subtitle_clock_independent_rotation_pose(self):
        frames=self.case([{'mode':'ease_in','reverse':True}],independent=True,text='HHHH',
                         animation={'type':'rotate','duration':2.8,'from_degrees':-25,'to_degrees':25})
        tested=0;errors=[]
        for i,image in enumerate(frames):
            local=self.author_time(i)-.25
            if not 2.<local<2.95:continue
            # Coverage-weighted moments retain antialiased glyphs during
            # fade-in; a high binary threshold leaves a sparse biased skeleton.
            points=[(x,y,max(0,image.getpixel((x,y))[0]-60)) for y in range(21,HEIGHT) for x in range(WIDTH) if image.getpixel((x,y))[0]>80]
            if len(points)<12:continue
            mass=sum(w for x,y,w in points)
            mx=sum(x*w for x,y,w in points)/mass;my=sum(y*w for x,y,w in points)/mass
            xx=sum((x-mx)**2*w for x,y,w in points);yy=sum((y-my)**2*w for x,y,w in points);xy=sum((x-mx)*(y-my)*w for x,y,w in points)
            angle=math.degrees(.5*math.atan2(2*xy,xx-yy));expected=-25+50*min(1.,local/2.8)
            tested+=1
            if abs(angle-expected)>2.5:errors.append((i,expected,angle))
        self.assertGreaterEqual(tested,5);self.assertFalse(errors,errors[:12])

    def test_subtitle_clock_independent_fade_transition(self):
        reference=self.opaque_reference(True)
        frames=self.case([{'mode':'ease_in','reverse':True}],independent=True,text='HHHH',
                         transitions={'transition_in':{'type':'fade','duration':1.8}})
        errors=[]
        for i,image in enumerate(frames):
            local=self.author_time(i)-.25
            if not .03<local<2.97:continue
            expected=max(0.,min(1.,local/1.8))
            observed=self.text_luma(image)/reference
            if abs(expected-observed)>.065:errors.append((i,expected,observed))
        self.assertFalse(errors,errors[:12])

    def test_subtitle_clock_srt_clip_relative_under_eased_reverse(self):
        self.check_cues(self.case([{'mode':'ease_in','reverse':True}],independent=True,file_kind='srt',time_base='clip'),'clip')

    def test_subtitle_clock_ass_sequence_time_and_video_frame_roundtrip(self):
        frames=self.case([{'mode':'ease_in','reverse':True}],file_kind='ass')
        self.check_cues(frames,'sequence')
        errors=[]
        for i,image in enumerate(frames):
            local=self.author_time(i)-.25
            if not .04<local<2.96:continue
            observed=sum(1<<b for b in range(7) if image.getpixel((b*12+4,10))[0]>128)
            if abs(observed-math.floor(local*FPS))>1:errors.append((i,local,observed))
        self.assertFalse(errors,errors[:12])

    def test_subtitle_clock_asset_style_options_resolve_registered_cues(self):
        self.case([{'rates':(1.,1.)}],independent=True,file_kind='ass',render=False)
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        title=next(c for s in project['sequences'] for t in s['tracks'] for c in t['clips'] if c['id']=='title')
        title.pop('generator');title['asset_id']='cues';title['subtitle'].pop('asset_uri')
        atomic_write_json(self.root/'project.json',project)
        result=self.call('render','--project',self.root,'--output',self.output)
        self.assertTrue(self.output.is_file());self.assertTrue(result['ok'])

    def test_subtitle_clock_invalid_asset_time_base_rejected_atomically(self):
        self.case(render=False)
        for value in ['remote',None,True,[],{}]:
            change=self.base/'bad_time_base.json'
            change.write_text(json.dumps({'operations':[{'op':'update_clip','sequence_id':'child_0','clip_id':'leaf',
                'patch':{'subtitle':{'text':'HH','asset_time_base':value,'style':self.style()}}}]}),encoding='utf-8')
            before=(self.root/'project.json').read_bytes();ledger=ledger_file(self.root).read_bytes()
            import contextlib,io
            from ai_ad_editor.cli import main
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):code=main(['timeline','compose','--project',str(self.root),'--input',str(change)])
            self.assertEqual(code,2,stream.getvalue());self.assertIn('SUBTITLE_ASSET_TIME_BASE_INVALID',stream.getvalue())
            self.assertEqual(before,(self.root/'project.json').read_bytes())
            self.assertEqual(ledger,ledger_file(self.root).read_bytes())

    def test_subtitle_clock_literal_text_and_custom_position_clock(self):
        frames=self.case([{'mode':'ease_in','reverse':True}],text='t t',style=self.style(x='10+12*t'))
        errors=[]
        for i,image in enumerate(frames):
            at=self.author_time(i)
            if not .3<at<3.2:continue
            xs=[x for y in range(28,HEIGHT) for x in range(WIDTH) if min(image.getpixel((x,y)))>180]
            if not xs:errors.append((i,'missing literal t'));continue
            expected=10+12*at
            if abs(min(xs)-expected)>2:errors.append((i,expected,min(xs)))
        self.assertFalse(errors,errors[:12])

    def test_subtitle_clock_dynamic_inline_alpha_remains_explicitly_degraded(self):
        self.case(animation={'type':'fade_in','duration':1.8},text='HHHH',render=False)
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        leaf=next(c for seq in project['sequences'] for t in seq['tracks'] for c in t['clips'] if c['id']=='leaf')
        leaf['keyframes']=[{'property':'transform.scale','keyframes':[{'at_tick':0,'value':.8,'interpolation':'linear'},{'at_tick':3*TPS,'value':1.,'interpolation':'linear'}]}]
        # An isolated group now supplies a fixed raster. Retain this legacy
        # warning regression on the direct, changing-dimension clip path.
        root=next(s for s in project['sequences'] if s['id']=='seq_main')
        root['tracks'][0]['clips']=[copy.deepcopy(leaf)]
        root['duration_tick']=int(leaf['timeline_start_tick'])+int(leaf['duration_tick'])
        project['sequences']=[root]
        atomic_write_json(self.root/'project.json',project)
        result=self.call('render','--project',self.root,'--output',self.output)
        self.assertTrue(any(w.get('feature')=='subtitle_inline_dynamic_alpha' for w in result['warnings']))
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(self.output),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
        self.assertGreater(len(raw),WIDTH*HEIGHT*3*8)
        self.assertGreater(sum(raw[i]>150 and raw[i+1]>150 and raw[i+2]>150 for i in range(0,len(raw),3)),100)

    def test_subtitle_clock_manifest_and_unaccepted_freeze_boundary(self):
        self.case([{'mode':'ease_in'}],render=False)
        records=[v['subtitle_time_mapping'] for v in self.plan['inputs'] if v.get('subtitle_time_mapping')]
        self.assertEqual(len(records),1);self.assertTrue(records[0]['maps'])
        self.assertFalse(records[0]['freeze_semantics_approximate'])
        self.assertFalse(any(w.get('feature')=='nested_sequence_caption_cues' for w in self.plan['warnings']))
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        parent=project['sequences'][0]['tracks'][0]['clips'][0]
        parent['freeze']={'at_tick':9000,'duration_tick':9000,'audio_mode':'silence'};parent['duration_tick']+=9000
        project['sequences'][0]['duration_tick']+=9000
        atomic_write_json(self.root/'project.json',project)
        plan=self.call('render','--project',self.root,'--output',self.output,'--dry-run')['data']['plan']
        self.assertTrue(any(w.get('feature')=='subtitle_freeze_clock' for w in plan['warnings']))
