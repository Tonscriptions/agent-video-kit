"""Decoded PCM acceptance for source-contained native tempo context.

These checks accept controlled content, not natural speech/music quality.
The fixed pre-context product is expected to fail the DC regressions.
"""
from __future__ import annotations
import array, json, math, wave, unittest
import test_audio_buses as fixtures

TPS, SR = fixtures.TPS, fixtures.SR


class TempoContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.AudioBusTests.setUpClass.__func__(cls)
        for name in ('selection', 'gap', 'antiphase', 'left_only', 'tail_marker'):
            samples = array.array('h')
            for n in range(2*SR):
                left = right = 10000
                if name == 'selection':
                    left = right = -25000 if n < SR//2 else (25000 if n >= 3*SR//2 else 10000)
                if name == 'gap':
                    left = right = 0 if SR//2 <= n < 3*SR//2 else 10000
                if name == 'tail_marker' and n >= 2*SR-4800:
                    left = right = 25000
                if name in ('antiphase', 'left_only'):
                    left = round(10000*math.sin(2*math.pi*400*n/SR))
                    right = -left if name == 'antiphase' else 0
                samples.extend((left, right))
            with wave.open(str(cls.sources/f'{name}.wav'), 'wb') as handle:
                handle.setparams((2, 2, SR, 0, 'NONE', 'not compressed'))
                handle.writeframes(samples.tobytes())
            cls.pcm[name] = [v/32768 for v in samples]

    tearDownClass = classmethod(fixtures.AudioBusTests.tearDownClass.__func__)
    setUp = fixtures.AudioBusTests.setUp
    call = fixtures.AudioBusTests.call
    sequence = fixtures.AudioBusTests.sequence
    tone = fixtures.AudioBusTests.tone
    group = fixtures.AudioBusTests.group
    compose = fixtures.AudioBusTests.compose
    render = fixtures.AudioBusTests.render

    def ramp(self, name='dc', *, reverse=False, low=1, high=2):
        self.sequence('child')
        self.tone('child', 'child_audio_1', name)
        elapsed = 2*math.log(high/low)/(high-low)
        self.group('child', duration_tick=round(elapsed*TPS), reverse=reverse,
                   speed_curve={'keyframes': [{'at_tick': 0, 'speed': low}, {'at_tick': 2*TPS, 'speed': high}]})

    def check_dc(self, samples, start=.2, end=1.):
        checked = samples[round(start*SR)*2:round(end*SR)*2]
        self.assertTrue(checked)
        self.assertLessEqual(max(abs(x-10000/32768) for x in checked), .001)
        self.assertFalse(any(checked[n] == checked[n+1] == 0 for n in range(0, len(checked), 2)))

    def test_nested_ramp_keeps_dc_without_interior_zero_padding(self):
        self.ramp(); actual, _, _, _ = self.render(); self.check_dc(actual)

    def test_nested_reverse_ramp_keeps_dc_without_interior_zero_padding(self):
        self.ramp(reverse=True); actual, _, _, _ = self.render(); self.check_dc(actual)

    def test_direct_ramp_keeps_dc_without_interior_zero_padding(self):
        self.tone(name='dc', duration_tick=round(2*math.log(2)*TPS), speed_curve={'keyframes': [
            {'at_tick': 0, 'speed': 1}, {'at_tick': 2*TPS, 'speed': 2}]})
        actual, _, _, _ = self.render(); self.check_dc(actual)

    def test_nested_scalar_fast_keeps_dc_between_authored_anchors(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', 'dc')
        self.group('child', speed=2, duration_tick=TPS)
        actual, _, _, _ = self.render(); self.check_dc(actual, .1, .9)

    def test_nested_slow_ramp_keeps_dc_without_interior_zero_padding(self):
        self.ramp(low=.5, high=1); actual, _, _, _ = self.render(duration_tick=3*TPS); self.check_dc(actual, .2, 1.8)
        active=math.ceil(round(4*math.log(2)*TPS)*SR/TPS)
        self.assertLessEqual(max(abs(x-10000/32768) for x in actual[:active*2]), .001)
        self.assertEqual(max(map(abs,actual[active*2:])),0)

    def test_context_cannot_read_loud_content_outside_parent_source_selection(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', 'selection')
        self.group('child', source_in_tick=TPS//2, source_out_tick=3*TPS//2,
                   duration_tick=round(math.log(2)*TPS), speed_curve={'keyframes': [
                       {'at_tick': 0, 'speed': 1}, {'at_tick': TPS, 'speed': 2}]})
        actual, _, _, _ = self.render(); self.check_dc(actual, .1, .5)
        active=math.ceil(round(math.log(2)*TPS)*SR/TPS)
        self.assertLessEqual(max(abs(x-10000/32768) for x in actual[:active*2]), .001)
        self.assertEqual(max(map(abs,actual[active*2:])),0)

    def test_slow_ramp_retains_real_terminal_marker_and_authored_silence(self):
        self.ramp('tail_marker',low=.5,high=1);actual,_,_,_=self.render(duration_tick=3*TPS)
        active=math.ceil(round(4*math.log(2)*TPS)*SR/TPS)
        tail=actual[(active-512)*2:active*2]
        self.assertLessEqual(max(abs(x-25000/32768) for x in tail), .001)
        self.assertEqual(max(map(abs,actual[active*2:])),0)

    def test_authored_silence_remains_silent_in_ramped_source(self):
        self.ramp('gap'); actual, _, _, _ = self.render()
        # Source [0.5, 1.5) maps to [0.4463, 1.1192); this interior excludes
        # WSOLA's unaccepted transient edges without redefining the clock.
        quiet = actual[round(.6*SR)*2:round(.9*SR)*2]
        self.assertEqual(max(map(abs, quiet)), 0)
        self.assertGreater(max(map(abs, actual[:round(.1*SR)*2])), .25)

    def test_stereo_antiphase_is_preserved_through_joint_wsola(self):
        self.ramp('antiphase'); actual, _, _, _ = self.render()
        self.assertGreater(max(map(abs, actual)), .25)
        self.assertEqual(max(abs(actual[n]+actual[n+1]) for n in range(0, len(actual), 2)), 0)

    def test_silent_right_channel_does_not_receive_left_channel_audio(self):
        self.ramp('left_only'); actual, _, _, _ = self.render()
        self.assertGreater(max(map(abs, actual[::2])), .25)
        self.assertEqual(max(map(abs, actual[1::2])), 0)

    def test_unity_nested_samples_remain_an_exact_identity(self):
        self.sequence('child'); self.tone('child', 'child_audio_1', 'stereo'); self.group('child')
        actual, _, _, _ = self.render()
        self.assertEqual(actual, self.pcm['stereo'])

    def test_large_nested_slowdown_rejects_terminal_context_before_execution(self):
        self.sequence('child');self.tone('child','child_audio_1','dc');self.sequence('middle')
        self.group('child',target='middle',speed=.01,duration_tick=200*TPS)
        self.group('middle',source_out_tick=200*TPS,duration_tick=round(20000*math.log(2)*TPS),
                   speed_curve={'keyframes':[{'at_tick':0,'speed':.01},{'at_tick':200*TPS,'speed':.02}]})
        self.compose()
        def authored():
            value=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
            return json.dumps({k:value[k] for k in ('settings','assets','sequences')},sort_keys=True),(self.root/'rights-ledger.json').read_bytes()
        before=authored();output=self.root/'renders/not-created.mkv'
        result=self.call('render','--project',self.root,'--output',output,'--dry-run',expected=2)
        self.assertEqual(result['errors'][0]['code'],'AUDIO_TEMPO_CONTEXT_LIMIT')
        self.assertFalse(output.exists());self.assertEqual(authored(),before)


if __name__ == '__main__': unittest.main()
