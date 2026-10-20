"""LUT clocks, independent RGB oracles, alpha and portable author data."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.effect_automation import EffectAutomation, validate
from ai_ad_editor.effects import get_effect
from ai_ad_editor.errors import AppError
from ai_ad_editor.lut_library import prepare_lut_intensity
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, save_project, load_project
from ai_ad_editor.queue_reuse import _dependency_paths, file_entry
from ai_ad_editor.render import _effect_filters, build_filter_graph
from test_magnetic_reorder import invoke

TPS=90000
PIXELS=bytes((32,96,192,0, 60,100,140,31, 180,90,40,128, 210,200,190,255))*8


def lut_effect(path='look.cube', left=0., right=1., end=TPS, easing='linear', kind='lut3d'):
    return {'type':kind,'parameters':{'path':path,'intensity':0},'keyframes':[
        {'property':'intensity','keyframes':[{'at_tick':0,'value':left,'interpolation':easing},
                                           {'at_tick':end,'value':right,'interpolation':'linear'}]}]}


def cube(path, *, neutral=False):
    path.write_text('LUT_3D_SIZE 2\n'+''.join(
        f'{r if neutral else 1} {g if neutral else 0} {b if neutral else 0}\n'
        for b in (0,1) for g in (0,1) for r in (0,1)),encoding='utf8')
    return path


class LutCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lut-automation-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);cube(self.root/'look.cube')

    def bind(self, effect=None, *, compiler=None, clip=None, start=0):
        compiler=compiler or EffectAutomation(self.root,'10',TPS)
        metadata=[];warnings=[]
        filters=_effect_filters([effect or lut_effect()],warnings,'clip',root=self.root,
            clip=clip or {'id':'clip','timeline_start_tick':round(start*TPS),'duration_tick':TPS},
            clip_start=start,tps=TPS,automation=compiler,automation_meta=metadata)
        return ','.join(filters),metadata,compiler,warnings

    def native(self, chain, count=10, rate='10', start=0):
        # The connected fragment is exercised with real upstream/downstream
        # filters, as in all renderer effect-chain call sites.
        graph=f'[0:v]setpts=PTS+{start}/TB,{chain},format=rgba[out]'
        result=subprocess.run([ffmpeg_path(),'-v','error','-filter_complex_threads','1',
            '-f','rawvideo','-pixel_format','rgba','-video_size','8x4','-framerate',rate,'-i','pipe:0',
            '-filter_complex',graph,'-map','[out]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'],
            input=PIXELS*count,capture_output=True,cwd=self.root)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        self.assertEqual(len(result.stdout),len(PIXELS)*count)
        return [result.stdout[i:i+128] for i in range(0,len(result.stdout),128)]

    def assert_mix(self, frame, strength, tolerance=1):
        # Independent arithmetic oracle for a solid-red transform. No
        # renderer, command-file parser or LUT interpolation in the oracle.
        expected=bytes(v if i%4==3 else round(v*(1-strength)+(255 if i%4==0 else 0)*strength)
                       for i,v in enumerate(PIXELS))
        self.assertLessEqual(max(abs(a-b) for a,b in zip(frame,expected)),tolerance)
        self.assertEqual(frame[3::4],PIXELS[3::4])


class LutStaticTests(LutCase):
    def test_neutral_cube_preserves_non_gray_rgb_at_all_static_strengths(self):
        cube(self.root/'look.cube',neutral=True)
        for strength in (0.,.25,.5,.75,1.):
            with self.subTest(strength=strength):
                chain,_,_,_=self.bind({'type':'lut3d','path':'look.cube','intensity':strength})
                self.assertEqual(self.native(chain or 'null',1)[0],PIXELS)

    def test_derived_cache_is_versioned_and_strength_keys_do_not_round_collide(self):
        source=self.root/'look.cube'
        old=hashlib.sha256((hashlib.sha256(source.read_bytes()).hexdigest()+'\n0.500000000').encode()).hexdigest()
        old_path=self.root/'cache/luts'/f'{old}.cube';old_path.parent.mkdir(parents=True);old_path.write_bytes(b'old-bad-table')
        a=prepare_lut_intensity(self.root,source,.5);b=prepare_lut_intensity(self.root,source,.5000000001)
        self.assertNotEqual(a,old_path);self.assertNotEqual(a,b)
        self.assertEqual(old_path.read_bytes(),b'old-bad-table')

    def test_changed_lut_bytes_invalidate_static_cache(self):
        source=self.root/'look.cube';a=prepare_lut_intensity(self.root,source,.5)
        cube(source,neutral=True);b=prepare_lut_intensity(self.root,source,.5)
        self.assertNotEqual(a,b)
        self.assertNotEqual(a.read_bytes(),b.read_bytes())

    def test_corrupt_static_cache_is_preserved_and_rejected_by_renderer(self):
        p=prepare_lut_intensity(self.root,self.root/'look.cube',.5);p.write_bytes(b'corrupt')
        with self.assertRaises(AppError) as caught:self.bind({'type':'lut3d','path':'look.cube','intensity':.5})
        self.assertEqual(caught.exception.code,'LUT_INTENSITY_CACHE_HASH_MISMATCH')
        self.assertEqual(p.read_bytes(),b'corrupt')


class LutAutomationContractTests(LutCase):
    def test_catalog_and_all_four_aliases_offer_only_intensity(self):
        for kind in ('lut3d','lut','cube','look'):
            self.assertEqual(get_effect(kind)['keyframe_parameters'],['intensity'])
            self.assertTrue(get_effect(kind)['keyframable'])
            self.assertEqual(validate(lut_effect(kind=kind)),[])

    def test_invalid_channels_numbers_and_times_reject_instead_of_static_fallback(self):
        for prop in ('path','lut_id','interpolation','c3_opacity','intensity;evil'):
            value=lut_effect();value['keyframes'][0]['property']=prop
            with self.subTest(prop=prop):
                with self.assertRaises(AppError) as caught:self.bind(value)
                self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED')
        for number in (True,'0.5',math.inf,math.nan,-.1,1.1):
            value=lut_effect();value['keyframes'][0]['keyframes'][0]['value']=number
            self.assertIn('EFFECT_AUTOMATION_VALUE_INVALID',{x['code'] for x in validate(value)})
        value=lut_effect();value['keyframes'][0]['keyframes'][1]['at_tick']=TPS+1
        self.assertIn('EFFECT_AUTOMATION_TIME_INVALID',{x['code'] for x in validate(value,duration_tick=TPS)})

    def test_native_runtime_missing_rejects_without_cache(self):
        with patch('ai_ad_editor.effect_automation.runtime_options',return_value=frozenset()):
            with self.assertRaises(AppError) as caught:self.bind()
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE')
        self.assertFalse((self.root/'cache').exists())

    def test_resource_hashes_unique_targets_and_deterministic_replay(self):
        compiler=EffectAutomation(self.root,'10',TPS)
        a=self.bind(compiler=compiler)[1][0];b=self.bind(compiler=compiler)[1][0]
        self.assertNotEqual(a['target'],b['target']);self.assertEqual(a,self.bind()[1][0])
        self.assertEqual(a['resource_context']['lut_sha256'],'sha256:'+hashlib.sha256((self.root/'look.cube').read_bytes()).hexdigest())
        cube(self.root/'look.cube',neutral=True);c=self.bind()[1][0]
        self.assertNotEqual(a['target'],c['target'])
        self.assertNotEqual(a['resource_context']['lut_sha256'],c['resource_context']['lut_sha256'])

    def test_global_budget_shared_with_other_color_families(self):
        compiler=EffectAutomation(self.root,'10',TPS);self.bind(compiler=compiler)
        other={'type':'exposure','keyframes':[{'property':'amount','keyframes':[
            {'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':TPS,'value':1,'interpolation':'linear'}]}]}
        with patch('ai_ad_editor.effect_automation.MAX_SAMPLES',19):
            with self.assertRaises(AppError) as caught:self.bind(other,compiler=compiler)
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_BUDGET')
        self.assertEqual(compiler.targets,1)

    def test_three_native_commands_per_changed_strength_are_budgeted(self):
        with patch('ai_ad_editor.effect_automation.MAX_COMMANDS',29):
            with self.assertRaises(AppError) as caught:self.bind()
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_BUDGET')

    def test_command_corruption_is_preserved_and_rejected(self):
        metadata=self.bind()[1][0];p=self.root/metadata['command_file'];p.write_bytes(b'corrupt')
        with self.assertRaises(AppError) as caught:self.bind()
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_CACHE_HASH_MISMATCH')
        self.assertEqual(p.read_bytes(),b'corrupt')


class LutAutomationNativeTests(LutCase):
    def test_linear_zero_static_default_does_not_disable_dynamic_mix_or_alpha(self):
        chain,meta,_,warnings=self.bind()
        for index,frame in enumerate(self.native(chain)):self.assert_mix(frame,index/10)
        self.assertEqual(warnings,[]);self.assertEqual(meta[0]['command_count'],30)

    def test_all_six_easings_match_independent_arithmetic_at_every_frame(self):
        formulas={'hold':lambda x:0.,'linear':lambda x:x,'ease_in':lambda x:x*x,
                  'ease_out':lambda x:x*(2-x),'ease_in_out':lambda x:2*x*x if x<.5 else 1-2*(1-x)**2,
                  'bezier':lambda x:3*x*x-2*x*x*x}
        for name,formula in formulas.items():
            value=lut_effect(easing=name)
            if name=='bezier':value['keyframes'][0]['keyframes'][0]['control_points']=[0,1]
            with self.subTest(easing=name):
                for i,frame in enumerate(self.native(self.bind(value)[0])):self.assert_mix(frame,formula(i/10))

    def test_hold_changes_on_exact_frame_and_fractional_fps_has_no_drift(self):
        value=lut_effect(end=45000,easing='hold')
        for i,frame in enumerate(self.native(self.bind(value)[0])):self.assert_mix(frame,0. if i<5 else 1.)
        compiler=EffectAutomation(self.root,'30000/1001',TPS)
        chain,metadata,_,_=self.bind(compiler=compiler)
        for i,frame in enumerate(self.native(chain,count=30,rate='30000/1001')):self.assert_mix(frame,i*1001/30000)
        self.assertEqual(metadata[0]['sampled_frames'],30)

    def test_nonzero_start_samples_local_author_clock(self):
        chain,_,_,_=self.bind(start=.2)
        for i,frame in enumerate(self.native(chain,start=.2)):self.assert_mix(frame,i/10)

    def test_reverse_ancestor_clock_samples_original_author_ticks(self):
        mapping={'source_start':0.,'source_end':1.,'timeline_start':.2,'timeline_duration':1.,
                 'speed':1.,'reverse':True,'segments':[],'curve_scale':1.}
        clip={'id':'clip','timeline_start_tick':18000,'duration_tick':TPS,
              '_nested_keyframe_clock':{'maps':[mapping],'authored_start':0.}}
        chain,_,_,_=self.bind(clip=clip,start=.2)
        for i,frame in enumerate(self.native(chain,start=.2)):self.assert_mix(frame,1-i/10)

    def test_two_identical_instances_can_be_chained_without_label_or_command_collision(self):
        compiler=EffectAutomation(self.root,'10',TPS)
        a=self.bind(compiler=compiler)[0];b=self.bind(compiler=compiler)[0]
        # Each 8-bit stage can truncate by one code value, so two stages
        # have a two-code arithmetic bound; alpha must still be exact.
        for i,frame in enumerate(self.native(a+','+b)):self.assert_mix(frame,1-(1-i/10)**2,tolerance=2)

    def test_neutral_lut_keeps_alpha_and_rgb_for_dynamic_strength(self):
        cube(self.root/'look.cube',neutral=True)
        for frame in self.native(self.bind()[0]):
            self.assertLessEqual(max(abs(a-b) for a,b in zip(frame,PIXELS)),1)
            self.assertEqual(frame[3::4],PIXELS[3::4])

    def test_3dl_native_format_executes_dynamic_strength_without_cube_materialization(self):
        source=self.root/'red.3dl';source.write_text('0 256 512 768 1024 1280 1536 1792 2048 2304 2560 2816 3072 3328 3584 3840 4096\n'+'4096 0 0\n'*(17**3))
        chain,_,_,warnings=self.bind(lut_effect(path='red.3dl'))
        for i,frame in enumerate(self.native(chain)):self.assert_mix(frame,i/10)
        self.assertEqual(warnings,[]);self.assertFalse((self.root/'cache/luts').exists())

    def test_dat_and_cinespace_native_formats_execute_the_same_pixel_mix(self):
        formats={'red.dat':'3DLUTSIZE 33\n'+'1 0 0\n'*(33**3),
                 'red.csp':'CSPLUTV100\n3D\n'+('2\n0 1\n0 1\n'*3)+'2 2 2\n'+'1 0 0\n'*8}
        for name,text in formats.items():
            (self.root/name).write_text(text,encoding='utf8')
            with self.subTest(format=name):
                for i,frame in enumerate(self.native(self.bind(lut_effect(path=name))[0])):self.assert_mix(frame,i/10)


class LutAutomationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lut-integration-');self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name);self.root,self.project=create_project(self.workspace/'project')
        source=self.workspace/'source.png';Image.new('RGB',(32,16),(32,96,192)).save(source)
        code,ingest=invoke('media','ingest','--project',self.root,'--input',source)
        self.assertEqual(code,0,ingest);self.project=load_project(self.root)[1]
        self.project['settings']['canvas']={'width':32,'height':16,'background':'#000000'}
        self.project['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':10,'den':1}}
        cube(self.root/'look.cube');self.seq=self.project['sequences'][0];self.seq['duration_tick']=TPS
        self.seq['tracks'][0]['clips']=[{'id':'picture','asset_id':ingest['data']['asset']['id'],
            'timeline_start_tick':0,'duration_tick':TPS,'source_in_tick':0,'source_out_tick':TPS,'effects':[lut_effect()]}]
        save_project(self.root,self.project)

    def pixels(self, project=None):
        project=project or self.project
        inputs,graph,meta,warnings=build_filter_graph(self.root,project,project['sequences'][0])
        script=self.root/'graph.ffgraph';script.write_text(graph,encoding='utf8')
        command=[ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,
            '-filter_complex_script',str(script),'-map','[vout]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1',
            '-map','[aout]','-f','null','NUL']
        result=subprocess.run(command,capture_output=True,cwd=self.root)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        self.assertEqual(len(result.stdout)%2048,0)
        return [result.stdout[i:i+2048] for i in range(0,len(result.stdout),2048)],meta,warnings

    def test_real_cli_render_records_lut_source_and_per_frame_commands(self):
        output=self.root/'renders/lut.mkv'
        code,result=invoke('render','--project',self.root,'--output',output)
        self.assertEqual(code,0,result);self.assertTrue(output.is_file())
        manifest=json.loads(Path(result['data']['manifest']).read_bytes())
        metadata=next(x for x in manifest['inputs'] if x.get('kind')=='effect-automation')
        self.assertEqual(metadata['parameters'],['intensity'])
        self.assertEqual(metadata['resource_context']['alpha'],'unchanged')

    def test_trim_and_split_preserve_original_non_linear_author_animation(self):
        self.seq['tracks'][0]['clips'][0]['effects']=[lut_effect(easing='ease_in_out')]
        before=self.pixels()[0]
        trimmed,_=apply_operation(self.project,self.seq['id'],{'op':'trim_clip','clip_id':'picture',
            'start_tick':18000,'end_tick':72000,'timeline_start_tick':0})
        trimmed['sequences'][0]['duration_tick']=54000
        self.assertEqual(self.pixels(trimmed)[0],before[2:8])
        split,_=apply_operation(self.project,self.seq['id'],{'op':'split_clip','clip_id':'picture','at_tick':45000})
        self.assertEqual(self.pixels(split)[0],before)

    def test_nested_reverse_and_parent_own_lut_have_shared_unique_allocation(self):
        child=copy.deepcopy(self.seq);child['id']='child';child['tracks'][0]['id']='child_track'
        child['tracks'][0]['clips'][0]['id']='leaf';self.project['sequences'].append(child)
        self.seq['tracks'][0]['clips']=[{'id':'container','sequence_id':'child','timeline_start_tick':0,
            'duration_tick':TPS,'source_in_tick':0,'source_out_tick':TPS,'reverse':True,'effects':[lut_effect()]}]
        frames,meta,_=self.pixels()
        targets=[x for x in meta if x.get('kind')=='effect-automation']
        self.assertEqual(len(targets),2);self.assertEqual(len({x['target'] for x in targets}),2)
        # Inner strength is 1-t, outer t; resulting red contribution 1-t+t².
        for i,f in enumerate(frames):
            t=i/10;w=1-t+t*t
            expected=(round(32*(1-w)+255*w),round(96*(1-w)),round(192*(1-w)))
            self.assertLessEqual(max(abs(a-b) for a,b in zip(f[:3],expected)),2)

    def test_interval_adjustment_has_local_clock_and_unaffected_outside_frames(self):
        self.seq['tracks'][0]['clips'][0].pop('effects')
        before=self.pixels()[0]
        self.project['settings']['adjustments']=[{'id':'grade','start_tick':18000,'duration_tick':54000,
                                                'effects':[lut_effect(end=54000)]}]
        frames,meta,_=self.pixels()
        self.assertEqual(frames[:2],before[:2]);self.assertEqual(frames[8:],before[8:])
        self.assertEqual(frames[2],before[2]);self.assertNotEqual(frames[7],before[7])
        self.assertEqual(next(x for x in meta if x.get('kind')=='effect-automation')['sampled_frames'],6)

    def test_text_layer_runs_dynamic_lut_on_raster_and_preserves_transparent_border(self):
        self.project['settings'].setdefault('output',{}).setdefault('video',{})['pixel_format']='yuva420p'
        self.seq['tracks'][0]['clips']=[]
        self.seq['tracks'].append({'id':'words','kind':'subtitle','order':2,'clips':[{
            'id':'caption','timeline_start_tick':0,'duration_tick':TPS,'source_in_tick':0,'source_out_tick':TPS,
            'subtitle':{'text':'TEST','style':{'fontsize':10,'fontcolor':'#ffffff','box':False,'x':.1,'y':.2}},
            'effects':[lut_effect()]}]})
        frames,meta,_=self.pixels()
        self.assertEqual(len(frames),10);self.assertNotEqual(frames[0],frames[-1])
        self.assertEqual(frames[0][3::4],frames[-1][3::4])
        self.assertIn(0,frames[0][3::4]);self.assertGreater(max(frames[0][3::4]),0)
        self.assertEqual(len([x for x in meta if x.get('kind')=='effect-automation']),1)

    def test_package_roundtrip_keeps_editable_keyframes_and_native_output(self):
        before=self.pixels()[0];package=self.workspace/'export.zip'
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package')
        self.assertEqual(code,0,result)
        target=self.workspace/'imported';code,result=invoke('convert','import','--input',package,'--output',target)
        self.assertEqual(code,0,result)
        original=self.root;self.root=target
        imported=load_project(target)[1]
        effects=imported['sequences'][0]['tracks'][0]['clips'][0]['effects']
        self.assertEqual(effects[0]['keyframes'],self.seq['tracks'][0]['clips'][0]['effects'][0]['keyframes'])
        self.assertEqual((target/effects[0]['parameters']['path']).read_bytes(),(original/'look.cube').read_bytes())
        self.assertEqual(self.pixels(imported)[0],before);self.root=original

    def test_queue_dependency_snapshot_binds_actual_lut_bytes(self):
        paths=_dependency_paths(self.root,self.project,self.project['settings'])
        lut=(self.root/'look.cube').resolve();self.assertIn(lut,paths)
        before=file_entry(lut);cube(lut,neutral=True)
        self.assertNotEqual(before,file_entry(lut))

    def test_registered_lut_package_resolves_id_preserves_bytes_and_keyframes(self):
        code,result=invoke('lut','register','--project',self.root,'--input',self.root/'look.cube','--lut-id','warm')
        self.assertEqual(code,0,result)
        self.seq['tracks'][0]['clips'][0]['effects'][0]['parameters']={'lut_id':'warm','intensity':0}
        save_project(self.root,self.project);before=self.pixels()[0]
        package=self.workspace/'registered.zip'
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package')
        self.assertEqual(code,0,result)
        target=self.workspace/'registered-import';code,result=invoke('convert','import','--input',package,'--output',target)
        self.assertEqual(code,0,result);imported=load_project(target)[1]
        effect=imported['sequences'][0]['tracks'][0]['clips'][0]['effects'][0]
        self.assertNotIn('lut_id',effect['parameters'])
        self.assertEqual(effect['keyframes'],lut_effect()['keyframes'])
        self.root=target;self.assertEqual(self.pixels(imported)[0],before)

    def test_package_rejects_missing_and_changed_registered_lut_before_creating_zip(self):
        path=self.root/'look.cube';data=path.read_bytes();path.unlink()
        package=self.workspace/'missing.zip'
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package')
        self.assertNotEqual(code,0,result);self.assertFalse(package.exists())
        path.write_bytes(data)
        code,result=invoke('lut','register','--project',self.root,'--input',path,'--lut-id','warm')
        self.assertEqual(code,0,result)
        self.seq['tracks'][0]['clips'][0]['effects'][0]['parameters']={'lut_id':'warm'};save_project(self.root,self.project)
        from ai_ad_editor.lut_library import resolve_lut_path
        registered=resolve_lut_path(self.root,'warm')[0];registered.write_bytes(data+b'# changed\n')
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package')
        self.assertNotEqual(code,0,result);self.assertFalse(package.exists())

    def test_edited_fragment_reuse_rebuilds_dynamic_lut_in_fresh_project(self):
        code,result=invoke('lut','register','--project',self.root,'--input',self.root/'look.cube','--lut-id','warm')
        self.assertEqual(code,0,result)
        self.seq['tracks'][0]['clips'][0]['effects'][0]['parameters']={'lut_id':'warm','intensity':0}
        save_project(self.root,self.project)
        before=self.pixels()[0];library=self.workspace/'library';request=self.workspace/'fragment.json'
        request.write_text(json.dumps({'id':'look','version':1,'name':'Animated LUT','sequence_id':self.seq['id']}),encoding='utf8')
        code,result=invoke('fragment','save','--project',self.root,'--library',library,'--input',request)
        self.assertEqual(code,0,result)
        target,p=create_project(self.workspace/'fragment-target');p['settings']=copy.deepcopy(self.project['settings']);save_project(target,p)
        request.write_text(json.dumps({'id':'look','version':1,'sequence_id':p['sequences'][0]['id'],
            'track_id':p['sequences'][0]['tracks'][0]['id'],'at_tick':0}),encoding='utf8')
        code,result=invoke('fragment','apply','--project',target,'--library',library,'--input',request)
        self.assertEqual(code,0,result);self.root=target
        imported=load_project(target)[1];self.assertEqual(self.pixels(imported)[0],before)


if __name__=='__main__':unittest.main()
