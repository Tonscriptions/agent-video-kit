"""Native identity-tempo regression, runnable against the fixed prior product."""
from __future__ import annotations
import array,json,subprocess,unittest
import test_nested_time_mapping as fixtures
from ai_ad_editor.utils import atomic_write_json

def decode(path):
    p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-f','f32le','-acodec','pcm_f32le','pipe:1'],capture_output=True,check=True)
    values=array.array('f');values.frombytes(p.stdout);return values

class UnityAudioTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.NestedTimeMappingTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.NestedTimeMappingTests.tearDownClass.__func__)
    setUp=fixtures.NestedTimeMappingTests.setUp
    call=fixtures.NestedTimeMappingTests.call

    def test_unity_nested_four_ms_keeps_actual_tone_samples(self):
        self.call('media','ingest','--project',self.root,'--input',self.speech,'--asset-id','sound')
        changes={'operations':[{'op':'add_sequence','id':'child','duration_tick':270000},
            {'op':'add_track','sequence_id':'child','track_id':'audio','kind':'audio','order':1},
            {'op':'append_clip','sequence_id':'child','track_id':'audio','id':'sound_leaf','asset_id':'sound','source_in_tick':0,'source_out_tick':270000,'duration_tick':270000},
            {'op':'append_sequence_clip','sequence_id':'seq_main','track_id':'track_audio_1','id':'nested','nested_sequence_id':'child','source_in_tick':18090,'source_out_tick':18450,'duration_tick':360,'timeline_start_tick':0},
            {'op':'append_clip','sequence_id':'seq_main','track_id':'track_video_1','id':'video','asset_id':'frames','source_in_tick':0,'duration_tick':45000,'source_out_tick':45000}]}
        path=self.base/'changes.json';atomic_write_json(path,changes);self.call('timeline','compose','--project',self.root,'--input',path)
        output=self.root/'renders/unity.mkv';self.call('render','--project',self.root,'--output',output,'--container','mkv','--audio-codec','pcm_s16le')
        actual=decode(output);self.assertEqual(sum(v!=0 for v in actual[:384]),378);self.assertTrue(all(v==0 for v in actual[384:]))


if __name__=='__main__':unittest.main()
