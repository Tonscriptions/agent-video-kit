"""Native encoded frame coverage at fractional nested source/output boundaries."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import unittest

from PIL import Image

import test_nested_time_mapping as fixtures
import test_speed_easing as reference
from ai_ad_editor.utils import atomic_write_json

TPS, W, H = 90000, 96, 64


class NestedFrameCoverageTests(unittest.TestCase):
    setUp = fixtures.NestedTimeMappingTests.setUp
    call = fixtures.NestedTimeMappingTests.call

    @classmethod
    def setUpClass(cls):
        fixtures.NestedTimeMappingTests.setUpClass.__func__(cls)
        cls.fractional_source = cls.fixture_root/'fractional.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(cls.source), '-an',
                        '-vf', 'setpts=N*1001/(30000*TB)', '-r', '30000/1001',
                        '-frames:v', '72', '-c:v', 'libx264', '-crf', '12',
                        '-pix_fmt', 'yuv420p', str(cls.fractional_source)],
                       capture_output=True, check=True)

    tearDownClass = classmethod(fixtures.NestedTimeMappingTests.tearDownClass.__func__)

    def render_coverage(self, parents, *, leaf_in=0., leaf_out=3.,
                        source_fps=Fraction(24), output_fps=Fraction(24)):
        asset='frames'
        if source_fps != 24:
            self.call('media','ingest','--project',self.root,'--input',self.fractional_source,'--asset-id','fractional')
            asset='fractional'
        leaf_span=round((leaf_out-leaf_in)*TPS)
        operations=[{'op':'add_sequence','id':'child_0','duration_tick':leaf_span},
            {'op':'append_clip','sequence_id':'child_0','track_id':'child_0_video_1','id':'leaf',
             'asset_id':asset,'source_in_tick':round(leaf_in*TPS),'source_out_tick':round(leaf_out*TPS),
             'duration_tick':leaf_span}]
        current='child_0';steps=[]
        for index,config in enumerate(parents):
            left,right=config.get('in',0.),config['out'];span=right-left
            mode=config.get('mode','linear');controls=tuple(config.get('controls',()))
            speeds=tuple(config.get('speeds',(1.,1.)))
            duration_tick=config.get('duration_tick',round(reference.elapsed(span,span,mode,controls,speeds)*TPS))
            duration=duration_tick/TPS;start_tick=config.get('start_tick',round(config.get('start',0.)*TPS))
            target='seq_main' if index==len(parents)-1 else f'child_{index+1}'
            if target!='seq_main':operations.append({'op':'add_sequence','id':target,'duration_tick':start_tick+duration_tick})
            point={'at_tick':0,'speed':speeds[0],'interpolation':mode}
            if controls:point['control_points']=list(controls)
            operations.append({'op':'append_sequence_clip','sequence_id':target,
                'track_id':'track_video_1' if target=='seq_main' else target+'_video_1',
                'id':f'parent_{index}','nested_sequence_id':current,'source_in_tick':round(left*TPS),
                'source_out_tick':round(right*TPS),'timeline_start_tick':start_tick,'duration_tick':duration_tick,
                'reverse':bool(config.get('reverse')),'speed_curve':{'keyframes':[point,
                    {'at_tick':round(span*TPS),'speed':speeds[1]}]}})
            steps.append((left,right,duration,bool(config.get('reverse')),mode,controls,speeds,start_tick/TPS))
            current=target
        change=self.base/'coverage.json';atomic_write_json(change,{'operations':operations})
        self.call('timeline','compose','--project',self.root,'--input',change)
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        project['settings']['timebase']['display_fps']={'num':output_fps.numerator,'den':output_fps.denominator}
        # Retain a real trailing timeline gap so extending the video past its
        # authored end cannot pass merely because the encoder stops there.
        final=steps[-1];end=final[7]+final[2]
        project['sequences'][0]['duration_tick']=round((end+.25)*TPS)
        atomic_write_json(self.root/'project.json',project)
        def authored():
            p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
            raw=json.dumps({key:p[key] for key in ('assets','settings','sequences')},sort_keys=True).encode()
            return hashlib.sha256(raw).hexdigest(),hashlib.sha256((self.root/'rights-ledger.json').read_bytes()).hexdigest()
        before=authored();output=self.root/'renders/coverage.mp4'
        result=self.call('render','--project',self.root,'--output',output,'--crf','0','--pixel-format','yuv444p')
        self.assertEqual(before,authored())
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
        stride=W*H*3;self.assertEqual(len(raw)%stride,0)
        frames=[Image.frombytes('RGB',(W,H),raw[i:i+stride]) for i in range(0,len(raw),stride)]
        self.assertGreaterEqual(len(frames),math.ceil(end*float(output_fps))+2)
        observations=[]
        for index,image in enumerate(frames):
            time=float(Fraction(index,1)/output_fps);author=time;visible=True
            for left,right,duration,reverse,mode,controls,speeds,start in reversed(steps):
                if not start<=author<start+duration:
                    visible=False;break
                author=reference.undo((left,right,duration,reverse,mode,controls,speeds),author-start)
            present=image.getpixel((W//2,H//2))[1]>35
            expected=max(0,min(71,math.floor((round(leaf_in*TPS)/TPS+author)*float(source_fps)+1e-7))) if visible else None
            actual=sum(1<<bit for bit in range(7) if image.getpixel((bit*12+6,8))[0]>128)
            observations.append({'frame':index,'seconds':time,'expected_visible':visible,'present':present,
                                 'source_frame':actual,'expected_source_frame':expected})
        self.assertEqual([r for r in observations if r['present']!=r['expected_visible']],[],observations)
        self.assertEqual([r for r in observations if r['expected_visible'] and abs(r['source_frame']-r['expected_source_frame'])>1],[],observations)
        return frames,observations,result

    def bezier(self,**overrides):
        return {'in':.2,'out':2.8,'start':.125,'reverse':True,'mode':'bezier',
                'controls':(.15,.05,.85,.7),'speeds':(.6,2.8),**overrides}

    def test_trimmed_bezier_reverse_preserves_all_visible_frames(self):
        self.render_coverage([self.bezier()])

    def test_trimmed_bezier_forward_covers_both_partial_source_frames(self):
        self.render_coverage([self.bezier(reverse=False)])

    def test_trimmed_linear_reverse_holds_the_last_partial_frame(self):
        self.render_coverage([{'in':.217,'out':2.797,'start':.137,'reverse':True,'speeds':(.6,2.8)}])

    def test_fractional_output_uses_the_global_half_open_interval(self):
        self.render_coverage([self.bezier()],output_fps=Fraction(30000,1001))

    def test_one_tick_after_grid_does_not_reveal_an_early_frame(self):
        self.render_coverage([{'in':.2,'out':2.8,'start_tick':11251,'duration_tick':2*TPS}])

    def test_exact_global_end_does_not_extend_into_the_trailing_gap(self):
        self.render_coverage([{'in':.25,'out':2.75,'start':.125,'duration_tick':2*TPS,'reverse':True}])

    def test_tiny_forward_trim_keeps_its_covering_source_frame(self):
        self.render_coverage([{'in':.201,'out':.205,'start':.125,'duration_tick':TPS//4,'speeds':(.016,.016)}])

    def test_tiny_reverse_trim_keeps_its_covering_source_frame(self):
        self.render_coverage([{'in':.201,'out':.205,'start':.125,'duration_tick':TPS//4,'reverse':True,'speeds':(.016,.016)}])

    def test_nonzero_leaf_offset_and_parent_trim_use_the_media_clock(self):
        self.render_coverage([self.bezier(out=2.6)],leaf_in=.15,leaf_out=2.95)

    def test_two_partial_reverse_ancestors_keep_real_source_frames(self):
        inner=self.bezier(start=0.)
        span=inner['out']-inner['in'];inner_end=round(reference.elapsed(span,span,'bezier',inner['controls'],inner['speeds'])*TPS)/TPS
        self.render_coverage([inner,{'in':.125,'out':inner_end-.125,'start':.137,'reverse':True,'speeds':(.8,1.4)}])

    def test_aligned_forward_trim_is_a_positive_control(self):
        self.render_coverage([{'in':.25,'out':2.75,'start':.125}])

    def test_no_output_grid_sample_produces_an_empty_video_interval(self):
        self.render_coverage([{'in':.2,'out':18001/TPS,'start_tick':11251,'duration_tick':1}])

    def test_fractional_source_rate_preserves_partial_frame_coverage(self):
        self.render_coverage([self.bezier(out=2.2)],source_fps=Fraction(30000,1001),leaf_out=2.4024)


if __name__=='__main__':unittest.main()
