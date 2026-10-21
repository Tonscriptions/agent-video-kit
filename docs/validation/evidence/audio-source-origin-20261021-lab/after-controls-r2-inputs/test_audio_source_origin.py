"""Native PCM source origins across scalar, nested, curve, R3 and audio sync paths."""
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np

from ai_ad_editor.audio_stretch import configuration,execute
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.multicam import synchronize_multicam_sources
from ai_ad_editor.project import create_project,load_project,save_project
from ai_ad_editor.render import build_filter_graph
from test_magnetic_reorder import invoke

RATE,TPS=48000,90000


class AudioSourceOriginTests(unittest.TestCase):
    @staticmethod
    def native(arguments,*,cwd=None):
        result=subprocess.run(list(map(str,arguments)),capture_output=True,cwd=cwd,timeout=180)
        if result.returncode:raise AssertionError(result.stderr.decode('utf8','replace'))
        return result.stdout

    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        cls.shared=tempfile.TemporaryDirectory(prefix='audio-origin-fixtures-',dir=base);cls.addClassCleanup(cls.shared.cleanup)
        cls.fixture=Path(cls.shared.name);count=3*RATE;t=np.arange(count,dtype=np.float64)/RATE
        rng=np.random.default_rng(62731);gain=rng.uniform(.08,.7,150)[np.arange(count)//960]
        cls.pcm=np.stack((np.sin(2*np.pi*433*t)*gain,np.sin(2*np.pi*739*t)*gain*.73),axis=1).astype('<f4')
        cls.expected=np.concatenate((np.zeros((RATE,2),dtype='<f4'),cls.pcm[:2*RATE]))
        frames=[bytes((30+i,50+2*i,220-i,255))*(32*18) for i in range(75)]
        cls.sources={}
        for name in ('reference','camera'):
            (cls.fixture/(name+'.rgba')).write_bytes(b''.join(frames) if name=='reference' else
                bytes((200,0,0,255))*(32*18)*25+b''.join(frames[:50]))
            (cls.fixture/(name+'.f32')).write_bytes((cls.pcm if name=='reference' else cls.pcm[:2*RATE]).tobytes())
            path=cls.fixture/(name+'.mkv');command=[ffmpeg_path(),'-hide_banner','-v','error','-f','rawvideo',
                '-pixel_format','rgba','-video_size','32x18','-framerate','25','-i',cls.fixture/(name+'.rgba'),
                '-f','f32le','-ar',RATE,'-ac','2','-i',cls.fixture/(name+'.f32')]
            if name=='camera':command+=['-filter_complex','[1:a]asetpts=PTS+1/TB[a]','-map','0:v:0','-map','[a]']
            command+=['-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',path]
            cls.native(command);cls.sources[name]=path
            offset=cls.fixture/(name+'-offset.mkv')
            cls.native([ffmpeg_path(),'-v','error','-i',path,'-map','0','-c','copy','-output_ts_offset','5',offset])
            cls.sources[name+'-offset']=offset

    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='case-',dir=self.fixture);self.addCleanup(self.case.cleanup)
        self.work=Path(self.case.name);self.root=self.work/'project';create_project(self.root)

    def project(self,name='camera',*,left=0.,right=3.,reverse=False,curve=False,nested=False,speed=1.):
        code,value=invoke('media','ingest','--project',self.root,'--input',self.sources[name]);self.assertEqual(code,0,value)
        p=load_project(self.root)[1];p['settings']['canvas']={'width':32,'height':18,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':25,'den':1}}
        seq=p['sequences'][0];duration=round((right-left)*TPS/speed);seq['duration_tick']=duration
        audio={'id':'sound','asset_id':value['data']['asset']['id'],'source_in_tick':round(left*TPS),
            'source_out_tick':round(right*TPS),'duration_tick':duration,'timeline_start_tick':0,'reverse':reverse,'speed':speed}
        if curve:audio['speed_curve']={'keyframes':[{'at_tick':0,'speed':1.},{'at_tick':3*TPS,'speed':1.}]}
        seq['tracks']=[{'id':'video','kind':'video','clips':[{'id':'picture','asset_id':audio['asset_id'],
            'source_in_tick':0,'source_out_tick':duration,'duration_tick':duration,'timeline_start_tick':0}]},
            {'id':'audio','kind':'audio','clips':[audio]}]
        if nested:
            child=copy.deepcopy(seq);child['id']='child'
            child['tracks']=[{'id':'child-audio','kind':'audio','clips':[{**audio,'id':'leaf'}]}]
            p['sequences'].append(child)
            seq['tracks'][1]['clips']=[{'id':'parent','sequence_id':'child','source_in_tick':0,
                'source_out_tick':duration,'duration_tick':duration,'timeline_start_tick':0}]
        save_project(self.root,p);return p,seq

    def render(self,p,seq):
        inputs,graph,metadata,warnings=build_filter_graph(self.root,p,seq)
        data=self.native([ffmpeg_path(),'-hide_banner','-v','error','-filter_complex_threads','1',*inputs,
            '-filter_complex',graph,'-map','[aout]','-f','f32le','-ac','2','pipe:1',
            '-map','[vout]','-f','null','NUL'],cwd=self.root)
        return data,metadata,warnings

    def test_audio_offset_includes_the_native_delayed_stream_start(self):
        sync=synchronize_multicam_sources([{'asset_id':n,'path':self.sources[n]} for n in ('reference','camera')],
            reference_asset_id='reference',analysis_seconds=3,max_offset_seconds=1.5)
        row=next(r for r in sync['offsets'] if r['asset_id']=='camera')
        self.assertAlmostEqual(row['relative_delay_seconds'],1.,delta=.021)
        self.assertGreater(row['score'],.95)

    def test_complete_explicit_audio_preserves_leading_silence_and_every_PCM_sample(self):
        p,seq=self.project();actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.expected.tobytes())

    def test_window_wholly_before_first_native_audio_is_silent(self):
        p,seq=self.project(left=.2,right=.8);actual,_,_=self.render(p,seq)
        self.assertEqual(actual,bytes(round(.6*RATE)*8))

    def test_window_crossing_native_start_preserves_partial_leading_gap(self):
        p,seq=self.project(left=.5,right=2.5);actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.expected[RATE//2:5*RATE//2].tobytes())

    def test_reverse_reverses_the_source_gap_with_the_content(self):
        p,seq=self.project(reverse=True);actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.expected[::-1].tobytes())

    def test_zero_origin_audio_remains_sample_exact(self):
        p,seq=self.project('reference');actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.pcm.tobytes())

    def test_equal_nonzero_audio_and_container_origins_add_no_false_silence(self):
        p,seq=self.project('reference-offset');actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.pcm.tobytes())

    def test_delayed_audio_uses_relative_gap_after_nonzero_container_origin(self):
        p,seq=self.project('camera-offset');actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.expected.tobytes())

    def test_identity_speed_curve_uses_the_same_native_audio_origin(self):
        p,seq=self.project(curve=True);actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.expected.tobytes())

    def test_nested_identity_audio_uses_the_same_native_audio_origin(self):
        p,seq=self.project(nested=True);actual,_,_=self.render(p,seq)
        self.assertEqual(actual,self.expected.tobytes())

    def r3(self,left,right):
        binary=os.environ.get('AI_AD_EDITOR_TEST_RUBBERBAND')
        if not binary:self.skipTest('requires explicitly supplied existing native Rubber Band')
        binary=Path(binary).resolve();license=binary.with_name('COPYING.txt');dll=binary.with_name('sndfile.dll')
        digest=lambda path:'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
        p,seq=self.project(left=left,right=right,speed=2.)
        p['settings']['audio_stretch']={'engine':'rubberband-r3-offline-v1','executable':str(binary),'sha256':digest(binary),
            'license_path':str(license),'license_sha256':digest(license),'license_spdx':'GPL-2.0-or-later',
            'dependencies':[{'path':str(dll),'sha256':digest(dll)}]}
        save_project(self.root,p)
        _,_,metadata,_=build_filter_graph(self.root,p,seq)
        job=next(r['audio_stretch'] for r in metadata if r.get('audio_stretch'))
        scratch=self.work/'scratch';scratch.mkdir()
        return execute(self.root,job,scratch)

    def test_R3_receives_all_source_clock_samples_including_the_native_gap(self):
        result=self.r3(0.,3.)
        self.assertEqual(result['input_pcm']['frames'],3*RATE)
        self.assertEqual(result['output_pcm']['frames'],3*RATE//2)

    def test_R3_wholly_leading_source_window_remains_silence(self):
        result=self.r3(.2,.8)
        self.assertEqual(result['input_pcm']['frames'],round(.6*RATE))
        self.assertEqual(result['input_pcm']['nonzero_samples'],[0,0])
        self.assertEqual(result['output_pcm']['nonzero_samples'],[0,0])


if __name__=='__main__':unittest.main()
