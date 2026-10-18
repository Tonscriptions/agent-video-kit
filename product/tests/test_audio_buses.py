"""Actual 48-kHz float samples for hierarchy, scope and post-mix processing."""
from __future__ import annotations
import array,contextlib,copy,hashlib,io,json,math,subprocess,tempfile,unittest,wave
from pathlib import Path
from PIL import Image
from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json

TPS,SR,DURATION=90000,48000,2

class AudioBusFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.fixture=tempfile.TemporaryDirectory(prefix='audio-bus-source-');cls.sources=Path(cls.fixture.name)
        Image.new('RGB',(128,80),(50,80,110)).save(cls.sources/'picture.png')
        cls.pcm={}
        for name in ('tone','other','negative','stereo','impulse','dc'):
            values=array.array('h')
            for n in range(SR*DURATION):
                left=round(11000*math.sin(2*math.pi*400*n/SR))
                right=round(7500*math.sin(2*math.pi*800*n/SR)) if name=='stereo' else left
                if name=='other':left=right=round(4500*math.sin(2*math.pi*1200*n/SR))
                if name=='negative':left=right=-left
                if name=='impulse':left=right=12000 if n==SR//4 else 0
                if name=='dc':left=right=10000
                values.extend((left,right))
            with wave.open(str(cls.sources/f'{name}.wav'),'wb') as h:
                h.setparams((2,2,SR,0,'NONE','not compressed'));h.writeframes(values.tobytes())
            cls.pcm[name]=[v/32768 for v in values]

    @classmethod
    def tearDownClass(cls):cls.fixture.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='audio-bus-project-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'project';self.call('project','init',self.root)
        p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        p['settings']['canvas'].update(width=128,height=80)
        p['settings']['output']={'container':'mkv','video':{'codec':'libx264','crf':0,'pixel_format':'yuv444p','preset':'ultrafast'},
                                  'audio':{'codec':'pcm_f32le','bitrate':'192k'}}
        atomic_write_json(self.root/'project.json',p)
        self.call('media','ingest','--project',self.root,'--input',self.sources/'picture.png','--asset-id','picture')
        self.ops=[{'op':'update_track','track_id':'track_video_1','patch':{'overlap_policy':'allow'}},
                  {'op':'append_clip','track_id':'track_video_1','id':'background','asset_id':'picture',
                   'source_in_tick':0,'source_out_tick':DURATION*TPS,'duration_tick':DURATION*TPS}]
        self.ingested=set();self.render_number=0

    def call(self,*args,expected=0):
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):code=main(list(map(str,args)))
        value=json.loads(capture.getvalue());self.assertEqual(code,expected,value);return value

    def sequence(self,name):self.ops.append({'op':'add_sequence','id':name,'duration_tick':DURATION*TPS})

    def track(self,seq,name,**audio):self.ops.append({'op':'add_track','sequence_id':seq,'id':name,'kind':'audio','order':1,'audio':audio})

    def tone(self,seq='seq_main',track='track_audio_1',name='tone',**extra):
        if name not in self.ingested:
            self.call('media','ingest','--project',self.root,'--input',self.sources/f'{name}.wav','--asset-id','asset_'+name)
            self.ingested.add(name)
        self.ops.append({'op':'append_clip','sequence_id':seq,'track_id':track,'id':f'{track}_{len(self.ops)}',
                         'asset_id':'asset_'+name,'source_in_tick':0,'source_out_tick':DURATION*TPS,'duration_tick':DURATION*TPS,'timeline_start_tick':0,**extra})

    def group(self,child,**extra):
        target=extra.pop('target','seq_main');track=extra.pop('track','track_video_1' if target=='seq_main' else target+'_video_1')
        self.ops.append({'op':'append_sequence_clip','sequence_id':target,'track_id':track,'id':f'group_{len(self.ops)}',
                         'nested_sequence_id':child,'source_in_tick':0,'source_out_tick':DURATION*TPS,
                         'duration_tick':DURATION*TPS,'timeline_start_tick':0,**extra})

    def compose(self,expected=0):
        changes=self.base/'changes.json';atomic_write_json(changes,{'operations':self.ops})
        return self.call('timeline','compose','--project',self.root,'--input',changes,expected=expected)

    def render(self,*,duration_tick=DURATION*TPS):
        self.compose()
        p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=duration_tick
        atomic_write_json(self.root/'project.json',p)
        def authored():
            p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
            return json.dumps({k:p[k] for k in ('settings','assets','sequences')},sort_keys=True),hashlib.sha256((self.root/'rights-ledger.json').read_bytes()).hexdigest()
        before=authored();self.render_number+=1;path=self.root/f'renders/audio{self.render_number}.mkv'
        result=self.call('render','--project',self.root,'--output',path);self.assertEqual(before,authored())
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-f','f32le','-c:a','pcm_f32le','pipe:1'],capture_output=True,check=True).stdout
        values=array.array('f');values.frombytes(raw);self.assertEqual(len(values),round(duration_tick/TPS*SR)*2)
        manifest=json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8-sig'))
        return list(values),result,manifest,path

    def close_pcm(self,actual,expected,tolerance=2e-6):
        self.assertEqual(len(actual),len(expected));self.assertLessEqual(max(map(abs,(a-b for a,b in zip(actual,expected))),default=0),tolerance)

    def reference_filter(self,values,filter_text):
        raw=array.array('f',values).tobytes()
        result=subprocess.run(['ffmpeg','-v','error','-f','f32le','-ar',str(SR),'-ac','2','-i','pipe:0','-af',filter_text,
                               '-f','f32le','-c:a','pcm_f32le','pipe:1'],input=raw,capture_output=True,check=True)
        out=array.array('f');out.frombytes(result.stdout);return list(out)

