"""Independent opacity clocks, native alpha commands and real retime transfers."""
from __future__ import annotations
import copy
import array
import hashlib
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch

from PIL import Image
from ai_ad_editor.blend_automation import OpacityClock, OpacityCurve
from ai_ad_editor.clip_windows import slice_clip
from ai_ad_editor.edit_planner import build_edit_plan, interchange_features
from ai_ad_editor.effect_automation import EffectAutomation
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.schema_contract import make_validator
from test_magnetic_reorder import invoke, clip, track
from test_retime_edits import state, request, at

SETTINGS={'timebase':{'ticks_per_second':1000,'display_fps':{'num':10,'den':1}}}


def animation(transform=None, *, duration=2000, easing='linear'):
    points=[{'at_tick':0,'value':0.,'interpolation':easing},
            {'at_tick':duration,'value':1.,'interpolation':'linear'}]
    if easing=='bezier': points[0]['control_points']=[1/3,0.,2/3,1.]
    return {'version':1,'author_duration_tick':duration,'keyframes':points,
        'clock_maps':[] if transform is None else [{'input_duration_tick':duration,
            'transform':transform,'offset_tick':0}]}


class OpacityClockContractTests(unittest.TestCase):
    def reject(self, model):
        with self.assertRaises(AppError) as caught: OpacityClock(model, SETTINGS)
        self.assertEqual(caught.exception.code,'BLEND_AUTOMATION_INVALID')

    def test_unknown_fields_versions_and_noninteger_ticks_reject(self):
        for key,value in [('extra',0),('version',True),('version',2),('author_duration_tick',True),
                          ('author_duration_tick',2**53),('author_duration_tick',0)]:
            with self.subTest(key=key,value=value):
                model=animation();model[key]=value;self.reject(model)

    def test_invalid_points_order_nonfinite_values_and_boolean_reject(self):
        for value in (True,-.1,1.1,float('nan'),float('inf'),10**400):
            model=animation();model['keyframes'][0]['value']=value;self.reject(model)
        for points in ([],[{'at_tick':1,'value':0},{'at_tick':0,'value':1}],
                       [{'at_tick':2001,'value':0}],[{'at_tick':False,'value':0}],
                       [{'at_tick':0,'value':0,'expression':'unsafe'}]):
            model=animation();model['keyframes']=points;self.reject(model)

    def test_invalid_easing_control_points_and_bounded_sizes_reject(self):
        for easing,control in [('unknown',[]),('bezier',[0,1,2]),('bezier',[0,0,2,1]),('bezier',[0,float('nan')])]:
            model=animation(easing=easing);model['keyframes'][0]['control_points']=control;self.reject(model)
        model=animation(duration=5000);model['keyframes']=[{'at_tick':i,'value':.5} for i in range(4097)];self.reject(model)
        model=animation({'speed':1});model['clock_maps']*=17;self.reject(model)
        with patch('ai_ad_editor.blend_automation.MAX_MODEL_BYTES',1):self.reject(animation())

    def test_invalid_relative_maps_reject_with_structured_error(self):
        for row in ({'input_duration_tick':0,'transform':{'speed':1},'offset_tick':0},
                    {'input_duration_tick':2000,'transform':{'speed':float('nan')},'offset_tick':0},
                    {'input_duration_tick':2000,'transform':{'reverse':1},'offset_tick':0},
                    {'input_duration_tick':2000,'transform':{'speed':1},'offset_tick':True},
                    {'input_duration_tick':2000,'transform':{'speed':1},'offset_tick':2**53}):
            model=animation();model['clock_maps']=[row];self.reject(model)

    def test_constant_reverse_and_nonlinear_inverse_have_independent_formula(self):
        for transform,expected in [({'speed':2},lambda t:t/1000),
            ({'speed':2,'reverse':True},lambda t:1-t/1000),
            ({'speed_curve':{'keyframes':[{'at_tick':0,'speed':1,'interpolation':'linear'},
                {'at_tick':2000,'speed':3}]}},lambda t:(math.exp(t/1000)-1)/2)]:
            model=OpacityClock(animation(transform),SETTINGS)
            # Curve output is rounded to 1099 ticks; use that declared clock.
            for ratio in (0.,.2,.5,.8):
                tick=(1099 if 'speed_curve' in transform else 1000)*ratio
                actual=model.value_at_tick(tick)
                oracle=expected(tick if 'speed_curve' not in transform else math.log(3)*1000*ratio)
                self.assertAlmostEqual(actual,oracle,places=7)

    def test_freeze_repeats_preceding_display_anchor_then_resumes(self):
        model=OpacityClock(animation({'speed':2,'freeze':{'at_tick':500,'duration_tick':300}}),SETTINGS)
        self.assertEqual([round(model.value_at_tick(i*100),7) for i in range(13)],
                         [0,.1,.2,.3,.4,.4,.4,.4,.5,.6,.7,.8,.9])

    def test_repeated_maps_window_offsets_and_ancestor_inverse_clock(self):
        model=animation({'speed':2});model['clock_maps'].insert(0,
            {'input_duration_tick':1000,'transform':{'speed':.5},'offset_tick':100})
        self.assertAlmostEqual(OpacityClock(model,SETTINGS).value_at_tick(400),.3)
        curve=OpacityCurve(animation(),{'timeline_start_tick':1000,
            '_nested_keyframe_clock':{'maps':[],'authored_start':.6}},1.,1000,Fraction(10))
        self.assertAlmostEqual(curve.value(1.2),.3)


