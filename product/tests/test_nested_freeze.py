"""Decoded frame identities and complete-bus samples for compound holds."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import subprocess
from unittest.mock import patch
import unittest

import numpy as np
from PIL import ImageFont

import test_source_transitions as base
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.errors import AppError
from ai_ad_editor.inline_sequences import transition_descendants
from ai_ad_editor.project import save_project
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.validator import validate_project

TPS,FPS,W,H,SR=base.TPS,base.FPS,base.W,base.H,base.SR


def held_frames(frames, at, count):
    """Author's frame-list oracle, independent of graph clock implementation."""
    before=list(frames[:at])
    picture=frames[max(0,at-1)]
    return np.stack([*before,*([picture]*count),*frames[at:]])


class NestedFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=base.raw_source
        with patch.object(base,'raw_source',side_effect=lambda p:raw(p,step=47)):
            base.SourceTransitionCliTests.setUpClass.__func__(cls)
        cls.font=cls.basepath/'font.ttf'
        cls.font.write_bytes(ImageFont.load_default(size=16).path.getvalue())

    @classmethod
    def tearDownClass(cls):base.SourceTransitionCliTests.tearDownClass.__func__(cls)
    setUp=base.SourceTransitionCliTests.setUp
    p=base.SourceTransitionCliTests.p
    render=base.SourceTransitionCliTests.render

    def setup_parent(self, *, at=TPS, hold=TPS, source_in=0, source_out=3*TPS,
                     speed=1, reverse=False, audio_mode='silence', start=0, **fields):
        p=self.p()
        child={'id':'nf_child','name':'native child','canvas':{'width':W,'height':H},'duration_tick':3*TPS,'tracks':[]}
        for kind,aid in (('video','source'),('audio','sound')):
            child['tracks'].append({'id':'nf_'+kind,'kind':kind,'order':0,'clips':[
                {'id':'nf_leaf_'+kind,'asset_id':aid,'timeline_start_tick':0,'duration_tick':3*TPS,
                 'source_in_tick':TPS,'source_out_tick':4*TPS}]})
        duration=round((source_out-source_in)/speed)+hold
        container={'id':'nf_container','sequence_id':'nf_child','timeline_start_tick':start,
                   'duration_tick':duration,'source_in_tick':source_in,'source_out_tick':source_out,
                   'speed':speed,'reverse':reverse,
                   'freeze':{'at_tick':at,'duration_tick':hold,'audio_mode':audio_mode},**fields}
        parent={'id':self.sequence_id,'name':'frozen parent','duration_tick':start+container['duration_tick'],'tracks':[
            {'id':'nf_parent_track','kind':'video','order':0,'clips':[container]}]}
        p['sequences']=[parent,child]
        save_project(self.root,p)
        return p,parent,child,container

    def pixels(self,actual,expected,tolerance=3):
        self.assertEqual(actual.shape,expected.shape)
        self.assertLessEqual(float(np.abs(actual.astype(float)-expected).max()),tolerance)

    def manifest(self,result):
        return json.loads(Path(result['data']['manifest']).read_bytes())

    def test_middle_freeze_has_exact_frame_identity_before_during_after(self):
        p,_,_,_=self.setup_parent()
        original=copy.deepcopy(p)
        rgb,pcm,result=self.render('middle')
        self.pixels(rgb,held_frames(self.source_rgb[10:40],10,10))
        source=self.source_pcm[SR:4*SR]
        expected=np.concatenate([source[:SR],np.zeros((SR,2)),source[SR:]])
        self.assertEqual(pcm.shape,expected.shape)
        self.assertLessEqual(float(np.abs(pcm-expected).max()),2e-6)
        after=self.p()
        for key in ('sequences','assets','settings'):self.assertEqual(after[key],original[key])
        manifest=self.manifest(result)
        surfaces=[m for m in manifest['inputs'] if m.get('purpose')=='nested-sequence-freeze']
        self.assertEqual(len(surfaces),1)
        self.assertEqual(surfaces[0]['authored_timing']['freeze']['at_tick'],TPS)
        self.assertEqual(surfaces[0]['intermediate_files'],0)
        self.assertFalse(any(w.get('feature') in {'nested_sequence_freeze_clock','subtitle_freeze_clock'} for w in manifest['warnings']))

    def test_start_freeze_uses_first_picture_and_silence_then_entire_source(self):
        self.setup_parent(at=0)
        rgb,pcm,_=self.render('head')
        self.pixels(rgb,held_frames(self.source_rgb[10:40],0,10))
        expected=np.concatenate([np.zeros((SR,2)),self.source_pcm[SR:4*SR]])
        self.assertLessEqual(float(np.abs(pcm-expected).max()),2e-6)

    def test_tail_freeze_keeps_last_picture_and_has_silent_tail(self):
        self.setup_parent(at=3*TPS)
        rgb,pcm,_=self.render('tail')
        self.pixels(rgb,held_frames(self.source_rgb[10:40],30,10))
        self.assertLessEqual(float(np.abs(pcm[:3*SR]-self.source_pcm[SR:4*SR]).max()),2e-6)
        self.assertEqual(float(np.abs(pcm[3*SR:]).max()),0)

    def test_continue_audio_runs_through_picture_pause_and_pads_tail(self):
        self.setup_parent(audio_mode='continue')
        rgb,pcm,_=self.render('continue')
        self.pixels(rgb,held_frames(self.source_rgb[10:40],10,10))
        expected=np.concatenate([self.source_pcm[SR:4*SR],np.zeros((SR,2))])
        self.assertLessEqual(float(np.abs(pcm-expected).max()),2e-6)

    def test_trim_and_reverse_happen_before_freeze(self):
        self.setup_parent(source_in=TPS//2,source_out=5*TPS//2,reverse=True,at=TPS//2)
        rgb,pcm,_=self.render('reverse')
        self.pixels(rgb,held_frames(self.source_rgb[15:35][::-1],5,10))
        source=self.source_pcm[SR+SR//2:3*SR+SR//2][::-1]
        expected=np.concatenate([source[:SR//2],np.zeros((SR,2)),source[SR//2:]])
        self.assertLessEqual(float(np.abs(pcm-expected).max()),2e-6)

    def test_nonzero_parent_placement_does_not_change_local_hold(self):
        self.setup_parent(start=TPS//2)
        rgb,pcm,_=self.render('placed')
        self.assertEqual(float(np.abs(rgb[:5]).max()),0)
        self.pixels(rgb[5:],held_frames(self.source_rgb[10:40],10,10))
        self.assertEqual(float(np.abs(pcm[:SR//2]).max()),0)
        self.assertEqual(len(pcm),round(4.5*SR))

    def test_constant_speed_freeze_samples_complete_child_before_pause(self):
        self.setup_parent(speed=2,at=TPS//2)
        rgb,pcm,_=self.render('fast')
        self.pixels(rgb,held_frames(self.source_rgb[10:40:2],5,10))
        self.assertEqual(len(pcm),int(2.5*SR))
        self.assertEqual(float(np.abs(pcm[SR//2:3*SR//2]).max()),0)

    def test_child_bus_gain_is_processed_before_pause_parent_gain_after(self):
        p,_,child,container=self.setup_parent()
        child['tracks'][1]['audio']={'volume':.7}
        child['tracks'][1]['clips'][0]['audio']={'volume':.4}
        container['keyframes']=[{'property':'audio.volume','keyframes':[
            {'at_tick':0,'value':.25,'interpolation':'linear'}, {'at_tick':4*TPS,'value':1.0,'interpolation':'linear'}]}]
        save_project(self.root,p)
        _,pcm,_=self.render('buses')
        source=self.source_pcm[SR:4*SR]*np.float32(.4)*np.float32(.7)
        expected=np.concatenate([source[:SR],np.zeros((SR,2)),source[SR:]])
        expected*=np.minimum(1,.25+np.arange(4*SR)/SR*.75/4)[:,None]
        self.assertLessEqual(float(np.abs(pcm-expected).max()),2e-6)

    def test_repeated_child_freezes_are_independent_and_no_pad_is_consumed_twice(self):
        p,parent,_,container=self.setup_parent()
        second=copy.deepcopy(container);second.update(id='nf_other',timeline_start_tick=4*TPS)
        second['freeze']['at_tick']=2*TPS
        parent['duration_tick']=8*TPS;parent['tracks'][0]['clips'].append(second)
        save_project(self.root,p)
        rgb,_,result=self.render('repeat')
        expected=np.concatenate([held_frames(self.source_rgb[10:40],10,10),held_frames(self.source_rgb[10:40],20,10)])
        self.pixels(rgb,expected)
        surfaces=[m for m in self.manifest(result)['inputs'] if m.get('purpose')=='nested-sequence-freeze']
        self.assertEqual(len({m['asset_id'] for m in surfaces}),2)

    def test_outer_reverse_retimes_the_complete_frozen_picture(self):
        p,parent,_,_=self.setup_parent()
        parent['id']='nf_middle'
        p['sequences'].insert(0,{'id':self.sequence_id,'name':'outer reverse','duration_tick':4*TPS,'tracks':[
            {'id':'nf_outer','kind':'video','order':0,'clips':[{'id':'nf_outer_clip','sequence_id':'nf_middle',
             'timeline_start_tick':0,'duration_tick':4*TPS,'source_in_tick':0,'source_out_tick':4*TPS,'reverse':True}]}]})
        save_project(self.root,p)
        rgb,_,_=self.render('outer-reverse')
        self.pixels(rgb,held_frames(self.source_rgb[10:40],10,10)[::-1])

    def test_double_freeze_pauses_an_already_frozen_child(self):
        p,parent,_,_=self.setup_parent()
        parent['id']='nf_middle'
        p['sequences'].insert(0,{'id':self.sequence_id,'name':'outer freeze','duration_tick':5*TPS,'tracks':[
            {'id':'nf_outer','kind':'video','order':0,'clips':[{'id':'nf_outer_clip','sequence_id':'nf_middle',
             'timeline_start_tick':0,'duration_tick':5*TPS,'source_in_tick':0,'source_out_tick':4*TPS,
             'freeze':{'at_tick':int(2.5*TPS),'duration_tick':TPS,'audio_mode':'silence'}}]}]})
        save_project(self.root,p)
        rgb,pcm,_=self.render('double')
        self.pixels(rgb,held_frames(held_frames(self.source_rgb[10:40],10,10),25,10))
        self.assertEqual(float(np.abs(pcm[int(2.5*SR):int(3.5*SR)]).max()),0)

    def test_window_inside_freeze_then_resume_preserves_complete_author_clock(self):
        p,parent,_,_=self.setup_parent()
        candidate,_=apply_operation(p,self.sequence_id,{'op':'trim_clip','clip_id':'nf_container',
            'start_tick':int(1.5*TPS),'end_tick':int(3.5*TPS),'timeline_start_tick':0})
        candidate['sequences'][0]['duration_tick']=2*TPS
        save_project(self.root,candidate)
        rgb,pcm,_=self.render('window')
        self.pixels(rgb,held_frames(self.source_rgb[10:40],10,10)[15:35])
        source=self.source_pcm[SR:4*SR]
        expected=np.concatenate([np.zeros((SR//2,2)),source[SR:int(2.5*SR)]])
        self.assertLessEqual(float(np.abs(pcm-expected).max()),2e-6)

    def test_child_transition_midpoint_is_held_then_progress_resumes(self):
        p=self.p();child=copy.deepcopy(p['sequences'][0]);child['id']='nf_child'
        p['sequences']=[child]
        p,_=base.build_plan(p,'nf_child',base.add())
        container={'id':'nf_container','sequence_id':'nf_child','timeline_start_tick':0,'duration_tick':7*TPS,
            'source_in_tick':0,'source_out_tick':6*TPS,'freeze':{'at_tick':2*TPS,'duration_tick':TPS,'audio_mode':'silence'}}
        p['sequences'].insert(0,{'id':self.sequence_id,'name':'frozen transition','duration_tick':7*TPS,'tracks':[
            {'id':'nf_parent','kind':'video','order':0,'clips':[container]}]})
        save_project(self.root,p)
        rgb,pcm,_=self.render('transition')
        reference=np.concatenate([self.source_rgb[20:40]]*3).astype(float)
        for k in range(15,25):
            reference[k]=(1-(k-15)/10)*self.source_rgb[20+k]+((k-15)/10)*self.source_rgb[k]
        self.pixels(rgb,held_frames(reference,20,10))
        self.assertEqual(float(np.abs(pcm[2*SR:3*SR]).max()),0)

    def test_planning_rejects_projection_quota_without_mutating_authorship(self):
        p,seq,_,_=self.setup_parent()
        p['settings']['sequence_sampling']={'method':'bilinear','max_working_bytes':100000}
        before=copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:build_filter_graph(self.root,p,seq)
        self.assertIn(caught.exception.code,{'SEQUENCE_INLINE_BUDGET_EXCEEDED','SEQUENCE_PROJECTION_BUDGET_EXCEEDED'})
        self.assertEqual(p,before)

    def test_invalid_freeze_and_cycle_remain_rejected(self):
        p,_,child,container=self.setup_parent(at=4*TPS)
        self.assertIn('FREEZE_AT_INVALID',{e['code'] for e in validate_project(self.root,p)['errors']})
        child['tracks'][0]['clips'].append({'id':'loop','sequence_id':self.sequence_id})
        with self.assertRaises(AppError) as caught:transition_descendants(p,self.sequence_id)
        self.assertEqual(caught.exception.code,'SEQUENCE_CYCLE')

    def test_video_only_planning_does_not_leave_unconsumed_audio_branches(self):
        p,seq,_,_=self.setup_parent()
        before=copy.deepcopy(p)
        _,graph,metadata,_=build_filter_graph(self.root,p,seq,_video_only=True)
        self.assertEqual(p,before)
        self.assertTrue(any(m.get('purpose')=='nested-sequence-freeze' for m in metadata))
        # The actual graph is also consumed by another compound in the outer
        # reverse and double-freeze encoded-output tests above.
        self.assertIn('anullsink',graph)

    def test_smooth_speed_curve_uses_integrated_frame_clock_before_hold(self):
        duration=round(1.5*math.log(3)*TPS)
        curve={'keyframes':[{'at_tick':0,'speed':1,'interpolation':'linear'},
                            {'at_tick':3*TPS,'speed':3,'interpolation':'linear'}]}
        p,_,_,_=self.setup_parent(at=7*TPS//10,duration_tick=duration+TPS,speed_curve=curve)
        rgb,pcm,_=self.render('curve')
        times=np.arange(math.ceil(duration/TPS*FPS))/FPS
        # Independent inverse of integral dx/(1+2*x/3).
        indices=np.floor(1.5*np.expm1(times/1.5)*FPS+1e-8).astype(int).clip(0,29)
        self.pixels(rgb,held_frames(self.source_rgb[10+indices],7,10))
        self.assertEqual(len(pcm),math.ceil((duration+TPS)*SR/TPS))

    def test_outer_curve_maps_the_complete_frozen_child(self):
        p,parent,_,_=self.setup_parent()
        parent['id']='nf_middle'
        duration=round(4*math.log(2)*TPS)
        p['sequences'].insert(0,{'id':self.sequence_id,'name':'outer curve','duration_tick':duration,'tracks':[
            {'id':'nf_outer','kind':'video','order':0,'clips':[{'id':'nf_outer_clip','sequence_id':'nf_middle',
             'timeline_start_tick':0,'duration_tick':duration,'source_in_tick':0,'source_out_tick':4*TPS,
             'speed_curve':{'keyframes':[{'at_tick':0,'speed':1,'interpolation':'linear'},
                                        {'at_tick':4*TPS,'speed':2,'interpolation':'linear'}]}}]}]})
        save_project(self.root,p)
        rgb,_,_=self.render('outer-curve')
        times=np.arange(math.ceil(duration/TPS*FPS))/FPS
        indices=np.floor(4*np.expm1(times/4)*FPS+1e-8).astype(int).clip(0,39)
        self.pixels(rgb,held_frames(self.source_rgb[10:40],10,10)[indices])

    def test_child_caption_and_animation_pause_with_complete_picture(self):
        code,result=base.invoke('media','ingest','--project',str(self.root),'--input',str(self.font),'--asset-id','nf_font')
        self.assertEqual(code,0,result)
        p,_,child,_=self.setup_parent()
        child['tracks'][0]['clips'][0]['keyframes']=[{'property':'transform.position.x','keyframes':[
            {'at_tick':0,'value':.5,'interpolation':'linear'}, {'at_tick':3*TPS,'value':.7,'interpolation':'linear'}]}]
        child['tracks'].append({'id':'nf_captions','kind':'subtitle','order':2,'clips':[
            {'id':'nf_text','generator':{'type':'text'},'timeline_start_tick':0,'duration_tick':3*TPS,'source_in_tick':0,'source_out_tick':3*TPS,
             'subtitle':{'text':'AA BB','style':{'font_asset_id':'nf_font','fontsize':12,'x':'4','y':'6','box':False,
                                               'active_color':'yellow'},
                         'word_timing':[{'text':'AA','start':0.,'end':1.5},{'text':'BB','start':1.5,'end':3.}]}}]})
        reference=copy.deepcopy(p);reference['sequences']=[copy.deepcopy(child)]
        reference['sequences'][0]['id']=self.sequence_id
        save_project(self.root,reference)
        child_rgb,_,_=self.render('child-reference')
        save_project(self.root,p)
        rgb,_,_=self.render('caption')
        # Same-renderer glyph/animation reference: this checks hold/resume of
        # the complete child, not an independent text layout or shaping engine.
        self.pixels(rgb,held_frames(child_rgb,10,10))

    def test_parent_animation_keeps_moving_while_child_picture_is_held(self):
        p,_,_,container=self.setup_parent(transform={'scale':.5})
        container['keyframes']=[{'property':'transform.position.x','keyframes':[
            {'at_tick':0,'value':.3,'interpolation':'linear'}, {'at_tick':4*TPS,'value':.7,'interpolation':'linear'}]}]
        save_project(self.root,p)
        rgb,_,_=self.render('moving-parent')
        centroids=[]
        for frame in (11,18):
            mask=np.max(rgb[frame],axis=2)>5
            ys,xs=np.nonzero(mask)
            self.assertGreater(len(xs),0)
            expected_center=W*(.3+.4*(frame/FPS)/4)-.5
            self.assertLessEqual(abs(float(xs.mean())-expected_center),1)
            self.assertLessEqual(abs((xs.max()-xs.min()+1)-W/2),2)
            centroids.append(float(xs.mean()))
        self.assertGreater(centroids[1]-centroids[0],3)

    def test_transparent_native_child_hold_preserves_every_alpha_pixel(self):
        values=np.zeros((30,H,W,4),dtype='uint8')
        values[:,:,:,:3]=self.source_rgb[10:40]
        values[:,:,:,3]=np.broadcast_to(np.array([0,64,128,255],dtype='uint8')[np.arange(W)//(W//4)],(30,H,W))
        source=Path(self.temp.name)/'alpha.nut'
        subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',f'{W}x{H}',
            '-r',str(FPS),'-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',str(source)],
            input=values.tobytes(),check=True,capture_output=True)
        code,result=base.invoke('media','ingest','--project',str(self.root),'--input',str(source),'--asset-id','nf_alpha')
        self.assertEqual(code,0,result)
        p,seq,child,_=self.setup_parent()
        child['tracks'][0]['clips'][0].update(asset_id='nf_alpha',source_in_tick=0,source_out_tick=3*TPS)
        p['settings'].setdefault('output',{}).setdefault('video',{})['pixel_format']='yuva420p'
        inputs,graph,_,_=build_filter_graph(self.root,p,seq)
        output=Path(self.temp.name)/'alpha-result.nut'
        r=subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',graph,'-map','[vout]',
            '-map','[aout]','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',str(output)],capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr.decode('utf-8','replace'))
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1'])
        actual=np.frombuffer(raw,dtype='uint8').reshape(-1,H,W,4)
        expected=held_frames(values,10,10)
        np.testing.assert_array_equal(actual[:,:,:,3],expected[:,:,:,3])

    def test_non_frame_hold_duration_reports_quantization(self):
        self.setup_parent(hold=TPS//4)
        rgb,pcm,result=self.render('quantized')
        self.assertEqual(len(rgb),math.ceil(3.25*FPS))
        self.assertEqual(len(pcm),int(3.25*SR))
        self.assertTrue(any(w.get('code')=='FREEZE_FRAME_QUANTIZED' for w in self.manifest(result)['warnings']))

    def test_fractional_root_duration_keeps_last_half_open_display_frame(self):
        p,parent,_,container=self.setup_parent()
        container.pop('freeze');container['duration_tick']=3*TPS
        parent['duration_tick']=3*TPS+TPS//20
        save_project(self.root,p)
        rgb,pcm,_=self.render('fractional-root')
        self.assertEqual(len(rgb),31)
        self.pixels(rgb[:30],self.source_rgb[10:40])
        self.assertEqual(int(rgb[-1].max()),0)
        self.assertEqual(len(pcm),int(3.05*SR))

    def test_independent_child_canvas_projects_complete_hold_once(self):
        p,_,child,container=self.setup_parent(transform={'scale':.5})
        child['canvas']={'width':W//2,'height':H//2}
        save_project(self.root,p)
        rgb,_,_=self.render('native-child')
        expected=np.zeros((40,H,W,3),dtype='uint8')
        values=held_frames(self.source_rgb[10:40],10,10)[:,0,0,:]
        expected[:,H//4:3*H//4,W//4:3*W//4,:]=values[:,None,None,:]
        self.pixels(rgb,expected)

    def test_inline_retime_rejects_file_engine_before_fake_source_path(self):
        p,seq,_,_=self.setup_parent(speed=2,at=TPS//2)
        # Protocol boundary only: no actual R3 invocation is claimed here.
        with patch('ai_ad_editor.render._audio_stretch_configuration',return_value={'engine':'file-only'}):
            with self.assertRaises(AppError) as caught:build_filter_graph(self.root,p,seq)
        self.assertEqual(caught.exception.code,'CLIP_WINDOW_INLINE_R3_UNSUPPORTED')

    def test_frozen_and_normal_transition_uses_share_no_external_pads(self):
        p=self.p();child=copy.deepcopy(p['sequences'][0]);child['id']='nf_child'
        p['sequences']=[child];p,_=base.build_plan(p,'nf_child',base.add())
        frozen={'id':'nf_frozen','sequence_id':'nf_child','timeline_start_tick':0,'duration_tick':7*TPS,
            'source_in_tick':0,'source_out_tick':6*TPS,'freeze':{'at_tick':2*TPS,'duration_tick':TPS,'audio_mode':'silence'}}
        normal={'id':'nf_normal','sequence_id':'nf_child','timeline_start_tick':7*TPS,'duration_tick':6*TPS,
                'source_in_tick':0,'source_out_tick':6*TPS}
        p['sequences'].insert(0,{'id':self.sequence_id,'name':'shared child','duration_tick':13*TPS,'tracks':[
            {'id':'nf_parent','kind':'video','order':0,'clips':[frozen,normal]}]})
        save_project(self.root,p)
        rgb,_,_=self.render('mixed')
        reference=np.concatenate([self.source_rgb[20:40]]*3).astype(float)
        for k in range(15,25):reference[k]=(1-(k-15)/10)*self.source_rgb[20+k]+((k-15)/10)*self.source_rgb[k]
        self.pixels(rgb,np.concatenate([held_frames(reference,20,10),reference]))


if __name__=='__main__':unittest.main()
