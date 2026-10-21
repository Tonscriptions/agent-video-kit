"""Decoded source samples retain hard internal gaps, overlaps and author EOF windows."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor.project import create_project,load_project,save_project
from ai_ad_editor.render import build_filter_graph
from test_magnetic_reorder import invoke

RATE,TPS,BLOCK,COUNT=48000,90000,480,20
CASES={'gap':(2400,0,'nut',480),'overlap':(0,240,'nut',480),
    'mixed':(2400,240,'nut',480),'one-sample-gap':(1,0,'nut',480),
    'continuous':(0,0,'nut',480),'coarse-continuous':(0,0,'mkv',1024)}

def native(arguments,*,cwd=None):
    result=subprocess.run(list(map(str,arguments)),capture_output=True,cwd=cwd,timeout=120,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise AssertionError(result.stderr.decode('utf8','replace'))
    return result.stdout

def original_samples():
    t=np.arange(BLOCK*COUNT,dtype=np.float64)/RATE
    step=np.arange(BLOCK*COUNT)//BLOCK
    left=.17+.013*step+.08*np.sin(2*np.pi*433*t)
    right=-.19-.009*step+.07*np.sin(2*np.pi*739*t)
    return np.stack((left,right),axis=1).astype('<f4')

def fixture_sources(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    pcm=directory/'original.f32';pcm.write_bytes(original_samples().tobytes())
    rows={}
    for name,(gap,overlap,container,packet) in CASES.items():
        expression='N'
        if gap:expression+=f'+if(gte(N,{5*BLOCK}),{gap},0)'
        if overlap:expression+=f'-if(gte(N,{10*BLOCK}),{overlap},0)'
        target=directory/(name+'.'+container)
        command=[ffmpeg_path(),'-v','error','-f','lavfi','-i','color=c=0x203040:size=32x18:rate=25:duration=0.4',
            '-f','f32le','-ar',RATE,'-ac','2','-i',pcm,'-af',f"asetnsamples=n={packet}:p=0,asetpts='{expression}'",
            '-map','0:v:0','-map','1:a:0','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',target]
        native(command)
        raw=native([ffprobe_path(),'-v','error','-select_streams','a:0','-show_frames','-show_streams',
            '-show_entries','frame=pts,nb_samples:stream=time_base,sample_rate,channels','-of','json',target])
        probe=json.loads(raw);tb=Fraction(probe['streams'][0]['time_base'])
        if packet==BLOCK:
            expected=[i*BLOCK+(gap if i>=5 else 0)-(overlap if i>=10 else 0) for i in range(COUNT)]
            actual=[Fraction(int(row['pts']))*tb*RATE for row in probe['frames']]
            if actual!=expected or any(int(row['nb_samples'])!=BLOCK for row in probe['frames']):
                raise AssertionError((name,'muxer changed the intended fixture clock',actual,expected))
        if sum(int(row['nb_samples']) for row in probe['frames'])!=BLOCK*COUNT:
            raise AssertionError((name,'native decoded sample count differs'))
        rows[name]={'path':str(target.resolve()),'sha256':'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest(),
            'gap_samples':gap,'overlap_samples':overlap,'container':container,'packet_samples':packet,
            'native_frames':probe['frames'],'audio_time_base':str(tb),'command':list(map(str,command))}
    return {'cases':rows,'sample_rate':RATE,'channels':2,'blocks':COUNT,'block_samples':BLOCK,
        'rights':'Original deterministic samples and flat video; CC0-1.0. No external media or fonts.'}

class AudioDiscontinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        cls.shared=tempfile.TemporaryDirectory(prefix='native-audio-clock-',dir=base);cls.addClassCleanup(cls.shared.cleanup)
        cls.fixture=Path(cls.shared.name)
        manifest=os.environ.get('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES')
        data=json.loads(Path(manifest).read_bytes()) if manifest else fixture_sources(cls.fixture/'originals')
        cls.sources={}
        for name,row in data['cases'].items():
            path=Path(row['path']);actual='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
            if actual!=row['sha256']:raise AssertionError((name,'source SHA changed'))
            cls.sources[name]=path

    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='case-',dir=self.fixture);self.addCleanup(self.case.cleanup)
        self.root=Path(self.case.name)/'project';create_project(self.root)

    def expected(self,name):
        gap,overlap,_,_=CASES[name];source=original_samples()
        result=np.zeros((round(.4*RATE),2),dtype='<f4')
        for i in range(COUNT):
            start=i*BLOCK+(gap if i>=5 else 0)-(overlap if i>=10 else 0)
            result[start:start+BLOCK]=source[i*BLOCK:(i+1)*BLOCK]
        return result

    def compare(self,name,*,left=0.,right=.4,reverse=False,nested=False,curve=False):
        code,response=invoke('media','ingest','--project',self.root,'--input',self.sources[name]);self.assertEqual(code,0,response)
        project=load_project(self.root)[1]
        project['settings']['canvas']={'width':32,'height':18,'background':'#000000'}
        project['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':25,'den':1}}
        duration=round((right-left)*TPS);sequence=project['sequences'][0];sequence['duration_tick']=duration
        audio={'id':'sound','asset_id':response['data']['asset']['id'],'timeline_start_tick':0,
            'source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),'duration_tick':duration,'reverse':reverse}
        if curve:audio['speed_curve']={'keyframes':[{'at_tick':0,'speed':1.},{'at_tick':duration,'speed':1.}]}
        sequence['tracks']=[{'id':'picture','kind':'video','clips':[{'id':'background','asset_id':audio['asset_id'],
            'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':duration,'duration_tick':duration}]},
            {'id':'audio','kind':'audio','clips':[audio]}]
        if nested:
            child=copy.deepcopy(sequence);child['id']='child';child['tracks']=[{'id':'child-audio','kind':'audio','clips':[audio]}]
            project['sequences'].append(child);sequence['tracks'][1]['clips']=[{'id':'parent','sequence_id':'child',
                'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':duration,'duration_tick':duration}]
        save_project(self.root,project)
        inputs,graph,_,_=build_filter_graph(self.root,project,sequence,_persist_video_index=True)
        raw=native([ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,'-filter_complex',graph,
            '-map','[aout]','-f','f32le','-ac','2','pipe:1','-map','[vout]','-f','null','NUL'],cwd=self.root)
        actual=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
        expected=self.expected(name)[round(left*RATE):round(right*RATE)]
        if reverse:expected=expected[::-1]
        self.assertEqual(actual.shape,expected.shape)
        self.assertEqual(actual.tobytes(),expected.tobytes(),
            f'{name}: wrong source clock; max error {float(np.max(np.abs(actual.astype(float)-expected)))}')

    def test_internal_gap_keeps_every_native_sample_at_its_author_time(self):self.compare('gap')
    def test_window_wholly_inside_internal_gap_is_silent(self):self.compare('gap',left=.06,right=.09)
    def test_window_crossing_internal_gap_keeps_both_edges(self):self.compare('gap',left=.035,right=.115)
    def test_window_after_internal_gap_uses_presentation_time(self):self.compare('gap',left=.11,right=.18)
    def test_reverse_moves_the_internal_gap_with_the_content(self):self.compare('gap',right=.25,reverse=True)
    def test_nested_audio_uses_the_same_internal_clock(self):self.compare('gap',nested=True)
    def test_identity_curve_uses_the_same_internal_clock(self):self.compare('gap',curve=True)
    def test_monotonic_PTS_overlap_uses_later_decoded_frame_samples(self):self.compare('overlap')
    def test_alternating_gap_and_overlap_preserve_the_complete_clock(self):self.compare('mixed')
    def test_exact_native_timebase_keeps_a_one_sample_gap(self):self.compare('one-sample-gap')
    def test_coarse_quantized_continuous_source_keeps_every_sample(self):self.compare('coarse-continuous')
    def test_exact_continuous_source_keeps_every_sample(self):self.compare('continuous')
    def test_reverse_preserves_the_authored_window_after_native_audio_EOF(self):self.compare('continuous',reverse=True)

if __name__=='__main__':unittest.main()