class AudioBusTests(AudioBusFixture):
    def test_root_tracks_sum_without_input_count_attenuation(self):
        self.tone();self.track('seq_main','other');self.tone(track='other',name='other')
        actual,_,_,_=self.render();self.close_pcm(actual,[a+b for a,b in zip(self.pcm['tone'],self.pcm['other'])])

    def test_silent_third_input_does_not_change_audible_gain(self):
        self.tone();self.track('seq_main','silent');self.tone(track='silent',audio={'volume':0})
        actual,_,_,_=self.render();self.close_pcm(actual,self.pcm['tone'])

    def test_container_gain_and_track_gain_follow_child_sum(self):
        self.sequence('child');self.tone('child','child_audio_1');self.track('child','other',volume=.5);self.tone('child','other','other')
        self.group('child',audio={'volume':.5})
        self.ops.append({'op':'update_track','track_id':'track_video_1','patch':{'audio':{'volume':.5}}})
        actual,_,manifest,_=self.render();self.close_pcm(actual,[(a+.5*b)*.25 for a,b in zip(self.pcm['tone'],self.pcm['other'])])
        buses=[v for v in manifest['inputs'] if v.get('kind')=='sequence-audio-bus'];self.assertEqual(len(buses),1)
        self.assertEqual(buses[0]['sample_rate'],SR);self.assertEqual(buses[0]['intermediate_files'],0)
        root=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-audio-root')
        self.assertEqual(root['output_samples'],2*SR);self.assertFalse(root['automatic_limiter'])

    def test_deep_container_gain_is_applied_once_per_level(self):
        self.sequence('child');self.tone('child','child_audio_1');self.sequence('middle')
        self.group('child',target='middle',audio={'volume':.5});self.group('middle',audio={'volume':.5})
        actual,_,_,_=self.render();self.close_pcm(actual,[v*.25 for v in self.pcm['tone']])

    def test_parent_volume_automation_keeps_phase_across_children(self):
        self.sequence('child');self.tone('child','child_audio_1',source_out_tick=TPS,duration_tick=TPS)
        self.tone('child','child_audio_1',source_in_tick=TPS,timeline_start_tick=TPS,duration_tick=TPS)
        self.group('child',audio={'volume':0},keyframes=[{'property':'audio.volume','keyframes':[
            {'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':2*TPS,'value':1,'interpolation':'linear'}]}])
        actual,_,_,_=self.render();self.close_pcm(actual,[v*(n//2/SR/2) for n,v in enumerate(self.pcm['tone'])])

    def test_parent_balance_preserves_independent_stereo_channels(self):
        self.sequence('child');self.tone('child','child_audio_1','stereo');self.group('child',audio={'pan':.5})
        actual,_,_,_=self.render();self.close_pcm(actual,[v*(.5 if n%2==0 else 1) for n,v in enumerate(self.pcm['stereo'])])

    def test_muted_container_keeps_video_and_silences_descendants(self):
        self.sequence('child');self.tone('child','child_audio_1');self.group('child',audio={'muted':True})
        actual,_,_,path=self.render();self.assertEqual(max(map(abs,actual)),0)
        frame=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
        self.assertGreater(sum(frame)/len(frame),50)

    def test_muted_video_track_audio_keeps_picture(self):
        self.sequence('child');self.tone('child','child_audio_1');self.group('child')
        self.ops.append({'op':'update_track','track_id':'track_video_1','patch':{'audio':{'mute':True}}})
        actual,_,_,_=self.render();self.assertEqual(max(map(abs,actual)),0)

    def test_muted_leaf_does_not_reappear_in_mix(self):
        self.tone(audio={'mute':True});actual,_,_,_=self.render();self.assertEqual(max(map(abs,actual)),0)

    def test_nested_solo_does_not_silence_root_sibling(self):
        self.sequence('child');self.track('child','selected',solo=True);self.tone('child','selected')
        self.tone('child','child_audio_1','other');self.group('child');self.tone(name='other')
        actual,_,_,_=self.render();self.close_pcm(actual,[a+b for a,b in zip(self.pcm['tone'],self.pcm['other'])])

    def test_compressor_processes_sum_once(self):
        self.sequence('child');self.tone('child','child_audio_1');self.track('child','cancel');self.tone('child','cancel','negative',audio={'volume':.5})
        self.group('child',audio={'compressor':{'threshold':.1,'ratio':4,'attack':1,'release':50}})
        actual,_,_,_=self.render();reference=self.reference_filter([v*.5 for v in self.pcm['tone']],
             'acompressor=threshold=0.1:ratio=4:attack=1:release=50')
        self.close_pcm(actual,reference)

    def test_track_compressor_processes_overlapping_clips_after_sum(self):
        self.ops.append({'op':'update_track','track_id':'track_audio_1','patch':{'overlap_policy':'allow','audio':{'compressor':{'threshold':.1,'ratio':4,'attack':1,'release':50}}}})
        self.tone();self.tone(name='negative',audio={'volume':.5})
        actual,_,_,_=self.render();self.close_pcm(actual,self.reference_filter([v*.5 for v in self.pcm['tone']],
             'acompressor=threshold=0.1:ratio=4:attack=1:release=50'))

    def test_container_fades_apply_to_summed_samples(self):
        self.sequence('child');self.tone('child','child_audio_1');self.group('child',audio={'fade_in':.5,'fade_out':.5})
        actual,_,_,_=self.render();self.close_pcm(actual,[v*min(1,n//2/SR/.5)*min(1,(2-n//2/SR)/.5) for n,v in enumerate(self.pcm['tone'])])

    def test_submillisecond_start_uses_sample_grid(self):
        self.tone(name='impulse',timeline_start_tick=1,source_out_tick=TPS,duration_tick=TPS)
        actual,_,manifest,_=self.render();expected=[0.]*len(actual);count=SR
        expected[2:2+count*2]=self.pcm['impulse'][:count*2]
        self.close_pcm(actual,expected);node=next(n for n in manifest['inputs'] if n.get('kind')=='audio')
        self.assertEqual(node['timeline_start_sample'],1)

    def test_reverb_tail_is_clipped_to_container_window(self):
        self.sequence('child');self.tone('child','child_audio_1','impulse')
        self.group('child',source_out_tick=TPS//2,duration_tick=TPS//2,
                   audio={'reverb':{'in_gain':.8,'out_gain':.9,'delays':'400','decays':'0.5'}})
        actual,_,_,_=self.render();self.assertGreater(max(map(abs,actual[:SR])),.1);self.assertEqual(max(map(abs,actual[SR:])),0)

    def test_multiple_ducking_inputs_use_independent_detector_outputs(self):
        for n,role in enumerate(('voice','voice','music','music')):
            name=f't{n}';self.track('seq_main',name,role=role,duck_under_voice=role=='music');self.tone(track=name,audio={'volume':.3})
        actual,result,_,_=self.render();self.assertGreater(max(map(abs,actual)),.05)
        warning=next(w for w in result['warnings'] if w.get('code')=='AUDIO_DUCKING_APPLIED')
        self.assertEqual((warning['voice_inputs'],warning['ducked_inputs']),(2,2))

    def test_reverse_container_does_not_reverse_its_own_automation(self):
        self.sequence('child');self.tone('child','child_audio_1');self.group('child',reverse=True,keyframes=[{'property':'audio.volume','keyframes':[
            {'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':2*TPS,'value':1,'interpolation':'linear'}]}])
        actual,_,_,_=self.render();frames=list(zip(self.pcm['tone'][::2],self.pcm['tone'][1::2]))[::-1]
        expected=[v*n/SR/2 for n,frame in enumerate(frames) for v in frame];self.close_pcm(actual,expected)

    def test_outer_reverse_reverses_inner_authored_gain(self):
        self.sequence('child');self.tone('child','child_audio_1');self.sequence('middle')
        self.group('child',target='middle',keyframes=[{'property':'audio.volume','keyframes':[
            {'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':2*TPS,'value':1,'interpolation':'linear'}]}])
        self.group('middle',reverse=True)
        actual,_,_,_=self.render();frames=list(zip(self.pcm['tone'][::2],self.pcm['tone'][1::2]))[::-1]
        self.close_pcm(actual,[v*(1-n/SR/2) for n,frame in enumerate(frames) for v in frame])

    def test_outer_trim_preserves_inner_fade_phase(self):
        self.sequence('child');self.tone('child','child_audio_1');self.sequence('middle')
        self.group('child',target='middle',audio={'fade_in':2});self.group('middle',source_in_tick=TPS,duration_tick=TPS)
        actual,_,_,_=self.render();expected=[v*(.5+n//2/SR/2) for n,v in enumerate(self.pcm['tone'][SR*2:])]+[0.]*SR*2
        self.close_pcm(actual,expected)

    def test_nonlinear_ancestor_gain_uses_inverse_original_clock(self):
        self.sequence('child');self.tone('child','child_audio_1','dc');self.sequence('middle')
        self.group('child',target='middle',audio={'fade_in':2})
        duration=round(2*math.log(2)*TPS)
        self.group('middle',duration_tick=duration,speed_curve={'keyframes':[{'at_tick':0,'speed':1},{'at_tick':2*TPS,'speed':2}]})
        actual,_,_,_=self.render()
        # Compare the same retimed signal without this gain: this test accepts
        # the authored envelope independently of the approximate retimer.
        # Dedicated context tests check the retained native DC regression.
        p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        for s in p['sequences']:
            for t in s['tracks']:
                for c in t['clips']:
                    if c.get('audio',{}).get('fade_in'):c.pop('audio')
        atomic_write_json(self.root/'project.json',p);self.ops=[]
        control,_,_,_=self.render();integral=2*math.log(2);maximum=0
        for n in range(SR//5,SR):
            source=2*math.expm1((n/SR)*integral/(duration/TPS)/2)
            expected_left=control[n*2]*source/2;expected_right=control[n*2+1]*source/2
            maximum=max(maximum,abs(actual[n*2]-expected_left),abs(actual[n*2+1]-expected_right))
        self.assertLessEqual(maximum,2e-6)

    def test_float_mix_preserves_over_unit_peak_for_explicit_mastering(self):
        self.tone(name='dc',audio={'volume':4});self.track('seq_main','loud');self.tone(track='loud',name='dc',audio={'volume':4})
        actual,_,_,_=self.render();self.close_pcm(actual,[v*8 for v in self.pcm['dc']]);self.assertGreater(max(actual),2)

    def test_group_equalizer_and_filters_match_independent_sum_processing(self):
        self.sequence('child');self.tone('child','child_audio_1');self.track('child','high');self.tone('child','high','other')
        self.group('child',audio={'equalizer':{'frequency':400,'gain':-6,'width':1},'highpass':80,'lowpass':5000})
        actual,_,_,_=self.render();expected=self.reference_filter([a+b for a,b in zip(self.pcm['tone'],self.pcm['other'])],
                  'equalizer=f=400:t=q:w=1:g=-6,highpass=f=80,lowpass=f=5000')
        self.close_pcm(actual,expected)

    def test_invalid_container_audio_rolls_back_before_render(self):
        self.sequence('child');self.group('child')
        project_before=(self.root/'project.json').read_bytes();ledger_before=(self.root/'rights-ledger.json').read_bytes()
        for control in ({'volume':-1},{'volume':True},{'volume':5},{'muted':'yes'},{'fade_in':-1},
                        {'compressor':{'threshold':0}},{'compressor':{'ratio':50}},
                        {'reverb':{'delays':'80|100','decays':'0.5'}},{'loudnorm':{'i':1}}):
            with self.subTest(audio=control):
                self.ops[-1]['audio']=control;self.compose(expected=2)
                self.assertEqual((self.root/'project.json').read_bytes(),project_before)
                self.assertEqual((self.root/'rights-ledger.json').read_bytes(),ledger_before)

    def test_invalid_volume_keyframe_is_rejected(self):
        self.sequence('child');self.group('child',keyframes=[{'property':'audio.volume','keyframes':[
            {'at_tick':0,'value':1,'interpolation':'linear'},{'at_tick':TPS,'value':-1,'interpolation':'linear'}]}])
        before=(self.root/'project.json').read_bytes();self.compose(expected=2);self.assertEqual((self.root/'project.json').read_bytes(),before)
