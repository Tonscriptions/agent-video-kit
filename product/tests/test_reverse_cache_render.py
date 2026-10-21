"""Exercise native chunk fallback through render, preview and source orientation."""
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor import reverse_cache as cache
from ai_ad_editor import reverse_video_clock as clock
from ai_ad_editor import render as renderer
from ai_ad_editor import preview
import test_cfr_boundaries as helpers
import test_reverse_video_clock as reverse_helpers


class ReverseChunkRenderTests(unittest.TestCase):
    run_native=helpers.CFRBoundaryTests.run_native
    source=helpers.CFRBoundaryTests.source
    project=helpers.CFRBoundaryTests.project
    assert_reverse=reverse_helpers.ReverseVideoClockTests.assert_reverse

    def setUp(self):
        helpers.CFRBoundaryTests.setUp(self)
        self.addCleanup(patch.stopall)
        patch.object(clock,'MAX_SELECTED_BUFFER_BYTES',2*helpers.W*helpers.H*16).start()

    def render(self,project,sequence):
        result=renderer.render_project(self.root,project,sequence,self.root/'renders/actual.mp4')
        manifest=json.loads(Path(result['manifest']).read_bytes())
        self.assertEqual(result['status'],'succeeded')
        jobs=[row['reverse_cache'] for row in manifest['inputs'] if 'reverse_cache' in row]
        self.assertTrue(jobs)
        self.assertTrue(all(j['post_render_verification']['status']=='cache-hit' for j in jobs))
        return helpers.CFRBoundaryTests.render(self,project,sequence)

    def test_render_VFR_speed_retains_independent_source_intervals(self):
        self.assert_reverse(vfr=[0,33,101,188,195,441,499,800,1002,1221,1600,1800],
            source_in=10170,source_out=100170,speed=Fraction(3,2))

    def test_render_nonlinear_speed_matches_independent_decimal_inverse(self):
        self.assert_reverse(vfr=[0,33,101,188,195,441,499,800,1002,1221,1600,1800],
            source_in=10170,source_out=100170,curve=True)

    def test_render_partial_alpha_matches_independent_composite(self):
        self.assert_reverse(vfr=[0,33,101,188,195,441,499,800,1002,1221,1600,1800],
            source_in=10170,source_out=100170,alpha=True)

    def test_dry_run_does_not_materialize_and_second_render_hits_cache(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        result=renderer.render_project(self.root,p,s,self.root/'renders/dry.mp4',dry_run=True)
        self.assertEqual(result['status'],'planned')
        self.assertFalse((self.root/'cache/reverse-video').exists())
        first=renderer.render_project(self.root,p,s,self.root/'renders/first.mp4')
        second=renderer.render_project(self.root,p,s,self.root/'renders/second.mp4')
        before=json.loads(Path(first['manifest']).read_bytes())
        after=json.loads(Path(second['manifest']).read_bytes())
        job=next(row['reverse_cache'] for row in after['inputs'] if 'reverse_cache' in row)
        self.assertEqual(job['execution']['status'],'cache-hit')
        self.assertEqual(job['execution']['new_encodings'],0)
        self.assertEqual(job['execution']['new_source_decodes'],0)
        self.assertEqual(job['key'],next(row['reverse_cache']['key'] for row in before['inputs'] if 'reverse_cache' in row))

    def test_preview_range_matches_full_author_surface_and_reuses_cache(self):
        source,_,_=self.source(vfr=[0,33,101,188,195,441,499,800,1002,1221,1600,1800],count=12)
        p,s,_=self.project(source,source_in=10170,source_out=100170,patch={'reverse':True})
        request=preview.plan(p,s,start_frame=3,end_frame=31,height=64)
        result=preview.preview_project(self.root,p,s,request=request)
        expected,_,_=helpers.CFRBoundaryTests.render(self,p,s)
        actual=self.run_native([ffmpeg_path(),'-v','error','-i',result['master'],
            '-map','0:v:0','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
        self.assertEqual(actual,b''.join(expected[3:31]))
        second=preview.preview_project(self.root,p,s,request=request)
        self.assertTrue(second['cache_hit'])
        self.assertEqual(result['cache_key'],second['cache_key'])

    def test_modified_cache_during_render_blocks_final_publication(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        real=renderer.run_process
        def mutate(*args,**kwargs):
            result=real(*args,**kwargs)
            for path in (self.root/'cache/reverse-video').glob('*/frames.nut'):
                path.write_bytes(path.read_bytes()+b'changed-after-decode')
            return result
        output=self.root/'renders/rejected.mp4'
        with patch.object(renderer,'run_process',side_effect=mutate):
            with self.assertRaises(AppError) as caught:renderer.render_project(self.root,p,s,output)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_CORRUPT')
        self.assertFalse(output.exists())

    def test_removed_cache_during_render_cannot_be_silently_rebuilt(self):
        source,_,_=self.source();p,s,_=self.project(source,patch={'reverse':True})
        real=cache.execute
        def remove(root,job,temp_dir,**kwargs):
            if kwargs.get('_require_ready'):
                Path(job['output']).unlink()
            return real(root,job,temp_dir,**kwargs)
        with patch.object(cache,'execute',side_effect=remove):
            with self.assertRaises(AppError) as caught:
                renderer.render_project(self.root,p,s,self.root/'renders/rejected.mp4')
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_CORRUPT')
        self.assertFalse((self.root/'renders/rejected.mp4').exists())

    def test_all_orthogonal_display_matrices_match_native_direct_render(self):
        # Spatially asymmetric pixels make rotations and flips observable.
        source=self.work/'pattern.mp4'
        raw=b''.join(bytes((x*7,y*11,(x*3+y*5+i*9)%256,255))
            for i in range(30) for y in range(helpers.H) for x in range(helpers.W))
        self.run_native([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','rgba',
            '-video_size',f'{helpers.W}x{helpers.H}','-framerate','25','-i','pipe:0',
            '-c:v','libx264','-pix_fmt','yuv420p',source],data=raw)
        for angle in (0,90,180,270):
            for flip in (0,1):
                with self.subTest(angle=angle,horizontal_flip=flip):
                    oriented=self.work/f'oriented-{angle}-{flip}.mp4'
                    self.run_native([ffmpeg_path(),'-v','error','-display_rotation:v:0',str(angle),
                        *(['-display_hflip:v:0'] if flip else []),'-i',source,'-map','0:v:0','-c','copy',oriented])
                    p,s,_=self.project(oriented,patch={'reverse':True})
                    with patch.object(clock,'MAX_SELECTED_BUFFER_BYTES',256*1024**2):
                        expected,_,_=helpers.CFRBoundaryTests.render(self,p,s)
                    inputs,_,metadata,_=renderer.build_filter_graph(self.root,p,s)
                    jobs=cache.materialize(self.root,metadata,self.root/'renders/.tmp/orientation')
                    self.assertTrue(jobs)
                    actual,_,_=helpers.CFRBoundaryTests.render(self,p,s)
                    self.assertEqual(actual,expected)


if __name__=='__main__':unittest.main()
