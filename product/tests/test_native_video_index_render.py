"""Actual render/preview reuse and publication boundaries for native indexes."""
from bisect import bisect_left
import copy
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_ad_editor import native_video_index as index
from ai_ad_editor import reverse_video_clock as clock
from ai_ad_editor import render as renderer
from ai_ad_editor import preview
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import save_project
import test_cfr_boundaries as helpers


def indexes(value):
    if isinstance(value,dict):
        if item:=value.get('native_frame_index'):yield item
        for child in value.values():yield from indexes(child)
    elif isinstance(value,list):
        for child in value:yield from indexes(child)


class NativeVideoIndexRenderTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp
    run_native=helpers.CFRBoundaryTests.run_native
    source=helpers.CFRBoundaryTests.source
    project=helpers.CFRBoundaryTests.project

    def manifest(self,result):return json.loads(Path(result['manifest']).read_bytes())

    def decode(self,path):
        return self.run_native([ffmpeg_path(),'-v','error','-i',path,'-map','0:v:0',
            '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'])

    def test_actual_second_render_uses_no_source_frame_probe(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        with patch.object(clock,'probe_frames',wraps=clock.probe_frames) as probe:
            first=renderer.render_project(self.root,p,s,self.root/'renders/first.mp4')
        self.assertEqual(probe.call_count,1)
        first_items=list(indexes(self.manifest(first)['inputs']))
        self.assertEqual(sum(item['source_index_decode_calls'] for item in first_items),1)
        directory=Path(first_items[0]['path']);before={x.name:x.read_bytes() for x in directory.iterdir()}
        with patch.object(clock,'probe_frames',side_effect=AssertionError('repeated full source frame probe')):
            second=renderer.render_project(self.root,p,s,self.root/'renders/second.mp4')
        second_items=list(indexes(self.manifest(second)['inputs']))
        self.assertTrue(second_items)
        self.assertTrue(all(item['source_index_decode_calls']==0 for item in second_items))
        self.assertEqual(self.decode(first['path']),self.decode(second['path']))
        self.assertEqual(before,{x.name:x.read_bytes() for x in directory.iterdir()})
        self.assertTrue(any(item.get('post_render_verification') for item in second_items))

    def test_dry_run_probes_readonly_then_actual_render_persists(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        planned=renderer.render_project(self.root,p,s,self.root/'renders/dry.mp4',dry_run=True)
        self.assertEqual(planned['status'],'planned')
        self.assertFalse((self.root/'cache/native-video-index').exists())
        result=renderer.render_project(self.root,p,s,self.root/'renders/actual.mp4')
        self.assertEqual(result['status'],'succeeded')
        self.assertEqual(len(list((self.root/'cache/native-video-index').iterdir())),1)

    def test_changed_preview_range_uses_index_without_source_probe(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        first=preview.preview_project(self.root,p,s,request=preview.plan(p,s,start_frame=2,end_frame=30,height=64))
        with patch.object(clock,'probe_frames',side_effect=AssertionError('preview must reuse native index')):
            second=preview.preview_project(self.root,p,s,request=preview.plan(p,s,start_frame=3,end_frame=30,height=64))
        self.assertFalse(second['cache_hit'])
        self.assertEqual(self.decode(first['master'])[helpers.W*helpers.H*4:],self.decode(second['master']))

    def test_VFR_fractional_source_preview_matches_independent_all_frame_oracle(self):
        points=[0,33,101,188,195,441,499,800,1002,1221,1600,1800]
        source,colors,times=self.source(count=len(points),vfr=points)
        start,source_in,source_out=2970,10170,100170
        speed=Fraction(3,2);duration=60000
        p,s,_=self.project(source,start=start,duration=duration,source_in=source_in,source_out=source_out,
                           patch={'reverse':True,'speed':float(speed)})
        before=copy.deepcopy(p)
        request=preview.plan(p,s,start_frame=0,end_frame=45,height=64)
        actual=preview.preview_project(self.root,p,s,request=request)
        expected=[]
        for frame in range(45):
            now=Fraction(frame*1001,30000);color=(0,0,0,255)
            if Fraction(start,90000)<=now<Fraction(start+duration,90000):
                source_time=Fraction(source_out,90000)-(now-Fraction(start,90000))*speed
                color=colors[max(0,bisect_left(times,source_time)-1)]
            expected.append(bytes(color)*(helpers.W*helpers.H))
        self.assertEqual(self.decode(actual['master']),b''.join(expected))
        self.assertEqual(p,before)

    def test_clip_windows_share_one_readonly_source_probe(self):
        source,_,_=self.source();p,s,clip=self.project(source,start=0,duration=45000,source_out=45000,
                                                     patch={'reverse':True})
        second={**clip,'id':'second','timeline_start_tick':45000}
        s['tracks'][0]['clips'].append(second);save_project(self.root,p)
        with patch.object(clock,'probe_frames',wraps=clock.probe_frames) as probe:
            _,_,metadata,_=renderer.build_filter_graph(self.root,p,s)
        self.assertEqual(probe.call_count,1)
        items=list(indexes(metadata));self.assertEqual(len(items),2)
        self.assertEqual(sorted(item['source_index_decode_calls'] for item in items),[0,1])
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_chunk_cache_and_frame_index_both_hit_on_second_render(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        with patch.object(clock,'MAX_SELECTED_BUFFER_BYTES',2*helpers.W*helpers.H*16):
            renderer.render_project(self.root,p,s,self.root/'renders/first.mp4')
            with patch.object(clock,'probe_frames',side_effect=AssertionError('source index decode repeated')):
                result=renderer.render_project(self.root,p,s,self.root/'renders/second.mp4')
        data=self.manifest(result)
        jobs=[item['reverse_cache'] for item in data['inputs'] if 'reverse_cache' in item]
        self.assertTrue(jobs)
        self.assertTrue(all(job['execution']['status']=='cache-hit' for job in jobs))
        self.assertTrue(all(job['execution']['new_source_decodes']==0 for job in jobs))
        self.assertTrue(all(item['source_index_decode_calls']==0 for item in indexes(data['inputs'])))

    def test_changed_index_during_render_blocks_final_output(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        real=renderer.run_process
        def mutate(*args,**kwargs):
            result=real(*args,**kwargs)
            for file in (self.root/'cache/native-video-index').glob('*/pts.i64le'):
                file.write_bytes(file.read_bytes()+b'changed')
            return result
        output=self.root/'renders/rejected.mp4'
        with patch.object(renderer,'run_process',side_effect=mutate):
            with self.assertRaises(AppError) as caught:renderer.render_project(self.root,p,s,output)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_CORRUPT')
        self.assertFalse(output.exists())

    def test_deleted_index_during_preview_blocks_preview_publication(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        real=preview.run_process
        def remove(*args,**kwargs):
            result=real(*args,**kwargs)
            for file in (self.root/'cache/native-video-index').glob('*/durations.i64le'):file.unlink()
            return result
        with patch.object(preview,'run_process',side_effect=remove):
            with self.assertRaises(AppError):
                preview.preview_project(self.root,p,s,request=preview.plan(p,s,start_frame=2,end_frame=20,height=64))
        self.assertFalse(list((self.root/'cache/timeline-preview').glob('*/preview.json')))

    def test_cancel_before_index_decode_does_not_publish_index_or_output(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        marker=self.work/'cancel';marker.write_text('cancel',encoding='utf8')
        with patch.object(clock,'probe_frames',side_effect=AssertionError('cancelled source must not decode')):
            with self.assertRaises(AppError) as caught:
                renderer.render_project(self.root,p,s,self.root/'renders/cancelled.mp4',cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_forward_render_does_not_build_native_index(self):
        source,_,_=self.source();p,s,_=self.project(source)
        with patch.object(clock,'probe_frames',side_effect=AssertionError('forward index is unnecessary')):
            result=renderer.render_project(self.root,p,s,self.root/'renders/forward.mp4')
        self.assertEqual(result['status'],'succeeded')
        self.assertFalse((self.root/'cache/native-video-index').exists())


if __name__=='__main__':unittest.main()
