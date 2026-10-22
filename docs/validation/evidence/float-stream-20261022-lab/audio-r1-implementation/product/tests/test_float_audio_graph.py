"""Actual authored stereo PCM through the common-engine Float32 audio adapter."""
import copy,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_audio_graph import prepare,verify
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.project import initial_project
from ai_ad_editor.render import build_filter_graph

NATIVE_CALLS=[]
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()

class FloatAudioGraphTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='float-audio-',dir=base);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        t=np.arange(48000,dtype=np.float64)/48000;self.samples=np.stack((.2*np.sin(2*np.pi*347*t),.17*np.cos(2*np.pi*619*t)),1).astype('<f4')
        raw=self.root/'source.f32';raw.write_bytes(self.samples.tobytes());self.audio=self.root/'source.wav'
        self.native([ffmpeg_path(),'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',raw,'-c:a','pcm_f32le',self.audio])
        self.p=initial_project('float audio graph fixture','float_audio');self.p['settings']['canvas'].update(width=8,height=4);self.p['settings']['timebase']['display_fps']={'num':10,'den':1}
        self.p['assets']=[{'id':'sound','kind':'audio','uri':'source.wav','sha256':sha(self.audio),'probe':probe_media(self.audio),'rights_ref':'rights_generated'},
            {'id':'visual','kind':'video','uri':'this-visual-file-is-deliberately-absent.mp4','sha256':'sha256:'+'a'*64,'probe':{'duration_tick':90000,'video':{'width':8,'height':4,'fps':'10/1'}},'rights_ref':'rights_generated'}]
        s=self.p['sequences'][0];s['duration_tick']=90000
        self.c={'id':'sound','asset_id':'sound','timeline_start_tick':0,'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000}
        self.v={'id':'visual','asset_id':'visual','timeline_start_tick':0,'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000}
        s['tracks'][0]['clips']=[self.v];s['tracks'][1]['clips']=[self.c]

    def native(self,command):
        command=list(map(str,command));p=subprocess.run(command,capture_output=True,cwd=self.root,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        NATIVE_CALLS.append({'test':self.id(),'command':command,'exit_code':p.returncode,'stdout_bytes':len(p.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),'stderr':p.stderr.decode('utf8','replace')[-2000:]})
        self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace')[-2000:]);return p.stdout

    def render(self,project=None):
        p=self.p if project is None else project;before=copy.deepcopy(p);plan=prepare(self.root,p,'seq_main');self.assertEqual(p,before)
        result=self.native([ffmpeg_path(),'-nostdin','-v','error','-filter_complex_threads','1',*plan['inputs'],'-filter_complex',plan['filter_complex'],'-map','[aout]','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(len(result),plan['expected_samples_48000']*8);verify(self.root,plan);return result,plan

    def test_native_stereo_source_is_exact_and_missing_visual_is_never_opened(self):
        result,plan=self.render();self.assertEqual(result,self.samples.tobytes());self.assertEqual(plan['pruned_visual_leaves'],1)
        self.assertNotIn('this-visual-file',str(plan['inputs']));self.assertTrue(plan['synthetic_video_discarded'])

    def test_half_open_source_trim_and_timeline_silence_match_every_sample(self):
        self.c.update(timeline_start_tick=9000,duration_tick=45000,source_in_tick=9000,source_out_tick=54000)
        result,_=self.render();expected=np.zeros_like(self.samples);expected[4800:28800]=self.samples[4800:28800];self.assertEqual(result,expected.tobytes())

    def test_reverse_preserves_channel_pairs_and_every_original_sample(self):
        self.c['reverse']=True;result,_=self.render();self.assertEqual(result,self.samples[::-1].tobytes())

    def test_freeze_inserts_exact_authored_silence_and_preserves_source_clock(self):
        self.c.update(source_out_tick=72000,freeze={'at_tick':22500,'duration_tick':18000})
        result,_=self.render();expected=np.concatenate((self.samples[:12000],np.zeros((9600,2),'<f4'),self.samples[12000:38400]));self.assertEqual(result,expected.tobytes())

    def test_nested_video_container_retains_complete_child_audio_and_window(self):
        root=self.p['sequences'][0];child=copy.deepcopy(root);child['id']='child';child['tracks'][0]['id']='child_video';child['tracks'][1]['id']='child_audio';self.p['sequences'].append(child)
        parent={'id':'nested','sequence_id':'child','timeline_start_tick':0,'duration_tick':45000,'source_in_tick':0,'source_out_tick':90000,
            'presentation_window':{'version':1,'authored_start_tick':0,'authored_duration_tick':90000,'offset_tick':18000}}
        root['duration_tick']=45000;root['tracks'][0]['clips']=[parent];root['tracks'][1]['clips']=[]
        result,_=self.render();self.assertEqual(result,self.samples[9600:33600].tobytes())

    def test_audio_volume_automation_is_retained_after_visual_keyframes_are_pruned(self):
        self.c['keyframes']=[{'property':'audio.volume_db','keyframes':[{'at_tick':0,'value':-6,'interpolation':'linear'},{'at_tick':90000,'value':-6,'interpolation':'linear'}]},
            {'property':'opacity','keyframes':[{'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':90000,'value':1,'interpolation':'linear'}]}]
        result,_=self.render();actual=np.frombuffer(result,'<f4').reshape(-1,2);np.testing.assert_allclose(actual,self.samples*10**(-6/20),atol=3e-8,rtol=0)

    def test_empty_and_muted_audio_keep_exact_authored_sample_count(self):
        self.p['sequences'][0]['duration_tick']=112501;self.p['sequences'][0]['tracks'][1]['muted']=True
        result,plan=self.render();self.assertEqual(plan['expected_samples_48000'],60001);self.assertEqual(result,bytes(60001*8))

    def test_cancel_and_unconnected_source_transitions_reject_without_real_video_decode(self):
        marker=self.root/'cancel';marker.touch()
        with self.assertRaises(AppError) as caught:prepare(self.root,self.p,'seq_main',cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED');self.p['sequences'][0]['source_transitions']=[{'id':'not-wired'}]
        with self.assertRaises(AppError) as caught:prepare(self.root,self.p,'seq_main')
        self.assertEqual(caught.exception.code,'FLOAT_AUDIO_SOURCE_TRANSITION_UNCONNECTED')

if __name__=='__main__':unittest.main()
