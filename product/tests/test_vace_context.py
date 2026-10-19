"""Generated overlap conditioning and real native I/O; callbacks are not model quality."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

import test_local_vace as vace_fixture
import test_outpainting as outpaint_fixture
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_inpainting import normalize_options
from ai_ad_editor.local_matting import manifest_hash
from ai_ad_editor.local_vace import buffer_budget, normalize_generation, verify_adapter, window_plan
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.vace_context import ConditioningTrace, validate_context_report
from ai_ad_editor.vace_frames import process_frames

ROOT = Path(__file__).resolve().parents[2]
invoke = vace_fixture.invoke


def case(*, frames=8, overlap=2, cuts=None, options=None, mode='previous', source=None,
         mask=None, infer=None, frame_function=process_frames, **sampling):
    if source is None:
        source=np.full((frames,48,64,4),180,np.uint8)
        source[...,3]=np.arange(64,dtype=np.uint8)[None,None,:]*4
    frames,height,width,_=source.shape
    if mask is None:
        mask=np.zeros_like(source);mask[:,16:32,24:40,3]=255
    generation=normalize_generation(prompt='Quiet background.\n保持原文',window_frames=5,
        window_overlap=overlap,scene_cut_frames=cuts,temporal_context=mode,frames=frames,**sampling)
    options=options or normalize_options(grow=0,context=0)
    destination=io.BytesIO();calls=[];model_trace=ConditioningTrace()
    def model(images,masks,g):
        model_trace.add(images,masks)
        calls.append((images.copy(),masks.copy(),copy.deepcopy(g),destination.tell()))
        return infer(images,masks,g) if infer else np.full(images.shape,.2 if g['seed']==0 else .8,np.float32)
    metrics=frame_function(io.BytesIO(np.concatenate([source,mask],axis=2).tobytes()),destination,
        width=width,height=height,frames=frames,options=options,generation=generation,channel='alpha',infer=model)
    output=np.frombuffer(destination.getvalue(),np.uint8).reshape(source.shape)
    execution={'window_input_shapes':[list(row[0].shape[:3]) for row in calls]}
    if mode=='previous' and calls:execution['conditioning_trace']=model_trace.snapshot()
    return source,mask,output,metrics,calls,generation,execution


class PreviousContextTests(unittest.TestCase):
    def validate(self, values):
        source,_,_,metrics,_,generation,execution=values
        validate_context_report(metrics,execution,generation,width=source.shape[2],height=source.shape[1],
                                windows=window_plan(len(source),generation))

    def test_mode_is_explicit_and_none_retains_the_original_canonical_parameters(self):
        default=normalize_generation(prompt='unaltered')
        self.assertEqual(default,normalize_generation(prompt='unaltered',temporal_context='none'))
        self.assertNotIn('temporal_context',default)
        chosen=normalize_generation(prompt='unaltered',temporal_context='previous')
        self.assertEqual(chosen['temporal_context'],'previous')
        self.assertEqual({k:v for k,v in chosen.items() if k!='temporal_context'},default)
        for value in ('future','auto','PREVIOUS',True,1,{},[]):
            with self.subTest(value=value),self.assertRaises(AppError):
                normalize_generation(prompt='unaltered',temporal_context=value)
        with self.assertRaises(AppError):
            normalize_generation(prompt='unaltered',temporal_context='previous',window_overlap=0)

    def test_previous_capacity_is_admitted_before_read_or_model_load(self):
        g=normalize_generation(prompt='background',window_frames=5,window_overlap=2,temporal_context='previous')
        old=normalize_generation(prompt='background',window_frames=5,window_overlap=2)
        extra=64*48*4*2
        self.assertEqual(buffer_budget(64,48,g,512)-buffer_budget(64,48,old,512),extra)
        class NeverRead:
            def read(_self,*args):raise AssertionError('Input must remain unread')
        with self.assertRaisesRegex(ValueError,'WINDOW_BUFFER_BUDGET_EXCEEDED'):
            process_frames(NeverRead(),io.BytesIO(),width=64,height=48,frames=8,
                options=normalize_options(grow=0,context=0),generation=g,channel='alpha',
                budget=buffer_budget(64,48,g,512)-1,infer=lambda *_:self.fail('Must not load'))

    def test_two_windows_receive_emitted_prefix_and_never_replace_it(self):
        values=case();source,mask,output,metrics,calls,_,execution=values
        np.testing.assert_array_equal(output[:,20,30,0],[51]*5+[204]*3)
        np.testing.assert_array_equal(output[...,3],source[...,3])
        selected=mask[...,3]!=0
        np.testing.assert_array_equal(output[~selected],source[~selected])
        self.assertEqual(calls[0][3],0)
        self.assertEqual(calls[1][3],5*64*48*4)
        np.testing.assert_array_equal(calls[1][0][:2],51)
        np.testing.assert_array_equal(calls[1][1][:2],0)
        np.testing.assert_array_equal(calls[1][0][2:][calls[1][1][2:]!=0],127)
        rows=metrics['window_samples'][1]['context_inputs']
        self.assertEqual([row['frame'] for row in rows],[3,4])
        for row in rows:
            self.assertEqual(row['rgba_sha256'],'sha256:'+hashlib.sha256(output[row['frame']].tobytes()).hexdigest())
        report=metrics['temporal_context']
        self.assertEqual((report['windows_conditioned'],report['frames_conditioned'],report['pixels_conditioned']),(1,2,512))
        self.assertEqual(report['input_trace'],execution['conditioning_trace'])
        self.assertEqual(metrics['overlap_frames_blended'],0)
        self.validate(values)

    def test_context_is_after_actual_harmonic_feather_and_quantization(self):
        options=normalize_options(grow=0,context=4,feather=2,blend_mode='harmonic')
        values=case(options=options);source,mask,output,metrics,calls,_,_=values
        self.assertEqual(metrics['blend']['frames'],8)
        x1,y1,x2,y2=metrics['window_samples'][1]['roi']
        for index,global_frame in enumerate((3,4)):
            np.testing.assert_array_equal(calls[1][0][index,:y2-y1,:x2-x1],output[global_frame,y1:y2,x1:x2,:3])
        np.testing.assert_array_equal(output[...,3],source[...,3])
        self.assertTrue(np.any(calls[1][0][:2]!=51))
        self.validate(values)

    def test_high_overlap_retains_bounded_context_and_hashes_all_model_calls(self):
        def ramp(images,masks,g):return np.full(images.shape,g['seed']*.02,np.float32)
        values=case(frames=25,overlap=4,infer=ramp)
        _,_,output,metrics,calls,_,_=values
        self.assertEqual(len(calls),21)
        expected=[0]*5+[int(np.rint(np.float32(seed*.02)*255)) for seed in range(1,21)]
        np.testing.assert_array_equal(output[:,20,30,0],expected)
        report=metrics['temporal_context']
        self.assertEqual((report['peak_frames'],report['peak_bytes'],report['capacity_bytes']),(4,64*48*16,64*48*16))
        self.assertEqual(report['frames_conditioned'],80)
        self.assertEqual(len(metrics['window_samples']),16)
        self.assertEqual((report['input_trace']['calls'],len(report['input_trace']['samples'])),(21,16))
        self.validate(values)

    def test_scene_cuts_clear_conditions_and_keep_original_frame_clock(self):
        values=case(frames=16,cuts=[8]);_,_,output,metrics,calls,_,_=values
        self.assertEqual(len(calls),4)
        self.assertEqual([len(row['context_inputs']) for row in metrics['window_samples']],[0,2,0,2])
        self.assertEqual(metrics['temporal_context']['scene_resets'],1)
        np.testing.assert_array_equal(calls[2][0][calls[2][1]!=0],127)
        self.assertEqual(output.shape[0],16)
        self.validate(values)

    def test_all_empty_masks_bypass_model_and_publish_an_empty_trace(self):
        values=case(mask=np.zeros((8,48,64,4),np.uint8),cuts=[4])
        source,_,output,metrics,calls,_,_=values
        np.testing.assert_array_equal(output,source)
        self.assertEqual(calls,[])
        self.assertEqual((metrics['model_calls'],metrics['empty_windows']),(0,2))
        report=metrics['temporal_context']
        self.assertEqual((report['peak_frames'],report['frames_conditioned']),(0,0))
        self.assertEqual(report['input_trace']['sha256'],'sha256:'+hashlib.sha256(b'').hexdigest())
        self.validate(values)

    def test_known_prefix_with_no_new_selection_does_not_call_the_model(self):
        mask=np.zeros((8,48,64,4),np.uint8);mask[:5,16:32,24:40,3]=255
        values=case(mask=mask);source,_,output,metrics,calls,_,_=values
        self.assertEqual(len(calls),1)
        np.testing.assert_array_equal(output[5:],source[5:])
        self.assertEqual((metrics['model_calls'],metrics['empty_windows']),(1,1))
        self.assertEqual(metrics['window_samples'][1]['context_inputs'],[])
        self.assertEqual(metrics['temporal_context']['frames_conditioned'],0)
        self.validate(values)

    def test_moving_selection_only_reuses_its_own_global_frame(self):
        mask=np.zeros((8,48,64,4),np.uint8)
        for index in range(8):mask[index,12:24,4+index*3:16+index*3,3]=255
        values=case(mask=mask);source,_,output,metrics,calls,_,_=values
        x1,y1,x2,y2=metrics['window_samples'][1]['roi']
        for index,global_frame in enumerate((3,4)):
            np.testing.assert_array_equal(calls[1][0][index,:y2-y1,:x2-x1],output[global_frame,y1:y2,x1:x2,:3])
        selected=mask[...,3]!=0
        np.testing.assert_array_equal(output[~selected],source[~selected])
        np.testing.assert_array_equal(output[...,3],source[...,3])
        self.validate(values)

    def test_removed_colors_cannot_leak_even_with_resizing_and_scaled_conditions(self):
        for factor in (1,2,4):
            observed=[]
            for color in ([255,0,0],[0,0,255]):
                source=np.full((8,96,144,4),180,np.uint8);source[...,3]=192
                source[:,24:72,48:96,:3]=color
                mask=np.zeros_like(source);mask[:,24:72,48:96,3]=255
                values=case(source=source,mask=mask,model_input_scale=factor,
                            options=normalize_options(grow=0,context=256,model_max_edge=64))
                observed.append(values[4]);self.validate(values)
            with self.subTest(factor=factor):
                for left,right in zip(*observed):
                    np.testing.assert_array_equal(left[0],right[0]);np.testing.assert_array_equal(left[1],right[1])
                    np.testing.assert_array_equal(left[0][left[1]!=0],127)
                self.assertTrue(np.all(observed[0][1][1][:2]==0))

    def test_final_padding_repeats_the_last_actual_condition_without_extra_output(self):
        values=case(frames=7);_,_,output,metrics,calls,_,_=values
        self.assertEqual(output.shape[0],7)
        self.assertEqual(metrics['padded_frames'],1)
        np.testing.assert_array_equal(calls[-1][0][-1],calls[-1][0][-2])
        np.testing.assert_array_equal(calls[-1][1][-1],calls[-1][1][-2])
        self.validate(values)

    def test_default_output_matches_the_archived_v67_implementation_byte_for_byte(self):
        evidence=ROOT/'docs/validation/evidence/vace-temporal-context-20261020-v68'
        raw=(evidence/'baseline-v67-source.zip').read_bytes()
        manifest=json.loads((evidence/'baseline-v67-source.json').read_bytes())
        self.assertEqual('sha256:'+hashlib.sha256(raw).hexdigest(),manifest['archive_sha256'])
        name='product/src/ai_ad_editor/vace_frames.py'
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:code=archive.read(name)
        self.assertEqual('sha256:'+hashlib.sha256(code).hexdigest(),manifest['frozen_inputs'][name])
        old=ModuleType('ai_ad_editor._v67_vace_frames');exec(compile(code,'<archived-v67-vace-frames>','exec'),old.__dict__)
        for options in ({},{'overlap':4,'frames':12},{'overlap':0},{'cuts':[3,6]},
                        {'model_input_scale':2},{'options':normalize_options(grow=0,context=12,feather=2)},
                        {'options':normalize_options(grow=0,context=4,blend_mode='harmonic')}):
            with self.subTest(options=options):
                current=case(mode='none',**options);previous=case(mode='none',frame_function=old.process_frames,**options)
                self.assertEqual(current[2].tobytes(),previous[2].tobytes())
                self.assertEqual(current[3]['overlap_frames_blended'],previous[3]['overlap_frames_blended'])
                for left,right in zip(current[4],previous[4],strict=True):
                    np.testing.assert_array_equal(left[0],right[0]);np.testing.assert_array_equal(left[1],right[1])
                    self.assertEqual(left[2:],right[2:])

    def test_trace_bounds_reject_dtype_shape_and_noncontiguous_arrays(self):
        trace=ConditioningTrace();rgb=np.zeros((5,4,6,3),np.uint8);mask=np.zeros((5,4,6),np.uint8)
        for index in range(30):rgb[0,0,0,0]=index;trace.add(rgb,mask)
        value=trace.snapshot();self.assertEqual((value['calls'],len(value['samples'])),(30,16))
        another=ConditioningTrace()
        for index in range(30):rgb[0,0,0,0]=index if index!=29 else 30;another.add(rgb,mask)
        self.assertNotEqual(value['sha256'],another.snapshot()['sha256'])
        for images,masks in ((rgb.astype(np.float32),mask),(rgb,mask[:,:,:5]),(rgb[:,:,::2],mask[:,:,::2])):
            with self.subTest(shape=images.shape),self.assertRaises(ValueError):trace.add(images,masks)

    def test_bad_conditioning_evidence_is_rejected_without_hiding_shape_errors(self):
        values=case();source,_,_,original,_,generation,execution=values
        mutations=[
            lambda m,e:m.pop('temporal_context'),
            lambda m,e:m['temporal_context'].update(generated_context_is_ground_truth=True),
            lambda m,e:m['temporal_context'].update(peak_frames=3),
            lambda m,e:m['temporal_context'].update(peak_bytes=1),
            lambda m,e:m['temporal_context'].update(scene_resets=1),
            lambda m,e:m['temporal_context'].update(cross_scene_frames=1),
            lambda m,e:m['temporal_context'].update(frames_conditioned=1),
            lambda m,e:m['temporal_context'].update(pixels_conditioned=1),
            lambda m,e:m.update(overlap_frames_blended=1),
            lambda m,e:e.pop('conditioning_trace'),
            lambda m,e:e.pop('window_input_shapes'),
            lambda m,e:e['conditioning_trace'].update(sha256='sha256:'+'0'*64),
            lambda m,e:m['temporal_context']['input_trace']['samples'][0].update(mask_shape=[True,64,64]),
            lambda m,e:m['window_samples'][0].update(context_inputs=m['window_samples'][1]['context_inputs']),
            lambda m,e:m['window_samples'][1]['context_inputs'][0].update(frame=5),
            lambda m,e:m['window_samples'][1]['context_inputs'][0].update(rgba_sha256='invalid'),
            lambda m,e:m['window_samples'].__setitem__(0,None),
        ]
        for index,mutate in enumerate(mutations):
            metrics=copy.deepcopy(original);model=copy.deepcopy(execution);mutate(metrics,model)
            with self.subTest(index=index),self.assertRaises(ValueError):
                validate_context_report(metrics,model,generation,width=64,height=48,windows=window_plan(8,generation))

    def test_none_rejects_unrequested_context_metadata(self):
        values=case(mode='none');_,_,_,metrics,_,generation,execution=values
        for left,right in (({**metrics,'temporal_context':{}},execution),(metrics,{'conditioning_trace':{}})):
            with self.assertRaises(ValueError):
                validate_context_report(left,right,generation,width=64,height=48,windows=window_plan(8,generation))


class NativeContextTests(unittest.TestCase):
    metadata=vace_fixture.NativeVaceTests.metadata
    decode=vace_fixture.NativeVaceTests.decode
    fake_command=vace_fixture.NativeVaceTests.fake_command
    ingest=vace_fixture.NativeVaceTests.ingest
    register=vace_fixture.NativeVaceTests.register
    command=vace_fixture.NativeVaceTests.command
    assert_clean_failure=vace_fixture.NativeVaceTests.assert_clean_failure
    setUp=vace_fixture.NativeVaceTests.setUp

    @classmethod
    def setUpClass(cls):configure_local_runtime()

    def test_plan_binds_mode_extra_capacity_and_positive_overlap_before_inference(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code,value=invoke(*self.command(),'--temporal-context','previous','--dry-run')
            self.assertEqual(code,0,value);plan=value['data']['plan']
            self.assertEqual(plan['generation']['temporal_context'],'previous')
            self.assertEqual(plan['owned_array_budget_bytes'],buffer_budget(64,48,plan['generation'],plan['inpainting']['model_max_edge']))
            self.assertEqual(invoke(*self.command(),'--temporal-context','previous','--window-overlap','0','--dry-run')[0],2)
            worker.assert_not_called()
        self.assertEqual(before,self.metadata())

    def test_adapter_closure_requires_the_context_implementation(self):
        adapter=self.register()
        self.assertEqual(sum(a['role']=='temporal_context' for a in adapter['artifacts']),1)
        changed=copy.deepcopy(adapter);changed['artifacts']=[a for a in changed['artifacts'] if a['role']!='temporal_context']
        changed['sha256']=manifest_hash(changed)
        self.assertFalse(verify_adapter(changed)['ok'])

    def test_native_ffmpeg_checks_model_side_trace_outside_rgba_and_pcm(self):
        self.register()
        with self.fake_command():code,value=invoke(*self.command(),'--temporal-context','previous')
        self.assertEqual(code,0,value);result=value['data']['inpainting'];worker=result['worker']
        self.assertEqual(worker['metrics']['temporal_context']['input_trace'],worker['model_execution']['conditioning_trace'])
        self.assertEqual(worker['metrics']['temporal_context']['frames_conditioned'],2)
        source=np.repeat(self.decode(self.source),2,axis=0);output=self.decode(self.output)
        np.testing.assert_array_equal(output[:,:16],source[:,:16]);np.testing.assert_array_equal(output[...,3],source[...,3])
        np.testing.assert_allclose(self.decode(self.output,audio=True),self.decode(self.source,audio=True),atol=1e-5)
        self.assertEqual(len(value['data']['rights']['derived_from']),3)
        self.assertEqual(value['data']['asset']['source']['vace_generation']['temporal_context'],'previous')

    def test_missing_or_mismatched_context_trace_rolls_back_the_native_transaction(self):
        self.register();before=self.metadata()
        for mode in ('missing_context_report','bad_context_trace'):
            with self.subTest(mode=mode),self.fake_command(mode):
                code,value=invoke(*self.command(),'--temporal-context','previous')
            self.assertEqual(code,6,value)
            self.assertEqual(value['errors'][0]['code'],'MATTING_WORKER_OUTPUT_INVALID')
            self.assert_clean_failure(before)

    def test_unrequested_context_is_rejected_by_default_pipeline(self):
        self.register();before=self.metadata()
        with self.fake_command('unrequested_context_report'):code,value=invoke(*self.command())
        self.assertEqual(code,6,value);self.assert_clean_failure(before)

    def test_idempotency_does_not_confuse_previous_with_independent_generation(self):
        self.register();command=[*self.command(),'--temporal-context','previous','--idempotency-key','context-once']
        with self.fake_command():code,value=invoke(*command)
        self.assertEqual(code,0,value)
        with patch('ai_ad_editor.cli.matte_native') as worker:
            self.assertEqual(invoke(*command)[0],0)
            code,value=invoke(*command,'--temporal-context','none')
            self.assertEqual(code,2,value);self.assertEqual(value['errors'][0]['code'],'IDEMPOTENCY_CONFLICT')
            worker.assert_not_called()

    def test_inpaint_generation_survives_packages_and_rebound_fragment_assets(self):
        from ai_ad_editor.project import create_project
        from ai_ad_editor.rights import active_records, load_ledger
        self.register()
        with self.fake_command():code,value=invoke(*self.command(),'--temporal-context','previous')
        self.assertEqual(code,0,value);generation=value['data']['asset']['source']['vace_generation']
        historical_parents=copy.deepcopy(value['data']['asset']['source']['derived_from'])
        rights_parents=copy.deepcopy(value['data']['rights']['derived_from'])
        package=self.base/'inpaint.aevpkg.zip'
        self.assertEqual(invoke('convert','export','--project',str(self.root),'--target-format','package','--output',str(package))[0],0)
        target=self.base/'imported'
        self.assertEqual(invoke('convert','import','--input',str(package),'--output',str(target))[0],0)
        project=json.loads((target/'project.json').read_bytes())
        self.assertEqual(next(a['source']['vace_generation'] for a in project['assets'] if a['id']=='repaired'),generation)
        library=self.base/'library';request=self.base/'fragment.json'
        request.write_text(json.dumps({'id':'inpaint','version':1,'sequence_id':'seq_main'}),encoding='utf8')
        self.assertEqual(invoke('fragment','save','--project',str(self.root),'--library',str(library),'--input',str(request))[0],0)
        target,_=create_project(self.base/'reused')
        request.write_text(json.dumps({'id':'inpaint','version':1,'sequence_id':'seq_main','track_id':'track_video_1','at_tick':0,'instance_id':'reuse'}),encoding='utf8')
        code,value=invoke('fragment','apply','--project',str(target),'--library',str(library),'--input',str(request))
        self.assertEqual(code,0,value)
        project=json.loads((target/'project.json').read_bytes())
        copied=next(a for a in project['assets'] if a.get('source',{}).get('vace_generation'))
        self.assertEqual(copied['source']['vace_generation'],generation)
        self.assertEqual(copied['source']['derived_from'],historical_parents)
        rights_map=value['data']['plan']['id_maps']['right']
        ledger={r['asset_id']:r for r in active_records(load_ledger(target))}
        self.assertEqual(ledger[copied['rights_ref']]['derived_from'],[rights_map[v] for v in rights_parents])
        self.assertTrue(all(rights_map[v] in ledger and rights_map[v]!=v for v in rights_parents))
        self.assertFalse((target/'models').exists())
        self.assertEqual(invoke('validate','--project',str(target))[0],0)

    def test_noncanonical_or_out_of_range_saved_generation_is_rejected(self):
        self.register()
        with self.fake_command():code,value=invoke(*self.command(),'--temporal-context','previous')
        self.assertEqual(code,0,value)
        path=self.root/'project.json';original=path.read_bytes();project=json.loads(original)
        for changes in ({'temporal_context':'auto'},{'window_overlap':0},{'scene_cut_frames':[999]}, {'seed':True}):
            payload=copy.deepcopy(project)
            asset=next(a for a in payload['assets'] if a['id']=='repaired')
            asset['source']['vace_generation'].update(changes)
            path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
            code,value=invoke('validate','--project',str(self.root))
            self.assertEqual(code,2,value)
            self.assertIn('VACE_GENERATION_METADATA_INVALID',[e['code'] for e in value['errors']])
        path.write_bytes(original)


class NativeOutpaintContextTests(unittest.TestCase):
    metadata=outpaint_fixture.NativeVaceOutpaintingTests.metadata
    fake_command=outpaint_fixture.NativeVaceOutpaintingTests.fake_command
    ingest=outpaint_fixture.NativeVaceOutpaintingTests.ingest
    register=outpaint_fixture.NativeVaceOutpaintingTests.register
    setUp=outpaint_fixture.NativeVaceOutpaintingTests.setUp
    command=outpaint_fixture.NativeVaceOutpaintingTests.command

    @classmethod
    def setUpClass(cls):configure_local_runtime()

    def test_outpaint_preserves_original_and_context_recipe_in_package_and_fragment(self):
        from ai_ad_editor.project import create_project
        self.register()
        with self.fake_command():
            code,value=invoke(*self.command(),'--temporal-context','previous','--fps','16','--apply','--track-id','track_video_1')
        self.assertEqual(code,0,value)
        recipe=value['data']['asset']['source']['outpainting']
        self.assertEqual(recipe['generation']['temporal_context'],'previous')
        self.assertEqual(value['data']['outpainting']['worker']['metrics']['temporal_context']['frames_conditioned'],2)
        data=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(self.output),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout
        output=np.frombuffer(data,np.uint8).reshape(-1,64,80,4)
        np.testing.assert_array_equal(output[:,8:56,8:72],np.repeat(self.frames,2,axis=0))
        package=self.base/'context.aevpkg.zip'
        code,value=invoke('convert','export','--project',str(self.root),'--target-format','package','--output',str(package))
        self.assertEqual(code,0,value)
        target=self.base/'imported';code,value=invoke('convert','import','--input',str(package),'--output',str(target))
        self.assertEqual(code,0,value)
        project=json.loads((target/'project.json').read_bytes())
        asset=next(a for a in project['assets'] if a['id']=='repaired')
        self.assertEqual(asset['source']['outpainting'],recipe)
        library=self.base/'library';request=self.base/'fragment.json'
        request.write_text(json.dumps({'id':'context','version':1,'sequence_id':'seq_main'}),encoding='utf8')
        code,value=invoke('fragment','save','--project',str(self.root),'--library',str(library),'--input',str(request))
        self.assertEqual(code,0,value)
        target,_=create_project(self.base/'reuse')
        request.write_text(json.dumps({'id':'context','version':1,'sequence_id':'seq_main','track_id':'track_video_1','at_tick':0,'instance_id':'reuse'}),encoding='utf8')
        code,value=invoke('fragment','apply','--project',str(target),'--library',str(library),'--input',str(request))
        self.assertEqual(code,0,value)
        project=json.loads((target/'project.json').read_bytes())
        rebound=next(a['source']['outpainting'] for a in project['assets'] if a.get('source',{}).get('outpainting'))
        self.assertEqual(rebound['generation'],recipe['generation'])
        self.assertNotEqual(rebound['source_asset_id'],recipe['source_asset_id'])
        self.assertEqual(invoke('validate','--project',str(target))[0],0)


if __name__=='__main__':unittest.main()
