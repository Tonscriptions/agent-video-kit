"""Native pixels for isolated sequence canvases, independent of graph spelling."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image

from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json

TPS, FPS, W, H = 90000, 8, 160, 96


class SequenceCompositingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.fixtures = tempfile.TemporaryDirectory(prefix='sequence-group-sources-')
        cls.sources = Path(cls.fixtures.name)
        for name, color in {'red':(240,0,0), 'blue':(0,0,240), 'green':(0,240,0),
                            'gray':(160,160,160), 'cyan':(0,160,160)}.items():
            Image.new('RGB', (W,H), color).save(cls.sources/f'{name}.png')

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sequence-group-project-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'project'
        self.call('project', 'init', self.root)
        self.ops = []
        self.ingested = set()
        value = json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        value['settings']['canvas'].update(width=W,height=H)
        value['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        value['settings']['output']={'container':'mkv','video':{'codec':'libx264','preset':'ultrafast','crf':0,'pixel_format':'yuv444p'},
                                    'audio':{'codec':'pcm_s16le','bitrate':'192k'}}
        atomic_write_json(self.root/'project.json',value)

    def call(self,*args):
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):
            code=main(list(map(str,args)))
        value=json.loads(capture.getvalue())
        self.assertEqual(code,0,value)
        return value

    def sequence(self,name):
        self.ops.append({'op':'add_sequence','id':name,'duration_tick':TPS})

    def track(self,seq,name,order,kind='video'):
        self.ops.append({'op':'add_track','sequence_id':seq,'track_id':name,'order':order,'kind':kind})

    def layer(self,seq,track,name,color,**extra):
        if color not in self.ingested:
            self.call('media','ingest','--project',self.root,'--input',self.sources/f'{color}.png','--asset-id',color)
            self.ingested.add(color)
        self.ops.append({'op':'append_clip','sequence_id':seq,'track_id':track,'id':name,'asset_id':color,
                         'source_in_tick':0,'source_out_tick':TPS,'timeline_start_tick':0,'duration_tick':TPS,**extra})

    def container(self,child,**extra):
        seq=extra.pop('target','seq_main')
        track=extra.pop('track','track_video_1' if seq=='seq_main' else seq+'_video_1')
        self.ops.append({'op':'append_sequence_clip','sequence_id':seq,'track_id':track,'id':'parent',
                         'nested_sequence_id':child,'source_in_tick':0,'source_out_tick':TPS,
                         'timeline_start_tick':0,'duration_tick':TPS,**extra})

    def two_layers(self,*,child_order=1,first=None,second=None):
        self.sequence('child');self.track('child','child_top',child_order)
        self.layer('child','child_video_1','red_leaf','red',mask={'type':'rectangle','x':0.,'y':0.,'width':.65,'height':1.},**(first or {}))
        self.layer('child','child_top','blue_leaf','blue',mask={'type':'rectangle','x':.35,'y':0.,'width':.65,'height':1.},**(second or {}))

    def render(self,duration=TPS):
        changes=self.base/'changes.json';atomic_write_json(changes,{'operations':self.ops})
        self.call('timeline','compose','--project',self.root,'--input',changes)
        value=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        value['sequences'][0]['duration_tick']=duration
        atomic_write_json(self.root/'project.json',value)
        def snapshot():
            p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
            return (json.dumps({k:p[k] for k in ('settings','sequences','assets')},sort_keys=True),
                    hashlib.sha256((self.root/'rights-ledger.json').read_bytes()).hexdigest())
        before=snapshot()
        out=self.root/'renders/result.mkv'
        result=self.call('render','--project',self.root,'--output',out)
        self.assertEqual(before,snapshot())
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(out),'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout
        frames=[Image.frombytes('RGB',(W,H),raw[i:i+W*H*3]) for i in range(0,len(raw),W*H*3)]
        self.assertEqual(len(frames),round(duration/TPS*FPS))
        manifest=json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8-sig'))
        return frames,result,manifest

    def pixel(self,frame,xy,expected,tolerance=4):
        actual=frame.getpixel(xy)
        self.assertLessEqual(max(abs(a-b) for a,b in zip(actual,expected)),tolerance,(xy,actual,expected))

    def test_parent_opacity_is_applied_after_overlapping_children(self):
        self.two_layers();self.container('child',transform={'opacity':.5})
        frames,result,_=self.render()
        for frame in frames:
            self.pixel(frame,(20,48),(120,0,0));self.pixel(frame,(80,48),(0,0,120))
            self.pixel(frame,(140,48),(0,0,120))
        self.assertFalse(any(w.get('feature')=='nested_sequence_multiple_masks' for w in result['data']['warnings']))

    def test_child_track_order_cannot_escape_parent_track_slot(self):
        self.two_layers(child_order=100);self.container('child')
        self.track('seq_main','root_above',1)
        self.layer('seq_main','root_above','occluder','green')
        frames,_,_=self.render()
        for frame in frames:self.pixel(frame,(80,48),(0,240,0))

    def test_deep_isolation_applies_each_opacity_once(self):
        self.two_layers();self.sequence('middle')
        self.container('child',target='middle',id='inner',transform={'opacity':.5})
        self.container('middle',transform={'opacity':.5})
        frames,_,_=self.render()
        for frame in frames:
            self.pixel(frame,(20,48),(60,0,0));self.pixel(frame,(80,48),(0,0,60))

    def test_parent_pivot_rotates_complete_sequence_canvas(self):
        self.sequence('child')
        self.layer('child','child_video_1','marker','red',mask={'type':'rectangle','x':.2,'y':.4,'width':.1,'height':.2})
        self.container('child',transform={'position':{'x':.5,'y':.5},'anchor':{'x':.25,'y':.5},'rotation':180.})
        frames,result,_=self.render()
        for frame in frames:
            self.pixel(frame,(80,48),(240,0,0));self.pixel(frame,(120,48),(0,0,0))
        self.assertFalse(any(w.get('feature')=='nested_sequence_parent_anchor' for w in result['data']['warnings']))

    def test_parent_mask_uses_post_transform_canvas_coordinates(self):
        self.sequence('child');self.layer('child','child_video_1','leaf','red')
        self.container('child',transform={'position':{'x':.75,'y':.5},'scale':.5},
                       mask={'type':'rectangle','x':.5,'y':0.,'width':.2,'height':1.})
        frames,_,_=self.render()
        for frame in frames:
            self.pixel(frame,(96,48),(240,0,0));self.pixel(frame,(128,48),(0,0,0))

    def test_blend_in_transparent_group_preserves_uncovered_source(self):
        self.sequence('child');self.track('child','upper',1)
        self.layer('child','child_video_1','bottom','gray',mask={'type':'rectangle','x':0.,'y':0.,'width':.65,'height':1.})
        self.layer('child','upper','top','cyan',mask={'type':'rectangle','x':.35,'y':0.,'width':.65,'height':1.},blend={'mode':'multiply'})
        self.container('child')
        frames,_,_=self.render()
        for frame in frames:
            self.pixel(frame,(20,48),(160,160,160));self.pixel(frame,(80,48),(0,100,100))
            self.pixel(frame,(140,48),(0,160,160))

    def test_group_visibility_is_half_open_and_gaps_stay_transparent(self):
        self.sequence('child');self.track('seq_main','background',-1)
        self.layer('seq_main','background','base','green',duration_tick=2*TPS,source_out_tick=2*TPS)
        self.layer('child','child_video_1','first','red',duration_tick=TPS//4,source_out_tick=TPS//4)
        self.layer('child','child_video_1','second','blue',timeline_start_tick=3*TPS//4,duration_tick=TPS//4,source_out_tick=TPS//4)
        self.container('child',timeline_start_tick=TPS//2)
        frames,_,_=self.render(2*TPS)
        colors=[(0,240,0)]*4+[(240,0,0)]*2+[(0,240,0)]*4+[(0,0,240)]*2+[(0,240,0)]*4
        for frame,color in zip(frames,colors):self.pixel(frame,(80,48),color)

    def test_parent_animated_opacity_keeps_phase_across_child_boundary(self):
        self.sequence('child')
        self.layer('child','child_video_1','first','red',duration_tick=TPS//2,source_out_tick=TPS//2)
        self.layer('child','child_video_1','second','blue',timeline_start_tick=TPS//2,duration_tick=TPS//2,source_out_tick=TPS//2)
        self.container('child',keyframes=[{'property':'transform.opacity','keyframes':[{'at_tick':0,'value':.25,'interpolation':'linear'},{'at_tick':TPS,'value':.75,'interpolation':'linear'}]}])
        frames,_,_=self.render()
        for i,frame in enumerate(frames):
            level=round(240*(.25+.5*i/FPS))
            self.pixel(frame,(80,48),(level,0,0) if i<4 else (0,0,level))

    def test_parent_crop_samples_composite_not_each_source_separately(self):
        self.two_layers();self.container('child',crop={'unit':'normalized','x':.25,'y':0.,'width':.5,'height':1.,'fit':'stretch'})
        frames,_,_=self.render()
        for frame in frames:
            self.pixel(frame,(16,48),(240,0,0));self.pixel(frame,(40,48),(0,0,240))
            self.pixel(frame,(128,48),(0,0,240))

    def test_group_manifest_exposes_isolation_and_original_project_survives(self):
        self.two_layers();self.container('child')
        _,_,manifest=self.render()
        # The persisted render plan is the same graph the native process used.
        nodes=[v for v in manifest['inputs'] if v.get('kind')=='sequence-composite']
        self.assertEqual(len(nodes),1);self.assertEqual(nodes[0]['child_layer_count'],2)
        self.assertEqual(nodes[0]['intermediate_files'],0)
        self.assertEqual(nodes[0]['canvas'],{'width':W,'height':H,'alpha':True})

    def test_parent_blur_runs_after_child_masks_and_overlap(self):
        self.two_layers();self.container('child',effects=[{'type':'blur','sigma':2.}])
        frames,_,_=self.render()
        for frame in frames:
            r,g,b=frame.getpixel((55,48))
            self.assertGreater(r,20);self.assertGreater(b,20)
            self.assertLess(r,220);self.assertLess(b,220);self.assertLess(g,4)

    def test_fractional_blend_uses_both_coverages_in_group(self):
        self.sequence('child');self.track('child','upper',1)
        self.layer('child','child_video_1','bottom','gray',transform={'opacity':.5})
        self.layer('child','upper','top','cyan',transform={'opacity':.5},blend={'mode':'multiply'})
        self.container('child')
        frames,_,_=self.render()
        # Against black: .25*Cb + .25*Cs + .25*(Cb*Cs/255).
        for frame in frames:self.pixel(frame,(80,48),(40,105,105),tolerance=5)

    def test_parent_fade_changes_group_coverage_in_authored_clock(self):
        self.two_layers();self.container('child',transition_in={'type':'fade','duration':.5})
        frames,_,_=self.render()
        for i,frame in enumerate(frames):
            level=round(240*min(1,i/FPS/.5))
            self.pixel(frame,(80,48),(0,0,level))

    def test_independent_text_tracks_are_isolated_before_parent_opacity(self):
        self.sequence('child')
        for order in (0,1):
            track=f'titles{order}';self.track('child',track,order,'subtitle')
            self.ops.append({'op':'append_clip','sequence_id':'child','track_id':track,'id':f'text{order}',
                             'generator':{'type':'text'},'source_in_tick':0,'source_out_tick':TPS,'duration_tick':TPS,
                             'subtitle':{'text':'HHH','style':{'fontsize':30,'fontcolor':'white','x':'10','y':'30','box':False,'expansion':'none'}}})
        self.container('child',transform={'opacity':.5})
        frames,_,_=self.render()
        for frame in frames:
            peak=frame.getextrema()[0][1]
            self.assertGreater(peak,120);self.assertLessEqual(peak,130)

    def test_two_instances_keep_internal_transition_labels_separate(self):
        self.sequence('child')
        self.ops.append({'op':'update_track','sequence_id':'child','track_id':'child_video_1','overlap_policy':'allow'})
        self.layer('child','child_video_1','first','red',duration_tick=3*TPS//4,source_out_tick=3*TPS//4)
        self.layer('child','child_video_1','second','blue',timeline_start_tick=TPS//2,duration_tick=TPS//2,
                   source_out_tick=TPS//2,transition_in={'type':'crossfade','duration':.25})
        self.container('child',id='left',transform={'scale':.5,'position':{'x':.25,'y':.5}})
        self.track('seq_main','right',1)
        self.container('child',track='right',id='right_instance',transform={'scale':.5,'position':{'x':.75,'y':.5}})
        frames,_,_=self.render()
        for x in (40,120):
            self.pixel(frames[0],(x,48),(240,0,0));self.pixel(frames[-1],(x,48),(0,0,240))

    def test_grouped_child_dynamic_scale_keeps_fixed_overlay_raster(self):
        self.sequence('child')
        self.layer('child','child_video_1','leaf','red',transform={'scale':.25},keyframes=[
            {'property':'transform.scale','keyframes':[{'at_tick':0,'value':.25,'interpolation':'linear'},
                                                     {'at_tick':TPS,'value':.75,'interpolation':'linear'}]}])
        self.container('child')
        frames,_,_=self.render()
        for i,frame in enumerate(frames):
            present=[x for x in range(W) if frame.getpixel((x,H//2))[0]>120]
            self.assertTrue(present)
            self.assertLessEqual(abs(len(present)-W*(.25+.5*i/FPS)),2.)

    def test_grouped_inline_fade_matches_independent_rgb_coverage_controls(self):
        self.sequence('child')
        self.layer('child','child_video_1','leaf','gray',transform={'scale':.5},keyframes=[
            {'property':'transform.scale','keyframes':[{'at_tick':0,'value':.5,'interpolation':'linear'},
                                                     {'at_tick':TPS,'value':.9,'interpolation':'linear'}]}],
            subtitle={'text':'HHH','style':{'fontsize':30,'fontcolor':'white','x':'10','y':'30','box':False,'expansion':'none'},
                      'animation':{'type':'fade_in','duration':.5}})
        self.container('child')
        faded,result,_=self.render()
        self.assertFalse(any(w.get('feature')=='subtitle_inline_dynamic_alpha' for w in result['data']['warnings']))
        p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        leaf=next(c for s in p['sequences'] for t in s['tracks'] for c in t['clips'] if c['id']=='leaf')
        controls=[]
        for variant in ('plain','blank'):
            if variant=='plain':leaf['subtitle'].pop('animation')
            else:leaf.pop('subtitle')
            atomic_write_json(self.root/'project.json',p)
            path=self.root/f'renders/{variant}.mkv';self.call('render','--project',self.root,'--output',path)
            controls.append(subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout)
        for i,frame in enumerate(faded):
            raw=frame.tobytes();start=i*W*H*3;alpha=min(1,(i/FPS)/.5)
            plain,blank=(v[start:start+W*H*3] for v in controls)
            self.assertGreater(max(abs(a-b) for a,b in zip(plain,blank)),50)
            maximum=max(abs(a-(b+alpha*(c-b))) for a,b,c in zip(raw,blank,plain))
            self.assertLessEqual(maximum,5.,(i,maximum))


if __name__=='__main__':unittest.main()
