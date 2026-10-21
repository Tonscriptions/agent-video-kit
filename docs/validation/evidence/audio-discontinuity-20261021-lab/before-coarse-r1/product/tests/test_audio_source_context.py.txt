"""Real native audio context, authored crops, clocks and failure boundaries."""
from __future__ import annotations

import array
import json
from pathlib import Path
from unittest import mock
import unittest

import test_audio_stretch as base
from ai_ad_editor.audio_stretch import configuration, execute, plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.utils import atomic_write_json


class AudioSourceContextTests(unittest.TestCase):
    setUp = base.OfflineAudioStretchTests.setUp
    call = base.OfflineAudioStretchTests.call
    prepare = base.OfflineAudioStretchTests.prepare
    render = base.OfflineAudioStretchTests.render
    setUpClass = classmethod(base.OfflineAudioStretchTests.setUpClass.__func__)
    tearDownClass = classmethod(base.OfflineAudioStretchTests.tearDownClass.__func__)

    def config(self):
        return {**base.OfflineAudioStretchTests.config(self), 'source_context_ms':64, 'channel_mode':'apart'}

    def test_real_context_preserves_four_ms_independent_tones(self):
        self.prepare(left=.201,right=.205,duration=.25)
        output,job,_=self.render()
        context=job['source_context'];execution=job['execution']
        self.assertEqual(context['source_head_frames'],3072)
        self.assertEqual(context['source_tail_frames'],3072)
        self.assertEqual(context['output_head_frames'],192000)
        self.assertEqual(context['output_crop'],[192000,204000])
        self.assertEqual(execution['input_pcm']['frames'],192)
        self.assertEqual(execution['context_input_pcm']['frames'],6336)
        self.assertEqual(execution['engine_raw_output_pcm']['frames'],396000)
        self.assertEqual(execution['output_pcm']['frames'],12000)
        values=base.decode(output)
        for channel,hz in enumerate((400,800)):
            samples=values[channel:24000:2]
            self.assertLessEqual(abs(base.peak_hz(samples,hz)-hz),5)
        left=values[:24000:2]
        def energy(hz):
            import math
            return sum(v*math.cos(2*math.pi*hz*i/48000) for i,v in enumerate(left))**2+sum(v*math.sin(2*math.pi*hz*i/48000) for i,v in enumerate(left))**2
        self.assertGreater(energy(400),10*energy(800))
        self.assertTrue(all(v==0 for v in values[24000:]))
        self.assertFalse(execution['stereo_phase_accepted'])
        self.assertFalse(execution['pitch_and_listening_accepted'])

    def test_nested_reverse_selects_context_before_sample_reversal(self):
        self.prepare(left=.201,right=.205,duration=.25,reverse=True,nested=True)
        output,job,_=self.render();actual=base.decode(output);derived=base.decode(job['output'])
        expected=array.array('f')
        for i in range(len(derived)-2,-1,-2):expected.extend(derived[i:i+2])
        self.assertEqual(actual[:len(expected)],expected)
        self.assertEqual(job['execution']['output_pcm']['frames'],12000)

    def test_context_clamps_to_real_source_edges_without_padding(self):
        for left,right,head,tail in [(0.,.004,0,3072),(2.996,3.,3072,0)]:
            with self.subTest(left=left):
                asset={'probe':{'audio':{'channels':2},'duration_seconds':3.},'sha256':base.digest(self.stereo)}
                engine=configuration(self.root,self.config())
                job=plan(self.root,engine,asset,self.stereo,left,right,[],.25,False)
                self.assertEqual(job['source_context']['source_head_frames'],head)
                self.assertEqual(job['source_context']['source_tail_frames'],tail)
                scratch=self.base/f'scratch-{left}';scratch.mkdir()
                result=execute(self.root,job,scratch)
                self.assertEqual(result['output_pcm']['frames'],12000)
                self.assertEqual(result['context_input_pcm']['frames'],192+head+tail)
                self.assertEqual(list(scratch.iterdir()),[])

    def test_non_linear_map_shifts_all_authored_anchors_and_crops_output(self):
        curve={'keyframes':[{'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},
                            {'at_tick':234000,'speed':2.8}]}
        self.prepare(left=.2,right=2.8,duration=1.5,nested=True,curve=curve)
        output,job,_=self.render();context=job['source_context']
        shift=(context['source_head_frames'],context['output_head_frames'])
        shifted=[[a+shift[0],b+shift[1]] for a,b in job['time_map']]
        self.assertEqual(context['time_map'][1:-1],shifted)
        self.assertGreater(len(job['execution']['engine_time_map']),10)
        self.assertEqual(job['execution']['output_pcm']['frames'],72000)
        self.assertEqual(context['output_crop'][1]-context['output_crop'][0],72000)
        self.assertTrue(all(a<b for (a,_),(b,__) in zip(context['time_map'],context['time_map'][1:])))
        self.assertTrue(all(a<b for (_,a),(__,b) in zip(context['time_map'],context['time_map'][1:])))
        self.assertTrue(all(abs(v)<10 for v in base.decode(output)))

    def test_invalid_context_values_reject_before_any_process(self):
        for value in (True,-1,1001,1.5,'64',None):
            with self.subTest(value=value),mock.patch('ai_ad_editor.audio_stretch.run_process') as process:
                with self.assertRaises(AppError) as error:configuration(self.root,{**self.config(),'source_context_ms':value})
                self.assertEqual(error.exception.code,'AUDIO_STRETCH_CONFIG_INVALID')
                process.assert_not_called()

    def test_extended_output_budget_rejects_before_decoding(self):
        asset={'probe':{'audio':{'channels':2},'duration_seconds':3.},'sha256':base.digest(self.stereo)}
        with mock.patch('ai_ad_editor.audio_stretch.run_process') as process:
            with self.assertRaises(AppError) as error:
                plan(self.root,configuration(self.root,self.config()),asset,self.stereo,.201,.205,[],100.,False)
            self.assertEqual(error.exception.code,'AUDIO_STRETCH_BUDGET_EXCEEDED')
            process.assert_not_called()

    def test_missing_source_duration_cannot_invent_context(self):
        asset={'probe':{'audio':{'channels':2}},'sha256':base.digest(self.stereo)}
        with self.assertRaises(AppError) as error:
            plan(self.root,configuration(self.root,self.config()),asset,self.stereo,.201,.205,[],.25,False)
        self.assertEqual(error.exception.code,'AUDIO_STRETCH_CONTEXT_BOUND_INVALID')

    def test_audio_shorter_than_probe_rejects_without_stretcher_or_cache(self):
        asset={'probe':{'audio':{'channels':2},'duration_seconds':4.},'sha256':base.digest(self.stereo)}
        job=plan(self.root,configuration(self.root,self.config()),asset,self.stereo,2.996,3.,[],.25,False)
        scratch=self.base/'short-source';scratch.mkdir()
        with self.assertRaises(AppError) as error:execute(self.root,job,scratch)
        self.assertEqual(error.exception.code,'AUDIO_STRETCH_SOURCE_LENGTH_MISMATCH')
        self.assertFalse(Path(job['output']).exists())
        self.assertEqual(list(scratch.iterdir()),[])

    def test_dry_run_exposes_context_without_decoding_or_cache(self):
        self.prepare(left=.201,right=.205,duration=.25)
        with mock.patch('ai_ad_editor.audio_stretch.run_process',side_effect=AssertionError('dry-run decoded audio')):
            value=self.call('render','--project',self.root,'--output',self.root/'renders/plan.mkv','--container','mkv','--dry-run')
        self.assertEqual(value['data']['status'],'planned')
        self.assertFalse((self.root/'cache/audio-stretch').exists())


if __name__=='__main__':unittest.main()
