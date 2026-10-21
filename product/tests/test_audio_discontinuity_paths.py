"""Actual R3, nonlinear/nested retiming and read-only multicam source clocks."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
from ai_ad_editor import audio_stretch
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.multicam import _extract_envelope,synchronize_multicam_sources
from ai_ad_editor.project import create_project,load_project,save_project
from ai_ad_editor.render import build_filter_graph
from test_audio_discontinuity import CASES,BLOCK,COUNT,RATE,TPS,fixture_sources,original_samples,native
from test_magnetic_reorder import invoke

def digest(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def oracle(name,*,repeats=1,tail=True):
    gap,overlap,_,_=CASES[name];source=np.tile(original_samples(),(repeats,1))
    length=round(.4*RATE) if tail and repeats==1 else len(source)+gap-overlap
    result=np.zeros((length,2),dtype='<f4')
    for i in range(COUNT*repeats):
        left=i*BLOCK+(gap if i>=5 else 0)-(overlap if i>=10 else 0)
        result[left:left+BLOCK]=source[i*BLOCK:(i+1)*BLOCK]
    return result


class NativeAudioPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        cls.shared=tempfile.TemporaryDirectory(prefix='native-audio-paths-',dir=base);cls.addClassCleanup(cls.shared.cleanup)
        cls.fixture=Path(cls.shared.name);manifest=os.environ.get('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES')
        data=json.loads(Path(manifest).read_bytes()) if manifest else fixture_sources(cls.fixture/'originals')
        cls.sources={name:Path(row['path']) for name,row in data['cases'].items()}
        for name,row in data['cases'].items():
            if digest(row['path'])!=row['sha256']:raise AssertionError((name,'original fixture SHA changed'))

    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='case-',dir=self.fixture);self.addCleanup(self.case.cleanup)
        self.work=Path(self.case.name);self.root=self.work/'project';create_project(self.root)

    def engine(self):
        executable=os.environ.get('AI_AD_EDITOR_TEST_RUBBERBAND')
        if not executable:self.skipTest('requires explicitly supplied existing native Rubber Band')
        executable=Path(executable);license=executable.with_name('COPYING.txt');dependency=executable.with_name('sndfile.dll')
        return audio_stretch.configuration(self.root,{'engine':'rubberband-r3-offline-v1','executable':str(executable),
            'sha256':digest(executable),'license_path':str(license),'license_sha256':digest(license),'license_spdx':'GPL-2.0-or-later',
            'dependencies':[{'path':str(dependency),'sha256':digest(dependency)}]})

    def R3(self,name,*,left=0.,right=.25):
        code,value=invoke('media','ingest','--project',self.root,'--input',self.sources[name]);self.assertEqual(code,0,value)
        asset=value['data']['asset'];job=audio_stretch.plan(self.root,self.engine(),asset,self.sources[name],left,right,[],(right-left)/2,False)
        real=audio_stretch.run_process;captured=self.work/'actual-R3-input.wav'
        def actual(command,**kwargs):
            result=real(command,**kwargs)
            if command[-1].endswith('input.wav') and result.returncode==0:captured.write_bytes(Path(command[-1]).read_bytes())
            return result
        scratch=self.work/'scratch';scratch.mkdir()
        with mock.patch.object(audio_stretch,'run_process',side_effect=actual):result=audio_stretch.execute(self.root,job,scratch)
        info=audio_stretch.inspect_pcm(captured)
        with captured.open('rb') as stream:stream.seek(info['data_offset']);raw=stream.read(info['data_bytes'])
        self.assertEqual(raw,oracle(name)[round(left*RATE):round(right*RATE)].tobytes())
        self.assertEqual(result['output_pcm']['frames'],round((right-left)*RATE/2))
        self.assertEqual(result['native_audio_clock']['stats']['soft_async_resampling'],False)
        return result

    def test_R3_consumes_the_exact_internal_gap_before_actual_offline_stretch(self):self.R3('gap')
    def test_R3_consumes_later_winning_overlap_samples_before_actual_offline_stretch(self):self.R3('overlap',right=.2)
    def test_R3_consumes_alternating_gap_and_overlap_before_actual_offline_stretch(self):self.R3('mixed')
    def test_R3_consumes_the_exact_single_sample_gap(self):self.R3('one-sample-gap')

    def test_R3_wholly_internal_gap_is_genuine_source_silence(self):
        result=self.R3('gap',left=.06,right=.09)
        self.assertEqual(result['input_pcm']['nonzero_samples'],[0,0]);self.assertEqual(result['output_pcm']['nonzero_samples'],[0,0])

    def test_R3_preserves_audio_EOF_silence_within_verified_video_coverage(self):
        result=self.R3('continuous',right=.4)
        self.assertEqual(result['source_clock_bound']['padding_samples'],9600)
        self.assertEqual(result['source_clock_bound']['policy'],'verified-native-audio-and-video-display-end')

    def test_R3_rejects_past_actual_video_and_audio_EOF(self):
        code,value=invoke('media','ingest','--project',self.root,'--input',self.sources['continuous']);self.assertEqual(code,0,value)
        job=audio_stretch.plan(self.root,self.engine(),value['data']['asset'],self.sources['continuous'],0,.5,[],.25,False)
        scratch=self.work/'scratch';scratch.mkdir()
        with self.assertRaises(AppError) as caught:audio_stretch.execute(self.root,job,scratch)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_SOURCE_LENGTH_MISMATCH');self.assertFalse(Path(job['output']).exists())

    def canonical_source(self,name):
        raw=self.work/(name+'-oracle.f32');raw.write_bytes(oracle(name).tobytes());target=self.work/(name+'-oracle.nut')
        native([ffmpeg_path(),'-v','error','-f','lavfi','-i','color=c=0x203040:size=32x18:rate=25:duration=0.4',
            '-f','f32le','-ar',RATE,'-ac','2','-i',raw,'-map','0:v:0','-map','1:a:0','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',target])
        return target

    def retimed(self,source,*,nested=False,reverse=False):
        root=self.work/('render-'+source.stem);create_project(root)
        code,value=invoke('media','ingest','--project',root,'--input',source);self.assertEqual(code,0,value)
        project=load_project(root)[1];project['settings']['canvas']={'width':32,'height':18,'background':'#000000'}
        project['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':25,'den':1}}
        duration=round(.25*math.log(3)/1.2*TPS)
        sound={'id':'sound','asset_id':value['data']['asset']['id'],'source_in_tick':0,'source_out_tick':round(.25*TPS),
            'timeline_start_tick':0,'duration_tick':duration,'reverse':reverse,
            'speed_curve':{'keyframes':[{'at_tick':0,'speed':.6},{'at_tick':round(.25*TPS),'speed':1.8}]}}
        sequence=project['sequences'][0];sequence['duration_tick']=duration
        sequence['tracks']=[{'id':'video','kind':'video','clips':[{'id':'picture','asset_id':sound['asset_id'],
            'source_in_tick':0,'source_out_tick':duration,'timeline_start_tick':0,'duration_tick':duration}]},
            {'id':'audio','kind':'audio','clips':[sound]}]
        if nested:
            child=copy.deepcopy(sequence);child['id']='child';child['tracks']=child['tracks'][1:];project['sequences'].append(child)
            outer=round(duration/1.25);sequence['duration_tick']=outer;sequence['tracks'][0]['clips'][0].update(source_out_tick=outer,duration_tick=outer)
            sequence['tracks'][1]['clips']=[{'id':'parent','sequence_id':'child','source_in_tick':0,'source_out_tick':duration,
                'timeline_start_tick':0,'duration_tick':outer,'speed':1.25}]
        save_project(root,project);inputs,graph,metadata,_=build_filter_graph(root,project,sequence,_persist_video_index=True)
        raw=native([ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,'-filter_complex',graph,
            '-map','[aout]','-f','f32le','-ac','2','pipe:1','-map','[vout]','-f','null','NUL'],cwd=root)
        self.assertTrue(any(row.get('native_audio_clock') for row in metadata));return raw

    def test_nonuniform_curve_matches_an_independently_placed_native_PCM_source(self):
        self.assertEqual(self.retimed(self.sources['mixed']),self.retimed(self.canonical_source('mixed')))

    def test_reversed_nonuniform_curve_matches_an_independently_placed_native_PCM_source(self):
        self.assertEqual(self.retimed(self.sources['gap'],reverse=True),self.retimed(self.canonical_source('gap'),reverse=True))

    def test_nested_retime_uses_the_same_discontinuous_source_clock(self):
        self.assertEqual(self.retimed(self.sources['mixed'],nested=True),self.retimed(self.canonical_source('mixed'),nested=True))

    def long_sources(self):
        raw=self.work/'long-original.f32';raw.write_bytes(np.tile(original_samples(),(5,1)).tobytes())
        expected=self.work/'long-oracle.f32';expected.write_bytes(oracle('mixed',repeats=5,tail=False).tobytes());paths=[]
        for name,source in (('long-discontinuous',raw),('long-oracle',expected)):
            target=self.work/(name+'.nut');command=[ffmpeg_path(),'-v','error','-f','lavfi','-i',
                'color=c=0x203040:size=32x18:rate=25:duration=1.2','-f','f32le','-ar',RATE,'-ac','2','-i',source]
            if name=='long-discontinuous':command+=['-af',"asetnsamples=n=480:p=0,asetpts='N+if(gte(N,2400),2400,0)-if(gte(N,4800),240,0)'"]
            command+=['-map','0:v:0','-map','1:a:0','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',target]
            native(command);paths.append(target)
        return paths

    def test_multicam_envelope_matches_independent_PCM_placement_without_project_writes(self):
        original,canonical=self.long_sources();before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        actual,meta=_extract_envelope(original,sample_rate=8000,max_seconds=1.,project_root=self.root)
        expected,_=_extract_envelope(canonical,sample_rate=8000,max_seconds=1.,project_root=self.root)
        self.assertEqual(actual.tobytes(),expected.tobytes());self.assertEqual(meta['sha256'],digest(original))
        self.assertTrue(meta['native_audio_clock']['ephemeral']);self.assertFalse(meta['native_audio_clock']['retained_after_analysis'])
        self.assertEqual({str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()},before)
        self.assertFalse(any(p.name.startswith('.audio-clock-transient-') for p in self.work.iterdir()))

    def test_multicam_sync_aligns_equal_author_clocks_despite_internal_gap_and_overlap(self):
        original,canonical=self.long_sources()
        result=synchronize_multicam_sources([{'asset_id':'reference','path':canonical},{'asset_id':'camera','path':original}],
            reference_asset_id='reference',analysis_seconds=1.,max_offset_seconds=.2)
        row=next(row for row in result['offsets'] if row['asset_id']=='camera')
        self.assertAlmostEqual(row['relative_delay_seconds'],0.,places=6);self.assertGreater(row['score'],.999)


if __name__=='__main__':unittest.main()