class OpacityRetimePlannerTests(unittest.TestCase):
    def original(self):
        p=state();at(p,'b').update(blend={'mode':'multiply','opacity':.25},keyframes=[
            {'property':'opacity','keyframes':[{'at_tick':0,'value':.5}]},
            {'property':'blend.opacity','keyframes':[{'at_tick':0,'value':0},{'at_tick':10,'value':1}]}])
        return p

    def test_retime_detaches_only_external_blend_and_retains_author_graph(self):
        p=self.original();before=copy.deepcopy(p);out,plan=build_edit_plan(p,'seq',request())
        self.assertEqual(p,before);parent=at(out,'b');inner=plan['created_sequences'][0]['tracks'][0]['clips'][0]
        self.assertEqual(parent['blend']['mode'],'multiply');self.assertNotIn('blend',inner)
        self.assertEqual([k['property'] for k in inner['keyframes']],['opacity'])
        model=parent['blend']['opacity_animation'];self.assertEqual(model['keyframes'],at(p,'b')['keyframes'][1]['keyframes'])
        self.assertEqual(OpacityClock(model,p['settings']).value_at_tick(2),.4)

    def test_repeated_retime_prepends_model_and_new_top_keys_override(self):
        p,_=build_edit_plan(self.original(),'seq',request())
        p,_=build_edit_plan(p,'seq',request({'reverse':True}))
        model=at(p,'b')['blend']['opacity_animation'];self.assertEqual(len(model['clock_maps']),2)
        self.assertAlmostEqual(OpacityClock(model,p['settings']).value_at_tick(1),.8)
        at(p,'b')['keyframes']=[{'property':'blend_opacity','keyframes':[{'at_tick':0,'value':.7}]}]
        p,_=build_edit_plan(p,'seq',request())
        self.assertEqual(len(at(p,'b')['blend']['opacity_animation']['clock_maps']),1)
        self.assertEqual(OpacityClock(at(p,'b')['blend']['opacity_animation'],p['settings']).value_at_tick(0),.7)

    def test_trimmed_author_window_and_linked_intersection_share_host_domain(self):
        p=self.original();c=at(p,'b');c['link_id']='pair'
        overlay=clip('label',12,18,link_id='pair',blend=copy.deepcopy(c['blend']),keyframes=copy.deepcopy(c['keyframes']))
        overlay['keyframes'][1]['keyframes'][-1]['at_tick']=6
        p['sequences'][0]['tracks'].append(track('side',[overlay],order=2))
        out,_=build_edit_plan(p,'seq',request())
        model=at(out,'label')['blend']['opacity_animation']
        self.assertEqual(model['clock_maps'][0]['offset_tick'],-2)
        # At the rider's new first frame, its own author curve still starts at 0.
        self.assertEqual(OpacityClock(model,p['settings']).value_at_tick(1),0.)
        c=at(p,'b');p['sequences'][0]['tracks'][0]['clips'][1]=slice_clip(c,2,8,start=10)
        at(p,'c')['timeline_start_tick']=16;at(p,'d')['timeline_start_tick']=26
        p['sequences'][0]['tracks'][1]['clips']=[]
        out,_=build_edit_plan(p,'seq',request())
        self.assertAlmostEqual(OpacityClock(at(out,'b')['blend']['opacity_animation'],p['settings']).value_at_tick(1),.4)

    def test_clock_depth_overflow_is_atomic(self):
        p=self.original();model=animation({'speed':1},duration=10);model['clock_maps']*=16
        at(p,'b')['blend']['opacity_animation']=model;at(p,'b')['keyframes']=[];before=copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:build_edit_plan(p,'seq',request())
        self.assertEqual(caught.exception.code,'BLEND_AUTOMATION_INVALID');self.assertEqual(p,before)


class NativeOpacityCommandTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='blend-command-');self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def test_six_easings_execute_alpha_only_at_fractional_cfr(self):
        oracle={'hold':lambda t:0.,'linear':lambda t:t,'ease_in':lambda t:t*t,
            'ease_out':lambda t:1-(1-t)**2,'ease_in_out':lambda t:2*t*t if t<.5 else 1-2*(1-t)**2,
            'bezier':lambda t:3*t*t-2*t*t*t}
        for easing,fn in oracle.items():
            with self.subTest(easing=easing):
                model=animation(easing=easing);compiler=EffectAutomation(self.root,'30000/1001',1000)
                chain,meta=compiler.bind_blend(model,{'id':'layer','timeline_start_tick':0},0.,1.)
                source=bytes((31,97,193,128))*4*30
                command=[ffmpeg_path(),'-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
                    '-video_size','2x2','-framerate','30000/1001','-i','pipe:0','-vf',','.join(chain),
                    '-frames:v','30','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1']
                result=subprocess.run(command,input=source,capture_output=True,cwd=self.root)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'));self.assertEqual(len(result.stdout),len(source))
                for i in range(30):
                    pixel=result.stdout[i*16:i*16+4];self.assertEqual(pixel[:3],bytes((31,97,193)))
                    self.assertLessEqual(abs(pixel[3]-round(128*fn(i*1001/30000/2))),1)
                self.assertEqual(meta['kind'],'blend-opacity-automation')

    def test_recursive_budget_native_capability_unique_targets_and_cache_corruption(self):
        compiler=EffectAutomation(self.root,'10',1000);model=animation({'speed':2})
        _,first=compiler.bind_blend(model,{'id':'same'},0,1)
        _,second=compiler.bind_blend(model,{'id':'same'},0,1)
        self.assertNotEqual(first['target'],second['target']);self.assertEqual(compiler.samples,40)
        with patch('ai_ad_editor.effect_automation.MAX_SAMPLES',59):
            with self.assertRaises(AppError) as caught:compiler.bind_blend(model,{},0,1)
            self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_BUDGET')
        with patch('ai_ad_editor.effect_automation.runtime_options',return_value=set()):
            with self.assertRaises(AppError) as caught:EffectAutomation(self.root,'10',1000).bind_blend(model,{},0,1)
            self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE')
        (self.root/first['command_file']).write_bytes(b'corrupt')
        with self.assertRaises(AppError) as caught:EffectAutomation(self.root,'10',1000).bind_blend(model,{'id':'same'},0,1)
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_CACHE_HASH_MISMATCH')


class NativeOpacityIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='blend-integration-');self.addCleanup(temp.cleanup)
        self.workspace=Path(temp.name);self.root,self.project=create_project(self.workspace/'project')
        for name,color in [('back',(30,90,160,255)),('front',(190,110,50,128))]:
            path=self.workspace/(name+'.png');Image.new('RGBA',(64,64),color).save(path)
            code,result=invoke('media','ingest','--project',self.root,'--input',path,'--asset-id',name)
            self.assertEqual(code,0,result)
        self.project=load_project(self.root)[1];self.project['settings'].update(copy.deepcopy(SETTINGS))
        self.project['settings']['canvas']={'width':64,'height':64,'background':'#000000'}
        self.seq=self.project['sequences'][0];self.seq['duration_tick']=4000
        self.seq['tracks']=[track('main',[{'id':'background','asset_id':'back','timeline_start_tick':0,
            'duration_tick':4000,'source_in_tick':0,'source_out_tick':4000}]),
            track('side',[{'id':'foreground','asset_id':'front','timeline_start_tick':1000,'duration_tick':2000,
                'source_in_tick':0,'source_out_tick':2000,'blend':{'mode':'normal','opacity':.25},
                'keyframes':[{'property':'blend.opacity','keyframes':animation()['keyframes']}]}],order=1)]
        save_project(self.root,self.project)

    def foreground(self,p=None):return (p or self.project)['sequences'][0]['tracks'][1]['clips'][0]

    def retime(self,transform):
        p,_=build_edit_plan(self.project,self.seq['id'],{'action':'retime','clip_ids':['foreground'],'transform':transform})
        return p

    def pixels(self,p=None,audio_output=None):
        p=p or self.project;inputs,graph,meta,warnings=build_filter_graph(self.root,p,p['sequences'][0])
        script=self.root/'graph.ffgraph';script.write_text(graph,encoding='utf8')
        command=[ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,'-filter_complex_script',str(script),
            '-map','[vout]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1','-map','[aout]','-f','null','NUL']
        if audio_output is not None:command[-3:]=['-f','s16le','-acodec','pcm_s16le',str(audio_output)]
        result=subprocess.run(command,capture_output=True,cwd=self.root)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        size=64*64*4;self.assertEqual(len(result.stdout)%size,0)
        return [result.stdout[i:i+size] for i in range(0,len(result.stdout),size)],meta,warnings

    def test_normal_multiply_screen_match_independent_opaque_background_formula(self):
        bg=(30,90,160);fg=(190,110,50)
        for mode in ('normal','multiply','screen'):
            with self.subTest(mode=mode):
                self.foreground()['blend']['mode']=mode;p=self.retime({'speed':2})
                frames,meta,_=self.pixels(p);self.assertEqual(len(frames),40)
                for i in range(40):
                    weight=(i-10)/10 if 10<=i<20 else 0
                    alpha=round(128*weight)/255
                    mixed=fg if mode=='normal' else tuple(a*b/255 if mode=='multiply' else 255-(255-a)*(255-b)/255 for a,b in zip(bg,fg))
                    expected=tuple(round(a*(1-alpha)+b*alpha) for a,b in zip(bg,mixed))
                    self.assertLessEqual(max(abs(a-b) for a,b in zip(frames[i][:3],expected)),2,(mode,i,frames[i][:4],expected))
                    self.assertEqual(frames[i][3],255)
                control=next(x for x in meta if x.get('kind')=='blend-opacity-automation')
                self.assertEqual(control['clock_stages'],1);self.assertEqual(control['sampled_frames'],10)

    def test_reverse_and_freeze_resume_at_declared_author_curve(self):
        for transform,weights in [({'speed':2,'reverse':True},[1-i/10 for i in range(10)]),
            ({'speed':2,'freeze':{'at_tick':500,'duration_tick':300}},[0,.1,.2,.3,.4,.4,.4,.4,.5,.6,.7,.8,.9])]:
            with self.subTest(transform=transform):
                frames,_,_=self.pixels(self.retime(transform))
                for i,w in enumerate(weights):
                    alpha=round(128*w)/255
                    expected=[round(b*(1-alpha)+f*alpha) for b,f in zip((30,90,160),(190,110,50))]
                    self.assertLessEqual(max(abs(a-b) for a,b in zip(frames[10+i][:3],expected)),2,(i,transform))

    def test_trim_and_split_preserve_saved_clock_phase(self):
        from ai_ad_editor.clip_windows import apply_operation
        p=self.retime({'speed':2});before=self.pixels(p)[0]
        trimmed,_=apply_operation(p,self.seq['id'],{'op':'trim_clip','clip_id':'foreground',
            'start_tick':200,'end_tick':800,'timeline_start_tick':1200})
        frames=self.pixels(trimmed)[0];self.assertEqual(frames[12:18],before[12:18])
        split,_=apply_operation(p,self.seq['id'],{'op':'split_clip','clip_id':'foreground','at_tick':500})
        self.assertEqual(self.pixels(split)[0],before)

    def test_schema_semantic_validation_and_external_loss_reporting(self):
        p=self.retime({'speed':2});self.assertEqual(list(make_validator().iter_errors(p)),[])
        self.assertIn('blend.opacity_animation',interchange_features(p))
        invalid=copy.deepcopy(p);self.foreground(invalid)['blend']['opacity_animation']['version']=2
        self.assertTrue(list(make_validator().iter_errors(invalid)))
        save_project(self.root,p)
        for fmt,extension in [('otio','otio'),('kdenlive-xml','mlt')]:
            code,result=invoke('convert','export','--project',self.root,'--target-format',fmt,'--output',self.workspace/('external.'+extension))
            self.assertEqual(code,2,result)  # Nested author sequences are not flattened for external editors.
            report=result['data']['report_data']
            self.assertTrue(any(x['status']=='Unsupported' and x.get('source')=='blend.opacity_animation' for x in report['items']),report)

    def test_real_cli_dry_run_atomic_failure_and_package_rebuild(self):
        q=self.workspace/'request.json';q.write_text(json.dumps({'action':'retime','clip_ids':['foreground'],'transform':{'speed':2}}),encoding='utf8')
        before=(self.root/'project.json').read_bytes()
        code,result=invoke('timeline','edit','--project',self.root,'--sequence-id',self.seq['id'],'--input',q,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual((self.root/'project.json').read_bytes(),before)
        code,result=invoke('timeline','edit','--project',self.root,'--sequence-id',self.seq['id'],'--input',q)
        self.assertEqual(code,0,result);p=load_project(self.root)[1];expected=self.pixels(p)[0]
        package=self.workspace/'portable.zip'
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package');self.assertEqual(code,0,result)
        target=self.workspace/'imported';code,result=invoke('convert','import','--input',package,'--output',target);self.assertEqual(code,0,result)
        self.root=target;imported=load_project(target)[1]
        self.assertEqual(self.foreground(imported)['blend'],self.foreground(p)['blend'])
        self.assertEqual(self.pixels(imported)[0],expected)
        q.write_text(json.dumps({'operations':[{'op':'retime_clip','clip_id':'foreground','transform':{'reverse':True}},
            {'op':'update_clip','clip_id':'background','patch':{'duration_tick':0}}]}),encoding='utf8')
        before=(self.root/'project.json').read_bytes()
        code,result=invoke('timeline','compose','--project',self.root,'--sequence-id',self.seq['id'],'--input',q)
        self.assertNotEqual(code,0,result);self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_transparent_delivery_preserves_original_coverage_once(self):
        self.project['settings'].setdefault('output',{}).setdefault('video',{})['pixel_format']='yuva420p'
        self.seq['tracks'][0]['clips']=[];p=self.retime({'speed':2})
        frames,_,_=self.pixels(p)
        for i in range(10):
            pixel=frames[10+i][:4]
            self.assertLessEqual(abs(pixel[3]-round(128*i/10)),1,(i,list(pixel)))
            if i:
                self.assertLessEqual(max(abs(a-b) for a,b in zip(pixel[:3],(190,110,50))),1)

    def test_new_top_level_curve_overrides_saved_curve_at_render(self):
        p=self.retime({'speed':2});self.foreground(p)['keyframes']=[{
            'property':'blend.opacity','keyframes':[{'at_tick':0,'value':.5}]}]
        frames,meta,_=self.pixels(p)
        self.assertFalse(any(x.get('kind')=='blend-opacity-automation' for x in meta))
        self.assertEqual(frames[10:20],[frames[10]]*10)
        expected=[round(b*(1-64/255)+f*64/255) for b,f in zip((30,90,160),(190,110,50))]
        self.assertLessEqual(max(abs(a-b) for a,b in zip(frames[10][:3],expected)),2)

    def test_fragment_transfer_keeps_clock_and_rebuilds_commands(self):
        p=self.retime({'speed':2});save_project(self.root,p);before=self.pixels(p)[0]
        library=self.workspace/'library';q=self.workspace/'fragment.json'
        q.write_text(json.dumps({'id':'blended','version':1,'name':'Editable blend','sequence_id':self.seq['id']}),encoding='utf8')
        code,result=invoke('fragment','save','--project',self.root,'--library',library,'--input',q);self.assertEqual(code,0,result)
        target,new=create_project(self.workspace/'fragment-target');new['settings']=copy.deepcopy(p['settings']);save_project(target,new)
        q.write_text(json.dumps({'id':'blended','version':1,'sequence_id':new['sequences'][0]['id'],
            'track_id':new['sequences'][0]['tracks'][0]['id'],'at_tick':0}),encoding='utf8')
        code,result=invoke('fragment','apply','--project',target,'--library',library,'--input',q);self.assertEqual(code,0,result)
        self.root=target;self.assertEqual(self.pixels(load_project(target)[1])[0],before)

    def test_ancestor_speed_and_reverse_preserve_external_curve_phase(self):
        p=self.retime({'speed':2});child=p['sequences'][0];outer=copy.deepcopy(child)
        outer.update(id='outer',duration_tick=2000,tracks=[track('outer-lane',[{'id':'container',
            'sequence_id':child['id'],'timeline_start_tick':0,'duration_tick':2000,
            'source_in_tick':0,'source_out_tick':4000,'speed':2,'reverse':True}])])
        p['sequences'].insert(0,outer);frames,_,_=self.pixels(p)
        self.assertEqual(len(frames),20)
        # An isolated ancestor transforms the already rendered 40-frame child.
        # Native reverse starts at frame 39; 2x selects 39,37,...,1. This is
        # distinct from continuously resampling an external author parameter.
        for i in range(20):
            source_frame=39-2*i;weight=(source_frame-10)/10 if 10<=source_frame<20 else 0
            alpha=round(128*weight)/255
            expected=[round(b*(1-alpha)+f*alpha) for b,f in zip((30,90,160),(190,110,50))]
            self.assertLessEqual(max(abs(a-b) for a,b in zip(frames[i][:3],expected)),2,(i,list(frames[i][:4]),expected))

    def test_silent_reversed_frozen_layer_leaves_every_background_PCM_sample_exact(self):
        pcm=array.array('h',((i%997-498)*5 for i in range(48000*4*2))).tobytes()
        path=self.workspace/'stereo.wav'
        with wave.open(str(path),'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(pcm)
        code,result=invoke('media','ingest','--project',self.root,'--input',path,'--asset-id','bed')
        self.assertEqual(code,0,result);self.project['assets']=load_project(self.root)[1]['assets']
        self.seq['tracks'].append(track('bed-lane',[{'id':'bed-clip','asset_id':'bed','timeline_start_tick':0,
            'duration_tick':4000,'source_in_tick':0,'source_out_tick':4000}],'audio',2))
        p=self.retime({'speed':2,'reverse':True,'freeze':{'at_tick':500,'duration_tick':300}})
        output=self.workspace/'actual.pcm';self.pixels(p,audio_output=output)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),hashlib.sha256(pcm).hexdigest())


if __name__=='__main__':unittest.main()
