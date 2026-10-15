from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ad_editor.animation import keyframe_value
from ai_ad_editor.bindings import compile_binding, make_binding, project_point, validate_project_bindings
from ai_ad_editor.cli import main
from ai_ad_editor.render import _speed_curve_elapsed_seconds, _speed_curve_segments
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, sha256_file


def invoke(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code,json.loads(output.getvalue())


class CoordinateMathTests(unittest.TestCase):
    def test_rectangular_canvas_rotation_uses_pixels_and_anchor(self):
        point={'x':.75,'y':.5,'width':.1}
        mapped=project_point({'transform':{'rotation':90}},point,at_tick=0,crop_tick=0,source_width=400,source_height=200,width=400,height=200)
        self.assertAlmostEqual(mapped['x'],.5)
        self.assertAlmostEqual(mapped['y'],1)
        mapped=project_point({'transform':{'rotation':90,'scale':.5,'anchor':{'x':0,'y':0},'position':{'x':.2,'y':.1}}},{'x':.1,'y':.2,'width':.1},at_tick=0,crop_tick=0,source_width=400,source_height=200,width=400,height=200)
        self.assertAlmostEqual(mapped['x'],.15)
        self.assertAlmostEqual(mapped['y'],.2)

    def test_fit_fill_stretch_and_crop_visibility(self):
        point={'x':.25,'y':.5,'width':.1}
        values={}
        for fit in ('fit','fill','stretch'):
            values[fit]=project_point({'crop':{'unit':'normalized','x':0,'y':0,'width':1,'height':1,'fit':fit}},point,at_tick=0,crop_tick=0,source_width=400,source_height=200,width=200,height=400)
        self.assertAlmostEqual(values['fit']['x'],.25)
        self.assertAlmostEqual(values['fill']['x'],-.5)
        self.assertAlmostEqual(values['stretch']['x'],.25)
        mapped=project_point({'crop':{'unit':'normalized','x':.5,'y':0,'width':.5,'height':1,'fit':'stretch'}},point,at_tick=0,crop_tick=0,source_width=400,source_height=200,width=200,height=400)
        self.assertFalse(mapped['inside_crop'])

    def test_dynamic_crop_local_and_clip_keyframes_and_bezier_timing(self):
        clip={'crop':{'unit':'normalized','x':0,'y':0,'width':.5,'height':1,'fit':'stretch','keyframes':[{'property':'x','keyframes':[{'at_tick':0,'value':0},{'at_tick':100,'value':.5}]}]}}
        mapped=project_point(clip,{'x':.5,'y':.5,'width':.1},at_tick=50,crop_tick=50,source_width=400,source_height=200,width=400,height=200)
        self.assertAlmostEqual(mapped['x'],.5)
        curve={'keyframes':[{'property':'scale','keyframes':[{'at_tick':0,'value':1,'interpolation':'bezier','control_points':[0,0,1,1]},{'at_tick':100,'value':3}]}]}
        self.assertAlmostEqual(keyframe_value(curve,('scale',),1,25),1.5,places=5)
        self.assertAlmostEqual(keyframe_value(curve,('scale',),1,50),2,places=5)


class CanvasBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        from PIL import Image,ImageDraw
        cls.temp=tempfile.TemporaryDirectory(prefix='tracking-geometry-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base=Path(cls.temp.name)
        cls.source=cls.base/'moving.mp4'
        raw=[]
        for index in range(16):
            image=Image.new('RGB',(320,180),'black')
            ImageDraw.Draw(image).rectangle((80+6*index,70,99+6*index,89),fill=(0,255,0))
            raw.append(image.tobytes())
        completed=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','320x180','-r','8','-i','pipe:0','-c:v','libx264','-crf','0','-pix_fmt','yuv444p',str(cls.source)],input=b''.join(raw),capture_output=True)
        assert completed.returncode==0,completed.stderr

    def setUp(self):
        self.root=self.base/self._testMethodName
        self.assertEqual(invoke('project','init',str(self.root))[0],0)
        code,value=invoke('media','ingest','--project',str(self.root),'--input',str(self.source))
        self.assertEqual(code,0,value)
        self.asset=value['data']['asset']['id']
        project=self.project()
        project['settings']['canvas'].update(width=320,height=180)
        project['settings']['timebase']['display_fps']={'num':8,'den':1}
        self.save(project)
        plan=self.root/'operations/compose.json'
        atomic_write_json(plan,{'operations':[{'op':'append_clip','track_id':'track_video_1','id':'video','asset_id':self.asset,'source_in_tick':0,'source_out_tick':180000}, {'op':'add_track','track_id':'titles','kind':'subtitle','order':3}, {'op':'append_clip','track_id':'titles','id':'marker','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':180000,'subtitle':{'text':'+','style':{'fontsize':24,'fontcolor':'red','box':False,'x':'(w-text_w)/2','y':'(h-text_h)/2'}}}]})
        code,value=invoke('timeline','compose','--project',str(self.root),'--input',str(plan))
        self.assertEqual(code,0,value)
        self.tracking={'engine':'local-template-matching','source_sha256':'sha256:'+sha256_file(self.source),'range':{'start_seconds':0,'end_seconds':2},'frames':[{'at_tick':i*11250,'at_seconds':i/8,'x':(90+6*i)/320,'y':80/180,'width':20/320,'height':20/180,'confidence':1} for i in range(16)]}

    def project(self):
        return json.loads((self.root/'project.json').read_text(encoding='utf-8'))

    def save(self,p): atomic_write_json(self.root/'project.json',p)

    def clips(self,p):
        sequence=p['sequences'][0]
        source=next(c for t in sequence['tracks'] for c in t['clips'] if c['id']=='video')
        target=next(c for t in sequence['tracks'] for c in t['clips'] if c['id']=='marker')
        return source,target

    def bind(self,*extra):
        with patch('ai_ad_editor.cli.track_media',return_value=copy.deepcopy(self.tracking)):
            return invoke('media','track-bind','--project',str(self.root),'--asset-id',self.asset,'--source-clip-id','video','--source-track-id','track_video_1','--roi','0,0,1,1','--target-track-id','titles','--target-clip-id','marker',*extra)

    def render(self,name='render.mp4',*extra):
        output=self.root/'renders'/name
        code,value=invoke('render','--project',str(self.root),'--output',str(output),*extra)
        self.assertEqual(code,0,value)
        return output,value

    def distance(self,output,at,width=320,height=180):
        completed=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-ss',str(at),'-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        from PIL import Image
        image=Image.frombytes('RGB',(width,height),completed.stdout)
        green=[];red=[]
        for y in range(height):
            for x in range(width):
                r,g,b=image.getpixel((x,y))
                if g>100 and g>r*1.8 and g>b*1.8: green.append((x,y))
                if r>90 and r>g*1.8 and r>b*1.8: red.append((x,y))
        self.assertTrue(green,(output,at,'green target missing'))
        self.assertTrue(red,(output,at,'red marker missing'))
        center=lambda p:((min(v[0] for v in p)+max(v[0] for v in p))/2,(min(v[1] for v in p)+max(v[1] for v in p))/2)
        a,b=center(green),center(red)
        return math.dist(a,b)

    def test_dry_run_and_plan_are_read_only_and_have_canvas_metadata(self):
        before=(self.root/'project.json').read_bytes()
        code,value=self.bind('--dry-run','--apply')
        self.assertEqual(code,0,value)
        self.assertEqual(value['data']['coordinate_space'],'timeline-canvas-v1')
        code,value=self.bind()
        self.assertEqual(code,0,value)
        self.assertIn('tracking_binding',value['data']['plan'])
        self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_rotated_animated_crop_zoom_anchor_binding_matches_actual_pixels(self):
        p=self.project();source,target=self.clips(p)
        source['crop']={'unit':'normalized','x':.05,'y':.05,'width':.9,'height':.9,'fit':'stretch'}
        source['transform']={'rotation':20,'scale':.8,'anchor':{'x':.4,'y':.6},'position':{'x':.45,'y':.55}}
        source['keyframes']=[{'property':prop,'keyframes':[{'at_tick':0,'value':a,'interpolation':'linear'},{'at_tick':180000,'value':b,'interpolation':'linear'}]} for prop,a,b in [('transform.rotation',20,50),('transform.scale',.8,.95),('crop.width',.9,.7),('crop.x',.05,.12)]]
        self.save(p)
        code,value=self.bind('--scale-mode','roi','--rotation-mode','source','--apply')
        self.assertEqual(code,0,value)
        output,_=self.render()
        for at in (.25,.75,1.25,1.75): self.assertLessEqual(self.distance(output,at),3,(at,output))

    def test_binding_recompiles_after_source_edit_and_portrait_output_override(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        p=self.project();source,target=self.clips(p)
        source['crop']={'unit':'normalized','x':.1,'y':0,'width':.8,'height':1,'fit':'fit'}
        source['transform']={'scale':.9,'position':{'x':.55,'y':.5}}
        self.save(p)
        before=self.project()
        output,_=self.render('portrait.mp4','--profile','custom','--width','180','--height','320')
        self.assertLessEqual(self.distance(output,.75,180,320),3)
        after=self.project()
        self.assertEqual(after['settings'],before['settings'])
        self.assertEqual(after['sequences'],before['sequences'])

    def test_forward_trim_speed_and_reverse_match_real_source_clock(self):
        for reverse in (False,True):
            p=self.project();source,target=self.clips(p)
            source.update(source_in_tick=45000,source_out_tick=180000,duration_tick=67500,speed=2,reverse=reverse,timeline_start_tick=22500)
            target.update(timeline_start_tick=22500,duration_tick=67500,source_out_tick=67500)
            self.save(p)
            code,value=self.bind('--apply');self.assertEqual(code,0,value)
            output,_=self.render('reverse.mp4' if reverse else 'forward.mp4')
            for at in (.375,.625,.875): self.assertLessEqual(self.distance(output,at),3,(reverse,at))

    def test_fill_stretch_and_reflection_match_actual_pixels(self):
        for fit,effect in [('fill','hflip'),('stretch','vflip')]:
            p=self.project();source,target=self.clips(p)
            source['crop']={'unit':'normalized','x':.05,'y':0,'width':.9,'height':1,'fit':fit}
            source['effects']=[{'type':effect}]
            self.save(p)
            code,value=self.bind('--apply');self.assertEqual(code,0,value)
            output,_=self.render(fit+'.mp4')
            self.assertLessEqual(self.distance(output,.75),3,fit)

    def test_cropped_out_subject_hides_marker_and_source_deletion_rolls_back(self):
        p=self.project();source,target=self.clips(p)
        source['crop']={'unit':'normalized','x':.6,'y':0,'width':.4,'height':1,'fit':'stretch'}
        self.save(p)
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        self.assertGreater(value['data']['plan']['hidden_frames'],0)
        output,_=self.render('hidden.mp4')
        raw=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-ss','0.75','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
        self.assertFalse(any(raw[i]>90 and raw[i]>raw[i+1]*1.8 and raw[i]>raw[i+2]*1.8 for i in range(0,len(raw),3)))
        before=(self.root/'project.json').read_bytes()
        changes=self.root/'operations/remove-source.json'
        atomic_write_json(changes,{'operations':[{'op':'remove_clip','track_id':'track_video_1','clip_id':'video'}]})
        code,value=invoke('timeline','compose','--project',str(self.root),'--input',str(changes))
        self.assertEqual(code,2,value)
        self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_external_exports_recompute_binding_and_report_loss(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        p=self.project();source,target=self.clips(p)
        old=copy.deepcopy(target['keyframes'])
        source['transform']={'position':{'x':.6,'y':.5}}
        self.save(p)
        output=self.root/'exports/project.otio'
        code,value=invoke('convert','export','--project',str(self.root),'--target-format','otio','--output',str(output));self.assertEqual(code,0,value)
        payload=json.loads(output.read_text(encoding='utf-8'))
        clips=[c for t in payload['tracks']['children'] for c in t['children'] if c.get('name')=='marker']
        baked=clips[0]['metadata']['ai_ad_editor']['clip']
        self.assertNotIn('tracking_binding',baked)
        self.assertNotEqual(baked['keyframes'],old)
        self.assertIn('tracking-binding',json.dumps(value['data']['report_data']))
        draft=self.root/'exports/draft.json'
        code,value=invoke('convert','export','--project',str(self.root),'--target-format','jianying-draft-json','--output',str(draft));self.assertEqual(code,0,value)
        self.assertTrue(any(x.get('capability')=='tracking-binding' and x.get('status')=='Baked' for x in value['data']['report_data']['items']))
        strict=self.root/'exports/strict.json'
        code,value=invoke('convert','export','--project',str(self.root),'--target-format','jianying-draft-json','--output',str(strict),'--strict')
        self.assertEqual(code,2,value);self.assertFalse(strict.exists())

    def test_speed_curve_and_freeze_have_source_clock_and_visibility(self):
        p=self.project();source,target=self.clips(p)
        source['speed_curve']={'keyframes':[{'at_tick':0,'speed':1,'interpolation':'linear'},{'at_tick':180000,'speed':2}]}
        segments=_speed_curve_segments(source,180000,90000)
        duration=round(_speed_curve_elapsed_seconds(segments,2)*90000)
        source['duration_tick']=target['duration_tick']=duration
        target['source_out_tick']=duration
        self.save(p)
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        output,_=self.render('curve.mp4')
        for at in (.25,.5,.875): self.assertLessEqual(self.distance(output,at),3,at)
        p=self.project();source,target=self.clips(p)
        source.pop('speed_curve')
        source['freeze']={'at_tick':45000,'duration_tick':45000}
        source['duration_tick']=target['duration_tick']=225000
        target['source_out_tick']=225000
        p['sequences'][0]['duration_tick']=225000
        self.save(p)
        output,_=self.render('freeze.mp4')
        for at in (.5,.75,1.25): self.assertLessEqual(self.distance(output,at),3,at)

    def test_non_grid_and_first_frame_freeze_match_rendered_clock(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        for at_tick,hold_tick,name in ((38700,27900,'off-grid'),(0,45000,'first-frame')):
            p=self.project();source,target=self.clips(p)
            source['freeze']={'at_tick':at_tick,'duration_tick':hold_tick}
            source['duration_tick']=target['duration_tick']=180000+hold_tick
            target['source_out_tick']=180000+hold_tick
            p['sequences'][0]['duration_tick']=180000+hold_tick
            self.save(p)
            output,value=self.render(name+'.mp4')
            if name=='off-grid':
                manifest=json.loads(Path(value['data']['manifest']).read_text(encoding='utf-8'))
                self.assertIn('FREEZE_FRAME_QUANTIZED',json.dumps(manifest['warnings']))
            for at in (.125,.5,.75,1,1.25,1.75):
                self.assertLessEqual(self.distance(output,at),3,(name,at))

    def test_missing_source_hash_tampering_cycles_and_nonfinite_are_rejected(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        valid=self.project()
        for change in (lambda b:b.update(source_clip_id='missing'),lambda b:b.update(source_sha256='sha256:'+'0'*64),lambda b:b['observations'][0].update(x=float('nan')),lambda b:b.update(source_clip_id='marker')):
            p=copy.deepcopy(valid);_,target=self.clips(p);change(target['tracking_binding'])
            self.assertTrue(validate_project_bindings(p))
        p=copy.deepcopy(valid);source,target=self.clips(p)
        source['tracking_binding']=copy.deepcopy(target['tracking_binding'])
        source['tracking_binding'].update(source_clip_id='marker',source_track_id='titles')
        target['asset_id']=self.asset
        p['sequences'][0]['tracks'][-1]['kind']='video'
        self.assertTrue(any(e['code']=='TRACK_BIND_CYCLE' for e in validate_project_bindings(p)))

    def test_changed_source_file_blocks_render_before_output(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        project=self.project()
        source=self.root/project['assets'][0]['uri']
        original=source.read_bytes()
        try:
            source.write_bytes(original+b'changed')
            output=self.root/'renders/changed.mp4'
            code,value=invoke('render','--project',str(self.root),'--output',str(output))
            self.assertEqual(code,2,value);self.assertFalse(output.exists())
        finally:
            source.write_bytes(original)

    def test_package_round_trip_retains_binding_and_can_render(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        bundle=self.root/'exports/binding.aevpkg.zip'
        code,value=invoke('convert','export','--project',str(self.root),'--target-format','package','--output',str(bundle));self.assertEqual(code,0,value)
        imported=self.root/'imported'
        code,value=invoke('convert','import','--input',str(bundle),'--output',str(imported));self.assertEqual(code,0,value)
        self.root=imported
        output,_=self.render('imported.mp4')
        self.assertLessEqual(self.distance(output,.75),3)

    def test_clearing_binding_via_timeline_keeps_baked_keyframes(self):
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        before=self.clips(self.project())[1]['keyframes']
        changes=self.root/'operations/unbind.json'
        atomic_write_json(changes,{'operations':[{'op':'update_clip','track_id':'titles','clip_id':'marker','patch':{'tracking_binding':None}}]})
        code,value=invoke('timeline','compose','--project',str(self.root),'--input',str(changes));self.assertEqual(code,0,value)
        target=self.clips(self.project())[1]
        self.assertIsNone(target.get('tracking_binding'))
        self.assertEqual(target['keyframes'],before)

    def test_dense_frame_binding_renders_with_bounded_expression_depth(self):
        p=self.project();source,target=self.clips(p)
        p['settings']['canvas'].update(width=160,height=90)
        p['settings']['timebase']['display_fps']={'num':120,'den':1}
        source['keyframes']=[{'property':'transform.rotation','keyframes':[{'at_tick':0,'value':10,'interpolation':'linear'},{'at_tick':180000,'value':50,'interpolation':'linear'}]}]
        self.save(p)
        code,value=self.bind('--apply');self.assertEqual(code,0,value)
        self.assertEqual(value['data']['plan']['sampled_frames'],241)
        self.assertGreater(len(value['data']['plan']['keyframes'][0]['keyframes']),200)
        output,value=self.render('dense.mp4')
        self.assertEqual(value['data']['filter_graph_transport']['mode'],'local-file')
        self.assertGreater(output.stat().st_size,1000)


if __name__=='__main__': unittest.main()
