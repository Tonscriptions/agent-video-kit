"""Camera coverage must preserve the independently established event clock."""
from __future__ import annotations
from array import array
import copy
import json
import math
import random
import unittest
from unittest.mock import patch
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.multicam import build_switch_segments
from ai_ad_editor.project import load_project, save_project
from ai_ad_editor.render import build_filter_graph
import test_cfr_boundaries as helpers
from test_magnetic_reorder import invoke


def sync(delay,duration):
    return {'reference_asset_id':'reference','sources':[{'asset_id':'reference'},{'asset_id':'camera'}],
        'offsets':[{'asset_id':'reference','relative_delay_seconds':0.,'evidence':{'duration_seconds':3.}},
            {'asset_id':'camera','relative_delay_seconds':delay,'evidence':{'duration_seconds':duration}}]}


class MulticamCoverageTests(unittest.TestCase):
    def plan(self,delay,duration,left,right,**options):
        return build_switch_segments(sync(delay,duration),start_seconds=0.,end_seconds=3.,
            switch_plan=[{'start_seconds':left,'end_seconds':right,'camera_asset_id':'camera'}],**options)

    def test_default_refuses_a_camera_that_begins_after_the_requested_event(self):
        with self.assertRaises(AppError):self.plan(-.4,2.,0.,1.)

    def test_default_refuses_a_camera_that_ends_before_the_requested_event(self):
        with self.assertRaises(AppError):self.plan(.2,1.,.5,1.2)

    def test_fully_covered_source_keeps_the_original_event_mapping(self):
        rows,_=self.plan(.2,3.,.5,1.2)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_in_seconds'],.7)
        self.assertEqual(rows[0]['source_out_seconds'],1.4)
        self.assertEqual(rows[0]['speed'],1.)
        self.assertEqual(rows[0]['timeline_start_seconds'],.5)
        self.assertEqual(rows[0]['duration_seconds'],.7)

    def test_trim_leading_gap_moves_the_clip_without_changing_speed(self):
        rows,warnings=self.plan(-.4,2.,0.,1.,source_shortfall='trim')
        row=rows[0]
        self.assertEqual((row['timeline_start_seconds'],row['duration_seconds']),(.4,.6))
        self.assertEqual((row['source_in_seconds'],row['source_out_seconds'],row['speed']),(0.,.6,1.))
        self.assertEqual((row['requested_start_seconds'],row['requested_end_seconds']),(0.,1.))
        self.assertEqual(row['source_coverage'],'trimmed')
        self.assertIn('MULTICAM_SOURCE_TRIMMED',[v['code'] for v in warnings])

    def test_trim_trailing_gap_retains_reference_event_position(self):
        rows,_=self.plan(.2,1.,.5,1.2,source_shortfall='trim')
        row=rows[0]
        self.assertEqual((row['start_seconds'],row['end_seconds']),(.5,.8))
        self.assertEqual((row['source_in_seconds'],row['source_out_seconds'],row['speed']),(.7,1.,1.))
        self.assertEqual(row['duration_seconds'],.3)

    def test_trim_both_edges_keeps_the_complete_short_camera_at_unity(self):
        rows,_=self.plan(-.4,1.44,0.,2.,source_shortfall='trim')
        self.assertEqual((rows[0]['start_seconds'],rows[0]['end_seconds'],rows[0]['speed']),(.4,1.84,1.))

    def test_trim_places_intersection_relative_to_nonzero_requested_start(self):
        rows,_=build_switch_segments(sync(-.4,1.44),start_seconds=.2,end_seconds=2.,timeline_start_seconds=5.,
            source_shortfall='trim',switch_plan=[{'start_seconds':.2,'end_seconds':2.,'camera_asset_id':'camera'}])
        self.assertEqual(rows[0]['timeline_start_seconds'],5.2)
        self.assertEqual(rows[0]['duration_seconds'],1.44)

    def test_disjoint_prefix_is_refused_by_every_policy(self):
        for policy in ('reject','trim','stretch'):
            with self.subTest(policy=policy),self.assertRaises(AppError) as caught:
                self.plan(-1.,1.,0.,.5,source_shortfall=policy)
            self.assertEqual(caught.exception.code,'MULTICAM_SOURCE_RANGE_EMPTY')

    def test_disjoint_tail_is_refused_by_every_policy(self):
        for policy in ('reject','trim','stretch'):
            with self.subTest(policy=policy),self.assertRaises(AppError) as caught:
                self.plan(.2,1.,1.,1.5,source_shortfall=policy)
            self.assertEqual(caught.exception.code,'MULTICAM_SOURCE_RANGE_EMPTY')

    def test_explicit_stretch_warns_even_when_prefix_clamping_keeps_speed_one(self):
        rows,warnings=self.plan(-.4,2.,0.,1.,source_shortfall='stretch')
        self.assertEqual((rows[0]['timeline_start_seconds'],rows[0]['duration_seconds'],rows[0]['speed']),(0.,1.,1.))
        self.assertEqual(rows[0]['source_coverage'],'stretched')
        self.assertIn('MULTICAM_SOURCE_CLOCK_CHANGED',[v['code'] for v in warnings])

    def test_explicit_stretch_retains_the_legacy_tail_fill_only_by_request(self):
        rows,warnings=self.plan(.2,1.,.5,1.2,source_shortfall='stretch')
        self.assertEqual((rows[0]['source_in_seconds'],rows[0]['source_out_seconds'],rows[0]['duration_seconds']),(.7,1.,.7))
        self.assertAlmostEqual(rows[0]['speed'],3/7,places=6)
        self.assertIn('MULTICAM_SOURCE_SLOWED',[v['code'] for v in warnings])

    def test_unknown_shortfall_policy_is_rejected(self):
        with self.assertRaises(AppError):self.plan(0.,3.,0.,1.,source_shortfall='pad')

    def test_trim_does_not_hide_overlapping_requested_events(self):
        with self.assertRaises(AppError):
            build_switch_segments(sync(-.4,.4),start_seconds=0.,end_seconds=3.,source_shortfall='trim',
                switch_plan=[{'start_seconds':0.,'end_seconds':2.,'camera_asset_id':'camera'},
                             {'start_seconds':1.,'end_seconds':2.5,'camera_asset_id':'reference'}])

    def test_float_boundary_noise_does_not_create_a_false_shortfall(self):
        rows,warnings=self.plan(-.1-.2,1.,.3,1.3)
        self.assertEqual((rows[0]['source_in_seconds'],rows[0]['source_out_seconds'],rows[0]['speed']),(0.,1.,1.))
        self.assertNotIn('MULTICAM_SOURCE_CLOCK_CHANGED',[v['code'] for v in warnings])

    def test_source_sync_report_is_not_mutated_by_success_or_refusal(self):
        report=sync(-.4,1.44);before=copy.deepcopy(report)
        options={'switch_plan':[{'start_seconds':0.,'end_seconds':2.,'camera_asset_id':'camera'}], 'end_seconds':2.}
        with self.assertRaises(AppError):build_switch_segments(report,**options)
        self.assertEqual(report,before)
        build_switch_segments(report,source_shortfall='trim',**options)
        self.assertEqual(report,before)


class NativeMulticamCoverageTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp
    run_native=helpers.CFRBoundaryTests.run_native
    source=helpers.CFRBoundaryTests.source
    project=helpers.CFRBoundaryTests.project
    render=helpers.CFRBoundaryTests.render

    def pair(self):
        source,colors,_=self.source(count=50)
        rng=random.Random(61243)
        gains=[.1+.75*rng.random() for _ in range(100)]
        pcm=array('f')
        for sample in range(96000):
            gain=gains[sample//960]
            pcm.extend((gain*math.sin(2*math.pi*433*sample/48000),gain*math.sin(2*math.pi*739*sample/48000)))
        audio=self.work/'reference.f32le';audio.write_bytes(pcm.tobytes())
        reference=self.work/'reference.mkv'
        self.run_native([ffmpeg_path(),'-v','error','-i',source,'-f','f32le','-ar','48000','-ac','2','-i',audio,
            '-map','0:v','-map','1:a','-c:v','copy','-c:a','pcm_f32le',reference])
        candidate=self.work/'candidate.mkv'
        self.run_native([ffmpeg_path(),'-v','error','-i',reference,'-filter_complex',
            '[0:v]trim=start_frame=10:end_frame=46,setpts=PTS-STARTPTS[v];[0:a]atrim=start_sample=19200:end_sample=88320,asetpts=PTS-STARTPTS[a]',
            '-map','[v]','-map','[a]','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',candidate])
        p,seq,clip=self.project(reference,rate='25',start=0,duration=180000,source_out=180000)
        reference_id=clip['asset_id']
        code,ingest=invoke('media','ingest','--project',self.root,'--input',candidate)
        self.assertEqual(code,0,ingest)
        p=load_project(self.root)[1];seq=p['sequences'][0];seq['duration_tick']=180000
        seq['tracks'][0]['clips']=[]
        audio_track=next(track for track in seq['tracks'] if track['kind']=='audio')
        audio_track['clips']=[{'id':'master_audio','asset_id':reference_id,'timeline_start_tick':0,'duration_tick':180000,'source_in_tick':0,'source_out_tick':180000}]
        save_project(self.root,p)
        plan=self.root/'candidate-plan.json'
        plan.write_text(json.dumps([{'start_seconds':0.,'end_seconds':2.,'camera_asset_id':ingest['data']['asset']['id']}]),encoding='utf8')
        common=('media','multicam','--project',self.root,'--source-asset-id',reference_id,
            '--source-asset-id',ingest['data']['asset']['id'],'--reference-asset-id',reference_id,
            '--sample-rate','8000','--analysis-seconds','2','--max-offset-seconds','.6',
            '--switch-plan',plan,'--start-seconds','0','--end-seconds','2','--track-id',seq['tracks'][0]['id'],
            '--output',self.root/'validation/coverage.json')
        return common,colors,pcm.tobytes(),plan

    def test_default_native_refusal_preserves_project_and_does_not_write_report_or_snapshot(self):
        common,_,_,_=self.pair()
        before=(self.root/'project.json').read_bytes()
        snapshots=list((self.root/'history').glob('*.json'))
        for options in (('--dry-run',),('--apply','--replace-track')):
            code,result=invoke(*common,*options)
            self.assertEqual(code,2,result)
            self.assertEqual(result['errors'][0]['code'],'MULTICAM_SOURCE_SHORTFALL')
            self.assertEqual((self.root/'project.json').read_bytes(),before)
            self.assertFalse((self.root/'validation/coverage.json').exists())
            self.assertEqual(list((self.root/'history').glob('*.json')),snapshots)

    def test_native_trim_preserves_every_event_frame_both_gaps_and_explicit_master_pcm(self):
        common,colors,pcm,_=self.pair()
        code,result=invoke(*common,'--source-shortfall','trim','--apply','--replace-track')
        self.assertEqual(code,0,result)
        row=result['data']['plan']['segments'][0]
        self.assertEqual((row['timeline_start_tick'],row['duration_tick'],row['source_in_tick'],row['source_out_tick']),(36000,129600,0,129600))
        self.assertEqual(row['speed'],1.)
        p=load_project(self.root)[1];seq=p['sequences'][0]
        self.assertEqual(seq['duration_tick'],180000)
        frames,_,_=self.render(p,seq)
        expected=[(0,0,0,255)]*10+colors[10:46]+[(0,0,0,255)]*4
        self.assertEqual(len(frames),len(expected))
        self.assertEqual(frames,[bytes(color)*(helpers.W*helpers.H) for color in expected])
        inputs,graph,_,_=build_filter_graph(self.root,p,seq)
        actual=self.run_native([ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,
            '-filter_complex',graph,'-map','[vout]','-f','null','-','-map','[aout]','-c:a','pcm_f32le','-ar','48000','-ac','2','-f','f32le','pipe:1'])
        self.assertEqual(actual,pcm)

    def test_trim_dry_run_reports_original_bounds_and_performs_no_write(self):
        common,_,_,_=self.pair();before=(self.root/'project.json').read_bytes()
        code,result=invoke(*common,'--source-shortfall','trim','--dry-run')
        self.assertEqual(code,0,result)
        row=result['data']['plan']['segments'][0]
        self.assertEqual((row['requested_start_seconds'],row['requested_end_seconds'],row['start_seconds'],row['end_seconds']),(0.,2.,.4,1.84))
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertFalse((self.root/'validation/coverage.json').exists())

    def test_locked_target_refuses_before_audio_analysis_even_in_apply_dry_run(self):
        common,_,_,_=self.pair();p=load_project(self.root)[1]
        p['sequences'][0]['tracks'][0]['locked']=True;save_project(self.root,p)
        before=(self.root/'project.json').read_bytes()
        with patch('ai_ad_editor.cli.synchronize_multicam_sources',side_effect=AssertionError('audio analysis must not run')):
            code,result=invoke(*common,'--source-shortfall','trim','--apply','--dry-run')
        self.assertEqual(code,2,result)
        self.assertEqual(result['errors'][0]['code'],'TRACK_LOCKED')
        self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_explicit_native_stretch_warns_and_visibly_replaces_the_first_gap(self):
        common,colors,_,_=self.pair()
        code,result=invoke(*common,'--source-shortfall','stretch','--apply','--replace-track')
        self.assertEqual(code,0,result)
        row=result['data']['plan']['segments'][0]
        self.assertEqual((row['timeline_start_tick'],row['duration_tick'],row['speed']),(0,180000,.72))
        self.assertIn('MULTICAM_SOURCE_CLOCK_CHANGED',[v['code'] for v in result['data']['plan']['warnings']])
        p=load_project(self.root)[1];frames,_,_=self.render(p,p['sequences'][0])
        self.assertEqual(frames[0],bytes(colors[10])*(helpers.W*helpers.H))

    def test_trim_preserves_an_existing_longer_authored_sequence(self):
        common,_,_,_=self.pair();p=load_project(self.root)[1]
        p['sequences'][0]['duration_tick']=270000;save_project(self.root,p)
        code,result=invoke(*common,'--source-shortfall','trim','--apply','--replace-track')
        self.assertEqual(code,0,result)
        self.assertEqual(load_project(self.root)[1]['sequences'][0]['duration_tick'],270000)

    def test_sub_tick_segment_refuses_instead_of_inventing_a_one_tick_clip(self):
        common,_,_,plan=self.pair();rows=json.loads(plan.read_bytes())
        rows[0].update(start_seconds=.5,end_seconds=.500001);plan.write_text(json.dumps(rows),encoding='utf8')
        before=(self.root/'project.json').read_bytes()
        code,result=invoke(*common,'--apply','--replace-track')
        self.assertEqual(code,2,result)
        self.assertEqual(result['errors'][0]['code'],'MULTICAM_SEGMENT_TOO_SHORT')
        self.assertEqual((self.root/'project.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
