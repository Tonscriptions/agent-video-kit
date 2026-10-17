"""Native pixels, authoring transactions and exports for independent rasters."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
import wave
from array import array
from unittest.mock import patch

import test_sequence_compositing as _fixtures
import test_tracking_geometry as _tracking
from ai_ad_editor.bindings import compile_binding
from ai_ad_editor.cli import main
from ai_ad_editor.convert import export_external, import_external
from ai_ad_editor.render import render_project
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.validator import validate_project

TPS, W, H = _fixtures.TPS, _fixtures.W, _fixtures.H


class SequenceCanvasTests(unittest.TestCase):
    setUpClass = _fixtures.SequenceCompositingTests.__dict__['setUpClass']
    tearDownClass = _fixtures.SequenceCompositingTests.__dict__['tearDownClass']
    setUp = _fixtures.SequenceCompositingTests.setUp
    call = _fixtures.SequenceCompositingTests.call
    track = _fixtures.SequenceCompositingTests.track
    layer = _fixtures.SequenceCompositingTests.layer
    container = _fixtures.SequenceCompositingTests.container
    render = _fixtures.SequenceCompositingTests.render
    pixel = _fixtures.SequenceCompositingTests.pixel

    def sequence(self, name, canvas=None):
        self.ops.append({'op':'add_sequence', 'id':name, 'duration_tick':TPS,
                         **({'canvas':canvas} if canvas is not None else {})})

    def portrait(self):
        self.sequence('child', {'width':64, 'height':128})
        self.layer('child', 'child_video_1', 'leaf', 'red', crop={'fit':'stretch'})

    def compose(self):
        path=self.base/'changes.json';atomic_write_json(path, {'operations':self.ops})
        return self.call('timeline','compose','--project',self.root,'--input',path)

    def bbox(self, frame):
        mask=frame.point(lambda x: x)
        return mask.getchannel('R').point(lambda x: 255 if x>120 else 0).getbbox()

    def test_portrait_fit_uses_child_geometry_and_transparent_bars(self):
        self.portrait();self.container('child')
        self.track('seq_main','background',-1);self.layer('seq_main','background','green_base','green')
        frames,_,manifest=self.render()
        for im in frames:
            self.assertEqual(self.bbox(im),(56,0,104,96))
            self.pixel(im,(20,48),(0,240,0));self.pixel(im,(80,48),(240,0,0))
        node=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-composite')
        self.assertEqual(node['canvas'],{'width':64,'height':128,'alpha':True})
        self.assertEqual(node['parent_canvas'],{'width':160,'height':96})

    def test_child_anchor_positions_its_own_left_edge(self):
        self.portrait();self.container('child',transform={'anchor':{'x':0,'y':.5},'position':{'x':.5,'y':.5}})
        frames,_,_=self.render()
        for im in frames:self.assertEqual(self.bbox(im),(80,0,128,96))

    def test_animated_child_anchor_retains_original_clock(self):
        self.portrait();self.container('child',keyframes=[{'property':'transform.anchor.x','keyframes':[
            {'at_tick':0,'value':0.,'interpolation':'linear'},
            {'at_tick':TPS//2,'value':1.,'interpolation':'linear'}]}])
        frames,_,_=self.render()
        self.assertEqual(self.bbox(frames[0]),(80,0,128,96))
        self.assertEqual(self.bbox(frames[4]),(32,0,80,96))

    def test_stretch_fills_parent_without_changing_child(self):
        self.portrait();self.container('child',crop={'fit':'stretch'})
        frames,_,_=self.render()
        for im in frames:self.assertEqual(self.bbox(im),(0,0,160,96))

    def test_pixel_crop_uses_native_child_dimensions(self):
        self.sequence('child',{'width':64,'height':128});self.track('child','upper',1)
        self.layer('child','child_video_1','left','red',crop={'fit':'stretch'},mask={'type':'rectangle','x':0.,'y':0.,'width':.5,'height':1.})
        self.layer('child','upper','right','blue',crop={'fit':'stretch'},mask={'type':'rectangle','x':.5,'y':0.,'width':.5,'height':1.})
        self.container('child',crop={'x':32,'y':0,'width':32,'height':128,'fit':'stretch'})
        frames,_,_=self.render()
        for im in frames:
            for xy in ((5,5),(80,48),(154,90)):self.pixel(im,xy,(0,0,240))

    def test_parent_rotation_and_mask_use_separate_coordinate_spaces(self):
        self.portrait();self.container('child',transform={'anchor':{'x':0,'y':.5},'rotation':90.},
            mask={'type':'rectangle','x':.5,'y':0.,'width':.5,'height':1.})
        frames,_,_=self.render()
        for im in frames:
            self.assertEqual(self.bbox(im),(80,48,128,96))
            self.pixel(im,(70,60),(0,0,0));self.pixel(im,(95,60),(240,0,0))

    def test_deep_mixed_rasters_preserve_each_container_geometry(self):
        self.sequence('child',{'width':32,'height':64})
        self.layer('child','child_video_1','leaf','red',crop={'fit':'stretch'},mask={'type':'rectangle','x':0.,'y':0.,'width':.5,'height':1.})
        self.sequence('middle',{'width':96,'height':64});self.container('child',target='middle',id='inner')
        self.container('middle',transform={'rotation':180.})
        frames,_,manifest=self.render()
        for im in frames:
            self.pixel(im,(90,48),(240,0,0));self.pixel(im,(65,48),(0,0,0));self.pixel(im,(110,48),(0,0,0))
        nodes=[v for v in manifest['inputs'] if v.get('kind')=='sequence-composite']
        self.assertEqual({(v['canvas']['width'],v['canvas']['height']) for v in nodes},{(32,64),(96,64)})

    def test_odd_child_raster_is_preserved_inside_even_parent(self):
        self.sequence('child',{'width':65,'height':129})
        self.layer('child','child_video_1','leaf','red',crop={'fit':'stretch'});self.container('child')
        frames,_,manifest=self.render()
        for im in frames:
            self.pixel(im,(80,48),(240,0,0));self.pixel(im,(10,48),(0,0,0))
        node=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-composite')
        self.assertEqual(node['canvas'],{'width':65,'height':129,'alpha':True})

    def test_canvas_does_not_modify_child_audio_samples(self):
        self.portrait();self.container('child')
        path=self.base/'dc.wav'
        with wave.open(str(path),'wb') as h:
            h.setnchannels(2);h.setsampwidth(2);h.setframerate(48000)
            h.writeframes(array('h',[6000,-3000]*48000).tobytes())
        self.call('media','ingest','--project',self.root,'--input',path,'--asset-id','voice')
        self.ops.append({'op':'append_clip','sequence_id':'child','track_id':'child_audio_1','id':'voice_clip','asset_id':'voice',
                         'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':TPS,'duration_tick':TPS})
        self.render()
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(self.root/'renders/result.mkv'),'-map','0:a:0','-f','s16le','pipe:1'],capture_output=True,check=True).stdout
        self.assertEqual(raw,array('h',[6000,-3000]*48000).tobytes())

    def test_selected_sequence_exports_its_own_canvas_and_passes_quality(self):
        self.portrait();self.compose()
        before=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        result=self.call('render','--project',self.root,'--sequence-id','child','--output',self.root/'renders/portrait.mkv')
        self.assertEqual(result['data']['settings']['canvas']['width'],64)
        self.assertEqual(result['data']['settings']['canvas']['height'],128)
        self.call('quality','check','--project',self.root,'--sequence-id','child','--input',self.root/'renders/portrait.mkv')
        after=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(before['settings'],after['settings']);self.assertEqual(before['sequences'],after['sequences'])

    def test_output_override_is_local_to_selected_root(self):
        self.portrait();self.container('child');self.compose()
        result=self.call('render','--project',self.root,'--width','192','--height','128','--output',self.root/'renders/wide.mkv')
        self.assertEqual(result['data']['settings']['canvas']['width'],192)
        manifest=json.loads((self.root/'renders/wide.mkv.manifest.json').read_text(encoding='utf-8'))
        child=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-composite')
        self.assertEqual(child['canvas']['width'],64);self.assertEqual(child['parent_canvas'],{'width':192,'height':128})

    def test_update_and_clear_canvas_are_atomic_and_dry_run_is_read_only(self):
        self.portrait();self.compose()
        old=(self.root/'project.json').read_bytes()
        path=self.base/'update.json';atomic_write_json(path,{'operations':[{'op':'update_sequence','sequence_id':'child',
                            'patch':{'canvas':{'width':128,'height':64},'name':'landscape'}}]})
        self.call('timeline','compose','--project',self.root,'--input',path,'--dry-run')
        self.assertEqual(old,(self.root/'project.json').read_bytes())
        self.call('timeline','compose','--project',self.root,'--input',path)
        child=json.loads((self.root/'project.json').read_text(encoding='utf-8'))['sequences'][1]
        self.assertEqual(child['canvas'],{'width':128,'height':64});self.assertEqual(child['name'],'landscape')
        atomic_write_json(path,{'operations':[{'op':'update_sequence','sequence_id':'child','patch':{'canvas':None}}]})
        self.call('timeline','compose','--project',self.root,'--input',path)
        self.assertIsNone(json.loads((self.root/'project.json').read_text(encoding='utf-8'))['sequences'][1]['canvas'])

    def test_invalid_canvas_rejected_by_builtin_validation_without_schema(self):
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        with patch('ai_ad_editor.validator._schema_report',return_value=([],[],'builtin')):
            for bad in ({},{'width':64},{'width':True,'height':64},{'width':64.,'height':64},{'width':1,'height':64},
                        {'width':8193,'height':64},{'width':'64','height':64},{'width':64,'height':64,'fps':30},[],0):
                with self.subTest(canvas=bad):
                    project['sequences'][0]['canvas']=bad
                    report=validate_project(self.root,project)
                    self.assertTrue(any(v['code']=='SEQUENCE_CANVAS_INVALID' for v in report['errors']),report)

    def test_fill_rotation_can_reveal_previously_offscreen_source(self):
        self.portrait();self.track('child','top_marker',1)
        self.layer('child','top_marker','marker','green',crop={'fit':'stretch'},
                   mask={'type':'rectangle','x':0.,'y':0.,'width':1.,'height':.2})
        self.container('child',crop={'fit':'fill'},transform={'rotation':90.,'scale':.5})
        frames,_,_=self.render()
        for frame in frames:
            self.pixel(frame,(145,48),(0,240,0));self.pixel(frame,(80,48),(240,0,0))
            self.pixel(frame,(80,3),(0,0,0))

    def test_normalized_crop_animation_uses_child_units_and_original_clock(self):
        self.portrait();self.track('child','right_half',1)
        self.layer('child','right_half','right','blue',crop={'fit':'stretch'},
                   mask={'type':'rectangle','x':.5,'y':0.,'width':.5,'height':1.})
        self.container('child',crop={'unit':'normalized','x':0.,'y':0.,'width':.5,'height':1.,'fit':'stretch'},
                       keyframes=[{'property':'crop.x','keyframes':[
                           {'at_tick':0,'value':0.,'interpolation':'linear'},
                           {'at_tick':TPS,'value':.5,'interpolation':'linear'}]}])
        frames,_,_=self.render()
        self.pixel(frames[0],(80,48),(240,0,0));self.pixel(frames[-1],(80,48),(0,0,240))

    def test_inherited_child_uses_project_canvas_not_its_parent_canvas(self):
        self.sequence('child');self.layer('child','child_video_1','leaf','red',crop={'fit':'stretch'})
        self.sequence('middle',{'width':96,'height':160});self.container('child',target='middle',id='inner')
        self.container('middle');frames,_,manifest=self.render()
        for frame in frames:
            self.pixel(frame,(80,48),(240,0,0));self.pixel(frame,(80,10),(0,0,0))
        child=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-composite' and v['sequence_id']=='child')
        self.assertEqual(child['canvas'],{'width':W,'height':H,'alpha':True})
        self.assertEqual(child['parent_canvas'],{'width':96,'height':160})

    def test_odd_selected_output_requires_compatible_pixel_format_before_job(self):
        self.sequence('child',{'width':65,'height':129})
        self.layer('child','child_video_1','leaf','red',crop={'fit':'stretch'});self.compose()
        old=(self.root/'project.json').read_bytes();out=self.root/'renders/odd.mkv';capture=io.StringIO()
        with contextlib.redirect_stdout(capture):
            code=main(list(map(str,('render','--project',self.root,'--sequence-id','child','--pixel-format','yuv420p','--output',out))))
        value=json.loads(capture.getvalue());self.assertEqual(code,2,value)
        self.assertEqual(value['errors'][0]['code'],'OUTPUT_CANVAS_ALIGNMENT_INVALID')
        self.assertFalse(out.exists());self.assertFalse((self.root/'renders/.tmp').exists())
        self.assertEqual(old,(self.root/'project.json').read_bytes())
        self.call('render','--project',self.root,'--sequence-id','child','--pixel-format','yuv444p','--output',out)
        self.assertEqual(self.output_size(out),(65,129))
        out=self.root/'renders/odd-custom.mkv'
        self.call('render','--project',self.root,'--sequence-id','child','--width','67','--height','129',
                  '--pixel-format','yuv444p','--output',out)
        self.assertEqual(self.output_size(out),(67,129))

    def output_size(self,path):
        raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(path)])
        stream=json.loads(raw)['streams'][0];return stream['width'],stream['height']

    def test_selected_explicit_root_override_keeps_grandchild_canvas_and_authoring(self):
        self.sequence('grandchild',{'width':32,'height':64});self.layer('grandchild','grandchild_video_1','leaf','red')
        self.sequence('child',{'width':64,'height':128});self.container('grandchild',target='child',id='inner');self.compose()
        before=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        out=self.root/'renders/selected.mkv'
        self.call('render','--project',self.root,'--sequence-id','child','--width','192','--height','128','--output',out)
        manifest=json.loads(out.with_suffix('.mkv.manifest.json').read_text(encoding='utf-8'))
        node=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-composite')
        self.assertEqual(node['canvas'],{'width':32,'height':64,'alpha':True})
        self.assertEqual(node['parent_canvas'],{'width':192,'height':128});self.assertEqual(self.output_size(out),(192,128))
        after=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(before['settings'],after['settings']);self.assertEqual(before['sequences'],after['sequences'])

    def test_direct_render_api_uses_selected_native_canvas_without_mutation(self):
        self.portrait();self.compose();project=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        before=json.dumps(project,sort_keys=True);out=self.root/'renders/api.mkv'
        render_project(self.root,project,project['sequences'][1],out)
        self.assertEqual(self.output_size(out),(64,128));self.assertEqual(before,json.dumps(project,sort_keys=True))

    def test_invalid_later_sequence_update_rolls_back_entire_operation_batch(self):
        self.portrait();self.compose();old=(self.root/'project.json').read_bytes();ledger=(self.root/'rights-ledger.json').read_bytes()
        for bad in ({'canvas':{'width':True,'height':64}},{'duration_tick':TPS//2}):
            with self.subTest(patch=bad):
                changes=self.base/'invalid.json';atomic_write_json(changes,{'operations':[
                    {'op':'update_sequence','sequence_id':'child','patch':{'name':'must roll back'}},
                    {'op':'update_sequence','sequence_id':'child','patch':bad}]})
                capture=io.StringIO()
                with contextlib.redirect_stdout(capture):
                    code=main(list(map(str,('timeline','compose','--project',self.root,'--input',changes))))
                self.assertNotEqual(code,0,json.loads(capture.getvalue()))
                self.assertEqual(old,(self.root/'project.json').read_bytes());self.assertEqual(ledger,(self.root/'rights-ledger.json').read_bytes())

    def test_queue_and_quality_use_selected_sequence_default_canvas(self):
        self.portrait();self.compose();jobs=self.base/'jobs.json'
        atomic_write_json(jobs,{'jobs':[{'job_id':'portrait','sequence_id':'child','output':'renders/queued.mkv','container':'mkv'}]})
        self.call('queue','enqueue','--project',self.root,'--input',jobs)
        result=self.call('queue','run','--project',self.root,'--job-id','portrait')
        self.assertEqual(result['data']['summary']['succeeded'],1)
        out=self.root/'renders/queued.mkv';self.assertEqual(self.output_size(out),(64,128))
        self.call('quality','check','--project',self.root,'--sequence-id','child','--input',out)

    def test_multiline_text_is_laid_out_in_native_child_before_projection(self):
        self.portrait();self.track('child','titles',1,kind='subtitle')
        self.ops.append({'op':'append_clip','sequence_id':'child','track_id':'titles','id':'title',
                         'generator':{'type':'text'},'source_in_tick':0,'source_out_tick':TPS,
                         'timeline_start_tick':0,'duration_tick':TPS,'subtitle':{'text':'H\nH','style':{
                             'fontsize':16,'fontcolor':'white','box':False,'borderw':0,'shadowx':0,'shadowy':0,
                             'x':'(w-text_w)/2','y':'(h-text_h)/2'}}})
        self.container('child');frames,_,_=self.render()
        out=self.root/'renders/text-child.mkv';self.call('render','--project',self.root,'--sequence-id','child','--output',out)
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(out),'-map','0:v:0','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
        from PIL import Image
        child=Image.frombytes('RGB',(64,128),raw)
        def white_bbox(frame):
            binary=Image.new('L',frame.size)
            binary.putdata([255 if min(frame.getpixel((x,y)))>180 else 0 for y in range(frame.height) for x in range(frame.width)])
            return binary.getbbox()
        native=white_bbox(child);actual=white_bbox(frames[0]);self.assertIsNotNone(native);self.assertIsNotNone(actual)
        expected=(56+native[0]*.75,native[1]*.75,56+native[2]*.75,native[3]*.75)
        for a,b in zip(actual,expected):self.assertLessEqual(abs(a-b),2,(actual,expected))

    def test_external_interchange_preserves_first_sequence_display_dimensions(self):
        self.layer('seq_main','track_video_1','leaf','red',crop={'fit':'stretch'})
        self.sequence('unused',{'width':96,'height':64})
        self.ops.append({'op':'update_sequence','sequence_id':'seq_main','patch':{'canvas':{'width':64,'height':128}}})
        self.compose();project=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        for target,suffix in (('otio','.otio'),('kdenlive-xml','.kdenlive'),('jianying-draft-json','.json')):
            with self.subTest(format=target):
                out=self.base/('export-'+target+suffix);result=export_external(self.root,project,out,target)
                self.assertFalse(result['report_data']['failures'],result)
                if target in {'otio','kdenlive-xml'}:
                    self.assertTrue(any(i['capability']=='sequence-canvas' and i['status']=='Unsupported' for i in result['report_data']['warnings']))
                destination=self.base/('import-'+target);import_external(out,destination)
                self.call('render','--project',destination,'--output',destination/'renders/roundtrip.mp4')
                self.assertEqual(self.output_size(destination/'renders/roundtrip.mp4'),(64,128))

    def test_native_json_and_package_roundtrip_keep_independent_nested_canvas(self):
        self.portrait();self.container('child');self.compose()
        project=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        for target,suffix in (('agent-json','.json'),('package','.zip')):
            with self.subTest(format=target):
                out=self.base/('native-'+target+suffix);export_external(self.root,project,out,target)
                destination=self.base/('native-import-'+target);import_external(out,destination)
                imported=json.loads((destination/'project.json').read_text(encoding='utf-8'))
                self.assertEqual(imported['sequences'][1]['canvas'],{'width':64,'height':128})
                output=destination/'renders/nested.mp4'
                self.call('render','--project',destination,'--output',output)
                self.assertEqual(self.output_size(output),(160,96))


class SequenceCanvasBindingTests(unittest.TestCase):
    setUpClass = _tracking.CanvasBindingTests.__dict__['setUpClass']
    setUp = _tracking.CanvasBindingTests.setUp
    project = _tracking.CanvasBindingTests.project
    save = _tracking.CanvasBindingTests.save
    clips = _tracking.CanvasBindingTests.clips
    bind = _tracking.CanvasBindingTests.bind

    def test_tracking_binding_recompiles_in_authored_sequence_canvas(self):
        project=self.project();sequence=project['sequences'][0];sequence['canvas']={'width':64,'height':128}
        source,_=self.clips(project);source['crop']={'fit':'stretch'};source['transform']={'rotation':90.}
        self.save(project);code,value=self.bind('--apply');self.assertEqual(code,0,value)
        project=self.project();sequence=project['sequences'][0];_,target=self.clips(project)
        track=next(t for t in sequence['tracks'] if t['id']=='titles')
        plan=compile_binding(project,sequence,track,target)
        self.assertEqual(plan['canvas'],{'width':64,'height':128})
        values={k['property']:k['keyframes'][0]['value'] for k in plan['keyframes']}
        self.assertAlmostEqual(values['transform.position.x'],(32+(64-80/180*128))/64,places=6)
        self.assertAlmostEqual(values['transform.position.y'],(64+(90/320*64-32))/128,places=6)


if __name__=='__main__':unittest.main()
