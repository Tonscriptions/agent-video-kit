"""Rendered pixels and pre-allocation rejection for sequence projection sampling."""
from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from PIL import Image

import test_sequence_canvas as _canvas
import test_sequence_compositing as _fixture
from ai_ad_editor.cli import main
from ai_ad_editor.convert import export_external, import_external
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.validator import validate_project

TPS, FPS, W, H = 90000, 8, 160, 96


class SequenceSamplingTests(unittest.TestCase):
    setUpClass = _fixture.SequenceCompositingTests.__dict__['setUpClass']
    tearDownClass = _fixture.SequenceCompositingTests.__dict__['tearDownClass']
    setUp = _fixture.SequenceCompositingTests.setUp
    call = _fixture.SequenceCompositingTests.call
    track = _fixture.SequenceCompositingTests.track
    layer = _fixture.SequenceCompositingTests.layer
    container = _fixture.SequenceCompositingTests.container
    sequence = _canvas.SequenceCanvasTests.sequence
    compose = _canvas.SequenceCanvasTests.compose
    pixel = _fixture.SequenceCompositingTests.pixel

    def project(self):
        return json.loads((self.root/'project.json').read_text(encoding='utf-8'))

    def config(self, value):
        p = self.project();p['settings']['sequence_sampling'] = value
        atomic_write_json(self.root/'project.json', p)

    def invoke(self, *args):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            code = main(list(map(str, args)))
        return code, json.loads(capture.getvalue())

    def pattern(self, size=(480,288), kind='gray', **container):
        self.image = Image.new('RGBA', size)
        def color(x, y):
            if kind == 'gray':return ((255 if x % 3 == 2 else 0),)*3+(255,)
            if kind.startswith('alpha'):
                return (240,0,0,255) if x % 3 == 2 else ((0,255,0,0) if kind=='alpha_green' else (0,0,0,0))
            return ((x % 5)*55, (y % 7)*35, ((x+y) % 3)*120, 255)
        self.image.putdata([color(x,y) for y in range(size[1]) for x in range(size[0])])
        # Per-project source avoids modifying the shared class fixture directory.
        path = self.base/(kind+'.png');self.image.save(path)
        self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','pattern')
        self.sequence('child', {'width':size[0],'height':size[1]})
        self.ops.append({'op':'append_clip','sequence_id':'child','track_id':'child_video_1',
                         'id':'texture','asset_id':'pattern','source_in_tick':0,'source_out_tick':TPS,
                         'timeline_start_tick':0,'duration_tick':TPS,'crop':{'fit':'stretch'}})
        self.container('child', **container);self.compose()

    def decode(self, path):
        raw = subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0',
                                       '-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
        self.assertEqual(len(raw), W*H*3*FPS)
        return [Image.frombytes('RGB',(W,H),raw[i:i+W*H*3]) for i in range(0,len(raw),W*H*3)]

    def output(self, name='area', *overrides):
        before = self.project();out = self.root/'renders'/(name+'.mkv')
        result = self.call('render','--project',self.root,'--output',out,*overrides)
        after = self.project()
        for key in ('settings','sequences','assets'):self.assertEqual(before[key],after[key])
        manifest = json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8'))
        return self.decode(out), manifest, result

    def expected(self, xy, *, crop=None, scale=1., rotation=0., anchor=(.5,.5), position=(.5,.5)):
        """Independent cell-overlap integration; no FFmpeg prefix sums or graph expressions."""
        sw,sh = self.image.size
        cx,cy,cw,ch = crop or (0.,0.,float(sw),float(sh))
        # All numerical-oracle test containers request stretch explicitly.
        fitx,fity = W/cw,H/ch
        a = math.radians(rotation);dx=xy[0]+.5-position[0]*W;dy=xy[1]+.5-position[1]*H
        sx=cx+anchor[0]*cw+(dx*math.cos(a)+dy*math.sin(a))/(scale*fitx)
        sy=cy+anchor[1]*ch+(-dx*math.sin(a)+dy*math.cos(a))/(scale*fity)
        fw,fh=max(1.,1/(abs(scale)*fitx)),max(1.,1/(abs(scale)*fity))
        left,right=max(cx,sx-fw/2),min(cx+cw,sx+fw/2)
        top,bottom=max(cy,sy-fh/2),min(cy+ch,sy+fh/2)
        values=[0.,0.,0.]
        for y in range(max(0,math.floor(top)),min(sh,math.ceil(bottom))):
            for x in range(max(0,math.floor(left)),min(sw,math.ceil(right))):
                weight=max(0.,min(right,x+1)-max(left,x))*max(0.,min(bottom,y+1)-max(top,y))/(fw*fh)
                rgba=self.image.getpixel((x,y))
                for c in range(3):values[c]+=rgba[c]*(rgba[3]/255)*weight
        return tuple(round(v) for v in values)

    def assert_reference(self, frames, **parameters):
        points=[(0,0),(1,1),(159,95),(158,94),(25,17),(43,32),(80,48),(122,67),(151,83)]
        for frame in frames:
            for xy in points:self.pixel(frame,xy,self.expected(xy,**parameters),tolerance=3)

    def test_three_pixel_stripes_preserve_their_area_mean(self):
        self.pattern(crop={'fit':'stretch'});self.config({'method':'area'})
        frames,manifest,_=self.output()
        for frame in frames:
            for xy in ((5,5),(80,48),(154,90)):self.pixel(frame,xy,(85,85,85),tolerance=2)
        node=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-composite')
        self.assertEqual(node['spatial_sampler'],'native-premultiplied-area-once')

    def test_anisotropic_color_minification_matches_cell_overlap(self):
        self.pattern((480,192),'color',crop={'fit':'stretch'});self.config({'method':'area'})
        frames,_,_=self.output();self.assert_reference(frames)

    def test_fractional_crop_uses_fractional_pixel_edges(self):
        crop=(48.48,14.4,321.6,195.84)
        self.pattern(kind='color',crop={'unit':'normalized','x':.101,'y':.05,'width':.67,'height':.68,'fit':'stretch'})
        self.config({'method':'area'});frames,_,_=self.output();self.assert_reference(frames,crop=crop)

    def test_animated_crop_and_scale_keep_author_clock(self):
        keys=[{'property':'crop.x','keyframes':[{'at_tick':0,'value':0.,'interpolation':'linear'},
                  {'at_tick':TPS,'value':.25,'interpolation':'linear'}]},
              {'property':'transform.scale','keyframes':[{'at_tick':0,'value':.7,'interpolation':'linear'},
                  {'at_tick':TPS,'value':1.3,'interpolation':'linear'}]}]
        self.pattern(kind='color',crop={'unit':'normalized','x':0.,'y':.05,'width':.65,'height':.8,'fit':'stretch'},keyframes=keys)
        self.config({'method':'area'});frames,_,_=self.output()
        for i,frame in enumerate(frames):
            self.assert_reference([frame],crop=(480*.25*i/FPS,14.4,312.,230.4),scale=.7+.6*i/FPS)

    def test_quarter_turn_and_noncentral_anchor(self):
        self.pattern(kind='color',crop={'fit':'stretch'},transform={'rotation':90.,'anchor':{'x':.2,'y':.6}})
        self.config({'method':'area'});frames,_,_=self.output()
        self.assert_reference(frames,rotation=90.,anchor=(.2,.6))

    def test_general_rotation_uses_declared_source_axis_kernel(self):
        self.pattern(kind='color',crop={'fit':'stretch'},transform={'rotation':17.,'scale':.8})
        self.config({'method':'area'});frames,_,_=self.output()
        self.assert_reference(frames,rotation=17.,scale=.8)

    def test_hidden_transparent_color_does_not_tint_area_average(self):
        self.pattern(kind='alpha_green',crop={'fit':'stretch'});self.config({'method':'area'})
        first,_,_=self.output('hidden-green')
        for frame in first:self.pixel(frame,(80,48),(80,0,0),tolerance=2)
        raw=self.image.tobytes()
        self.image.putdata([(raw[i],0,raw[i+2],raw[i+3]) for i in range(0,len(raw),4)])
        path=self.base/'hidden-black.png';self.image.save(path)
        self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','black_hidden')
        p=self.project();p['sequences'][1]['tracks'][0]['clips'][0]['asset_id']='black_hidden'
        atomic_write_json(self.root/'project.json',p)
        second,_,_=self.output('hidden-black')
        self.assertEqual([f.tobytes() for f in first],[f.tobytes() for f in second])

    def test_same_canvas_shrink_also_selects_area_sampling(self):
        self.pattern((W,H),crop={'fit':'stretch'},transform={'scale':1/3})
        self.config({'method':'area'});frames,_,_=self.output()
        self.assert_reference(frames,scale=1/3)

    def test_omitted_and_explicit_bilinear_are_pixel_compatible(self):
        self.pattern(crop={'fit':'stretch'})
        first,_,_=self.output('default');self.config({'method':'bilinear'})
        second,_,_=self.output('bilinear')
        self.assertEqual([f.tobytes() for f in first],[f.tobytes() for f in second])

    def test_area_identity_retains_native_pixel_values(self):
        self.pattern((W,H),'color',crop={'fit':'stretch'});self.config({'method':'area'})
        frames,_,_=self.output();self.assert_reference(frames)

    def test_invalid_sampling_rejected_by_builtin_and_schema(self):
        project=self.project()
        for bad in ([],False,{'method':'cubic'},{'method':False},{'max_working_bytes':True},
                    {'max_working_bytes':1.5},{'max_working_bytes':'100'}, {'max_working_bytes':0},
                    {'max_working_bytes':68719476737},{'quality':'best'}):
            with self.subTest(value=bad):
                project['settings']['sequence_sampling']=bad
                with patch('ai_ad_editor.validator._schema_report',return_value=([],[],'builtin')):
                    report=validate_project(self.root,project)
                self.assertTrue(any(e['code']=='SEQUENCE_SAMPLING_INVALID' for e in report['errors']),report)
        from jsonschema import Draft202012Validator
        schema=json.loads((Path(__file__).resolve().parents[2]/'docs/specs/agent-project.schema.json').read_text(encoding='utf-8'))
        project['settings']['sequence_sampling']={'method':'unknown'}
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(project)))

    def test_budget_rejection_precedes_ffmpeg_and_job_allocation(self):
        self.pattern(crop={'fit':'stretch'});self.config({'method':'area','max_working_bytes':1})
        before=(self.root/'project.json').read_bytes();operations=sorted((self.root/'operations').glob('*.json'))
        for extra in ((),('--dry-run',)):
            with self.subTest(extra=extra),patch('ai_ad_editor.render.run_process',side_effect=AssertionError('FFmpeg must not run')):
                code,result=self.invoke('render','--project',self.root,'--output',self.root/'renders/rejected.mkv',*extra)
                self.assertEqual(code,2,result);self.assertEqual(result['errors'][0]['code'],'SEQUENCE_PROJECTION_BUDGET_EXCEEDED')
        self.assertEqual(before,(self.root/'project.json').read_bytes())
        self.assertEqual(operations,sorted((self.root/'operations').glob('*.json')))
        self.assertFalse((self.root/'renders/rejected.mkv').exists());self.assertFalse((self.root/'renders/.tmp').exists())

    def test_extreme_cross_aspect_canvas_is_rejected_without_large_arrays(self):
        self.sequence('child',{'width':8192,'height':2});self.layer('child','child_video_1','leaf','red')
        self.container('child');self.compose();project=self.project()
        project['sequences'][0]['canvas']={'width':2,'height':8192};atomic_write_json(self.root/'project.json',project)
        with patch('ai_ad_editor.render.run_process',side_effect=AssertionError('FFmpeg must not run')):
            code,value=self.invoke('render','--project',self.root,'--dry-run')
        self.assertEqual(code,2,value);self.assertEqual(value['errors'][0]['code'],'SEQUENCE_PROJECTION_BUDGET_EXCEEDED')
        self.assertFalse((self.root/'renders/.tmp').exists())

    def test_exact_budget_and_repeated_references_are_accounted_separately(self):
        self.pattern(crop={'fit':'stretch'})
        self.ops=[]
        self.track('seq_main','again_track',1);self.container('child',track='again_track',id='again_clip');self.compose()
        # 2 native RGBA source + 4 parent RGBA + 3 float/2 byte work + 4 double SAT planes, per execution node.
        expected=2*(480*288*8+W*H*16+480*288*88)
        self.config({'method':'area','max_working_bytes':expected})
        plan=self.call('render','--project',self.root,'--dry-run')['data']['plan']
        meta=next(x for x in plan['inputs'] if x.get('kind')=='sequence-projection-budget')
        self.assertEqual(meta['estimated_working_bytes'],expected);self.assertEqual(len(meta['nodes']),2)
        self.config({'method':'area','max_working_bytes':expected-1})
        code,value=self.invoke('render','--project',self.root,'--dry-run')
        self.assertEqual(code,2,value)

    def test_unused_large_sequence_is_not_charged_to_root(self):
        self.sequence('unused',{'width':8192,'height':8192})
        self.layer('seq_main','track_video_1','base','red');self.compose()
        self.config({'method':'area','max_working_bytes':1})
        _,manifest,_=self.output()
        quota=next(x for x in manifest['inputs'] if x.get('kind')=='sequence-projection-budget')
        self.assertEqual(quota['estimated_working_bytes'],0);self.assertEqual(quota['nodes'],[])

    def test_cli_quality_fingerprints_and_author_settings(self):
        self.pattern(crop={'fit':'stretch'});before=self.project()
        frames,manifest,result=self.output('override','--sequence-sampling','area','--sequence-memory-mib','32')
        self.pixel(frames[0],(80,48),(85,85,85),tolerance=2)
        self.assertEqual(result['data']['settings']['sequence_sampling'],{'method':'area','max_working_bytes':32*1024*1024})
        self.assertEqual(before['settings'],self.project()['settings'])
        self.call('quality','golden','--project',self.root,'--mode','capture','--input',self.root/'renders/override.mkv',
                  '--sequence-sampling','area','--sequence-memory-mib','32')
        self.call('quality','check','--project',self.root,'--input',self.root/'renders/override.mkv',
                  '--sequence-sampling','area','--sequence-memory-mib','32')
        plain=self.call('render','--project',self.root,'--dry-run')['data']['plan']
        self.assertNotEqual(plain['project_fingerprint'],result['data']['project_fingerprint'])

    def test_queue_persists_and_executes_area_override(self):
        self.pattern(crop={'fit':'stretch'});path=self.base/'queue.json'
        atomic_write_json(path,{'job_id':'area','container':'mkv','output':'renders/queued.mkv',
                                'sequence_sampling':'area','sequence_memory_mib':32})
        value=self.call('queue','enqueue','--project',self.root,'--input',path)
        self.assertEqual(value['data']['jobs'][0]['sequence_sampling'],'area')
        value=self.call('queue','run','--project',self.root,'--job-id','area')
        self.assertEqual(value['data']['summary']['succeeded'],1,value)
        for frame in self.decode(self.root/'renders/queued.mkv'):self.pixel(frame,(80,48),(85,85,85),tolerance=2)

    def test_quality_overrides_reject_invalid_author_configuration_read_only(self):
        for bad in (['invalid'],False,{'method':'unknown'},{'max_working_bytes':True}):
            self.config(bad);before=(self.root/'project.json').read_bytes()
            for action in ('check','golden'):
                with self.subTest(config=bad,action=action):
                    extra=('--mode','capture') if action=='golden' else ()
                    code,value=self.invoke('quality',action,'--project',self.root,'--input',self.sources/'red.png',
                                           '--sequence-sampling','area','--dry-run',*extra)
                    self.assertEqual(code,2,value)
                    self.assertEqual(value['errors'][0]['code'],'SEQUENCE_SAMPLING_INVALID')
                    self.assertEqual(before,(self.root/'project.json').read_bytes())

    def test_queue_rejects_malformed_sampling_atomically(self):
        path=self.base/'queue.json';before=(self.root/'project.json').read_bytes()
        for bad in ({'sequence_sampling':'cubic'},{'sequence_sampling':False},{'sequence_memory_mib':True},
                    {'sequence_memory_mib':1.5},{'sequence_memory_mib':0},{'sequence_memory_mib':65537}):
            with self.subTest(bad=bad):
                atomic_write_json(path,{'job_id':'bad',**bad})
                code,value=self.invoke('queue','enqueue','--project',self.root,'--input',path)
                self.assertEqual(code,2,value)
        self.assertEqual(before,(self.root/'project.json').read_bytes())

    def test_cancel_resume_retains_area_and_rejects_changed_override(self):
        self.pattern(crop={'fit':'stretch'});cancel=self.base/'cancel.flag';cancel.write_text('cancel',encoding='utf-8')
        code,value=self.invoke('render','--project',self.root,'--output',self.root/'renders/resumed.mkv',
                               '--sequence-sampling','area','--sequence-memory-mib','32','--cancel-file',cancel)
        self.assertEqual(code,8,value);operation=value['operation_id'];cancel.unlink()
        code,value=self.invoke('render','--project',self.root,'--resume',operation,'--sequence-sampling','bilinear')
        self.assertEqual(code,2,value);self.assertEqual(value['errors'][0]['code'],'RESUME_INPUT_CHANGED')
        value=self.call('render','--project',self.root,'--resume',operation)
        self.assertEqual(value['data']['settings']['sequence_sampling']['method'],'area')
        self.pixel(self.decode(self.root/'renders/resumed.mkv')[0],(80,48),(85,85,85),tolerance=2)

    def test_native_exchange_retains_sampling_external_reports_loss(self):
        self.pattern(crop={'fit':'stretch'});self.config({'method':'area','max_working_bytes':32*1024*1024})
        project=self.project()
        for fmt,suffix in (('agent-json','.json'),('package','.zip')):
            with self.subTest(format=fmt):
                out=self.base/(fmt+suffix);export_external(self.root,project,out,fmt)
                destination=self.base/('import-'+fmt);import_external(out,destination)
                p=json.loads((destination/'project.json').read_text(encoding='utf-8'))
                self.assertEqual(p['settings']['sequence_sampling'],project['settings']['sequence_sampling'])
        for fmt,suffix in (('otio','.otio'),('kdenlive-xml','.kdenlive'),('jianying-draft-json','.json')):
            with self.subTest(format=fmt):
                value=export_external(self.root,project,self.base/(fmt+suffix),fmt)
                self.assertTrue(any(x['capability']=='sequence-sampling' and x['status']=='Unsupported'
                                    for x in value['report_data']['warnings']),value)


if __name__=='__main__':unittest.main()
