"""Real local offline audio, preservation, independent tone and failure gates."""
from __future__ import annotations
import array
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
from unittest import mock
import unittest
import wave

import test_nested_time_mapping as fixtures
from ai_ad_editor.audio_stretch import ENGINE, configuration, execute, inspect_pcm, plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.utils import atomic_write_json

TPS=90000

def digest(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def decode(path):
    p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-f','f32le','-acodec','pcm_f32le','pipe:1'],capture_output=True,check=True)
    values=array.array('f');values.frombytes(p.stdout);return values

def peak_hz(samples, expected):
    values=samples[len(samples)//8:len(samples)*7//8];n=len(values)
    def energy(hz):
        angle=2*math.pi*hz/48000;coefficient=2*math.cos(angle);a=b=0.
        for i,value in enumerate(values):
            c=value*(.5-.5*math.cos(2*math.pi*i/max(1,n-1)))+coefficient*a-b;b=a;a=c
        return a*a+b*b-coefficient*a*b
    return max(range(expected-45,expected+46),key=energy)


class OfflineAudioStretchTests(unittest.TestCase):
    setUp=fixtures.NestedTimeMappingTests.setUp
    call=fixtures.NestedTimeMappingTests.call

    @classmethod
    def setUpClass(cls):
        value=os.environ.get('AI_AD_EDITOR_TEST_RUBBERBAND') or shutil.which('rubberband')
        if not value:raise unittest.SkipTest('Native offline tests require an explicitly supplied local Rubber Band executable')
        cls.binary=Path(value).resolve();cls.license=cls.binary.with_name('COPYING.txt');cls.dll=cls.binary.with_name('sndfile.dll')
        assert all(p.is_file() for p in (cls.binary,cls.license,cls.dll))
        fixtures.NestedTimeMappingTests.setUpClass.__func__(cls)
        cls.stereo=cls.fixture_root/'stereo.wav';values=array.array('h')
        for i in range(144000):
            values.extend((round(.2*32767*math.sin(2*math.pi*400*i/48000)),round(.15*32767*math.sin(2*math.pi*800*i/48000))))
        with wave.open(str(cls.stereo),'wb') as h:h.setparams((2,2,48000,0,'NONE',''));h.writeframes(values.tobytes())

    tearDownClass=classmethod(fixtures.NestedTimeMappingTests.tearDownClass.__func__)

    def config(self):
        return {'engine':ENGINE,'executable':str(self.binary),'sha256':digest(self.binary),
                'dependencies':[{'path':str(self.dll),'sha256':digest(self.dll)}],
                'license_path':str(self.license),'license_sha256':digest(self.license),'license_spdx':'GPL-2.0-or-later'}

    def prepare(self, *, left=.25, right=.375, duration=.25, reverse=False, curve=None, nested=False):
        self.call('media','ingest','--project',self.root,'--input',self.stereo,'--asset-id','stereo')
        p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'));p['settings']['audio_stretch']=self.config();atomic_write_json(self.root/'project.json',p)
        clip={'op':'append_clip','sequence_id':'seq_main','track_id':'track_audio_1','id':'sound','asset_id':'stereo',
              'source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),'duration_tick':round(duration*TPS),'speed':(right-left)/duration,'reverse':reverse}
        ops=[{'op':'append_clip','sequence_id':'seq_main','track_id':'track_video_1','id':'video','asset_id':'frames','source_in_tick':0,'source_out_tick':TPS,'duration_tick':TPS}]
        if curve:clip['speed_curve']=curve
        if nested:
            ops+=[{'op':'add_sequence','id':'child','duration_tick':3*TPS},{'op':'add_track','sequence_id':'child','track_id':'child_audio','kind':'audio','order':1},
                  {**{k:v for k,v in clip.items() if k!='speed_curve'},'sequence_id':'child','track_id':'child_audio','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS,'speed':1.,'reverse':False}]
            ops.append({'op':'append_sequence_clip','sequence_id':'seq_main','track_id':'track_audio_1','id':'parent','nested_sequence_id':'child','timeline_start_tick':0,
                        'source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),'duration_tick':round(duration*TPS),'speed':(right-left)/duration,'reverse':reverse,
                        **({'speed_curve':curve} if curve else {})})
        else:ops.append(clip)
        change=self.base/'audio-change.json';atomic_write_json(change,{'operations':ops});self.call('timeline','compose','--project',self.root,'--input',change)
        return json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))

    def render(self,name='offline',extra=()):
        output=self.root/f'renders/{name}.mkv';result=self.call('render','--project',self.root,'--output',output,'--container','mkv','--audio-codec','pcm_f32le',*extra)
        manifest=json.loads(output.with_suffix('.mkv.manifest.json').read_text(encoding='utf-8-sig'))
        job=next(i['audio_stretch'] for i in manifest['inputs'] if i.get('audio_stretch'))
        self.assertEqual(job['execution']['status'],'succeeded');return output,job,result

    def test_whole_clip_scalar_stretch_preserves_stereo_tones(self):
        self.prepare();output,job,_=self.render();values=decode(output);channels=[values[c:24000:2] for c in range(2)]
        self.assertEqual(job['source_frames'],6000);self.assertEqual(job['target_frames'],12000)
        self.assertNotIn('--timemap',job['execution']['command']);self.assertNotIn('NaN',job['execution']['engine_stderr'])
        for samples,hz in zip(channels,(400,800)):
            self.assertLessEqual(abs(peak_hz(samples,hz)-hz),5);self.assertGreater(math.sqrt(sum(v*v for v in samples)/len(samples)),.04)
        self.assertTrue(all(v==0 for v in values[24000:]))

    def test_four_ms_offline_output_has_sound_in_all_deciles(self):
        self.prepare(left=.201,right=.205,duration=.25,nested=True);output,job,_=self.render();values=decode(output)
        self.assertEqual(job['source_frames'],192);self.assertEqual(job['target_frames'],12000)
        for i in range(10):
            part=values[i*2400:(i+1)*2400];self.assertGreater(math.sqrt(sum(v*v for v in part)/len(part)),.0005)
        self.assertFalse(job['execution']['pitch_and_listening_accepted'])

    def test_reverse_output_matches_reversed_derived_pcm(self):
        self.prepare(reverse=True,nested=True);output,job,_=self.render();rendered=decode(output);derived=decode(job['output'])
        expected=array.array('f')
        for i in range(len(derived)-2,-1,-2):expected.extend(derived[i:i+2])
        self.assertEqual(rendered[:len(expected)],expected)

    def test_faster_stretch_retains_pitch_and_exact_sample_count(self):
        self.prepare(duration=.0625);output,job,_=self.render();self.assertEqual(job['target_frames'],3000)
        values=decode(output)
        for c,hz in enumerate((400,800)):self.assertLessEqual(abs(peak_hz(values[c:6000:2],hz)-hz),5)

    def test_dry_run_never_decodes_or_runs_the_offline_engine(self):
        self.prepare();self.assertFalse((self.root/'cache/audio-stretch').exists())
        with mock.patch('ai_ad_editor.audio_stretch.run_process',side_effect=AssertionError('plan decoded media')):
            value=self.call('render','--project',self.root,'--output',self.root/'renders/plan.mkv','--container','mkv','--dry-run')
        self.assertFalse((self.root/'cache/audio-stretch').exists());self.assertEqual(value['data']['status'],'planned')

    def test_repeated_render_keeps_the_prior_cached_audio_bytes(self):
        self.prepare();_,first,_=self.render('one');_,second,_=self.render('two')
        self.assertEqual(first['key'],second['key']);self.assertEqual(first['execution']['output_pcm']['sha256'],second['execution']['output_pcm']['sha256'])

    def test_nonlinear_nested_curve_uses_one_whole_clip_time_map(self):
        curve={'keyframes':[{'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},
                            {'at_tick':234000,'speed':2.8}]}
        self.prepare(left=.2,right=2.8,duration=1.5,nested=True,curve=curve)
        output,job,_=self.render();self.assertEqual(job['target_frames'],72000);self.assertGreater(len(job['time_map']),10)
        self.assertTrue(all(0<a<job['source_frames'] and 0<b<job['target_frames'] for a,b in job['execution']['engine_time_map']));self.assertNotIn('NaN',job['execution']['engine_stderr'])
        values=decode(output)
        for c,hz in enumerate((400,800)):self.assertLessEqual(abs(peak_hz(values[c::2],hz)-hz),5)

    def direct_plan(self, *, right=.375, duration=.25):
        project=self.prepare();asset=next(a for a in project['assets'] if a['id']=='stereo')
        source=self.root/asset['uri'];engine=configuration(self.root,self.config())
        return plan(self.root,engine,asset,source,.25,right,[],duration,False)

    def test_remote_engine_reference_is_rejected_before_a_process_starts(self):
        config=self.config();config['executable']='https://example.invalid/tool.exe'
        with mock.patch('ai_ad_editor.audio_stretch.run_process') as process:
            with self.assertRaises(AppError):configuration(self.root,config)
        process.assert_not_called()

    def test_dependency_hash_changes_fail_before_a_process_starts(self):
        config=self.config();license_file=self.base/'license.txt';shutil.copyfile(self.license,license_file);config['license_path']=str(license_file)
        license_file.write_bytes(license_file.read_bytes()+b'changed')
        with mock.patch('ai_ad_editor.audio_stretch.run_process') as process:
            with self.assertRaises(AppError) as caught:configuration(self.root,config)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_HASH_MISMATCH');process.assert_not_called()

    def test_missing_declared_native_dependency_is_rejected(self):
        config=self.config();config['dependencies']=[]
        with self.assertRaises(AppError) as caught:configuration(self.root,config)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_DEPENDENCY_MISSING')

    def test_unknown_engine_options_are_rejected(self):
        config=self.config();config['download_url']='unused'
        with self.assertRaises(AppError) as caught:configuration(self.root,config)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_CONFIG_INVALID')

    def test_cache_tamper_fails_without_overwriting_the_prior_file(self):
        self.prepare();_,job,_=self.render();cache=Path(job['output']);bad=cache.read_bytes()+b'corrupt';cache.write_bytes(bad)
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):code=fixtures.main(['render','--project',str(self.root),'--output',str(self.root/'renders/tampered.mkv'),'--container','mkv'])
        value=json.loads(capture.getvalue());self.assertEqual(code,6);self.assertIn('AUDIO_STRETCH_CACHE_CONFLICT',json.dumps(value))
        self.assertEqual(cache.read_bytes(),bad);self.assertFalse((self.root/'renders/tampered.mkv').exists())

    def test_cancelled_preprocessing_does_not_create_a_derived_file(self):
        job=self.direct_plan();marker=self.base/'cancel.flag';marker.write_text('cancel',encoding='utf-8');temp=self.base/'scratch';temp.mkdir()
        with self.assertRaises(AppError) as caught:execute(self.root,job,temp,cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertFalse(Path(job['output']).exists());self.assertEqual(list(temp.iterdir()),[])

    def test_genuinely_short_input_is_not_padded_into_success(self):
        job=self.direct_plan(right=3.25,duration=3.)
        temp=self.base/'scratch';temp.mkdir()
        with self.assertRaises(AppError) as caught:execute(self.root,job,temp)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_SOURCE_LENGTH_MISMATCH');self.assertFalse(Path(job['output']).exists())

    def test_pcm_and_channel_budgets_fail_before_decode(self):
        project=self.prepare();asset=next(a for a in project['assets'] if a['id']=='stereo');engine=configuration(self.root,self.config())
        with mock.patch('ai_ad_editor.audio_stretch.run_process') as process:
            with self.assertRaises(AppError) as caught:plan(self.root,engine,asset,self.root/asset['uri'],0,3,[],10000.,False)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_BUDGET_EXCEEDED');process.assert_not_called()

    def test_float_pcm_rejects_nan_and_truncated_chunks(self):
        path=self.base/'nan.wav';fmt=struct.pack('<HHIIHH',3,1,48000,192000,4,32);data=struct.pack('<f',float('nan'))
        raw=b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',4)+data
        path.write_bytes(b'RIFF'+struct.pack('<I',len(raw))+raw)
        with self.assertRaises(AppError) as caught:inspect_pcm(path)
        self.assertEqual(caught.exception.code,'AUDIO_STRETCH_PCM_INVALID');path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaises(AppError):inspect_pcm(path)

    def test_high_precision_pcm_matroska_exports_are_real(self):
        self.prepare()
        for codec in ('pcm_s24le','pcm_s32le','pcm_f32le'):
            with self.subTest(codec=codec):
                output,job,_=self.render(codec,('--audio-codec',codec))
                probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(output)],capture_output=True,check=True).stdout)
                self.assertEqual(next(s['codec_name'] for s in probe['streams'] if s['codec_type']=='audio'),codec)
                values=decode(output);reference=decode(job['output']);self.assertEqual(len(values[:24000]),len(reference))
                self.assertLessEqual(max(abs(a-b) for a,b in zip(values,reference)),2**-22)


if __name__=='__main__':unittest.main()
