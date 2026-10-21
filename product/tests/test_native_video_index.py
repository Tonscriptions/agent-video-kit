"""Actual native index persistence, zero-probe hits and unchanged author clock."""
from array import array
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from ai_ad_editor import native_video_index as index
from ai_ad_editor import reverse_video_clock as clock
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.utils import sha256_file
import test_cfr_boundaries as helpers

class NativeVideoIndexTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp
    run_native=helpers.CFRBoundaryTests.run_native
    source=helpers.CFRBoundaryTests.source

    def acquire(self,path,**kwargs):
        return index.acquire(self.root,path,'sha256:'+sha256_file(path),clock.probe_frames,**kwargs)

    def test_readonly_miss_uses_native_probe_without_creating_cache(self):
        source,_,_=self.source();*_,result=self.acquire(source)
        self.assertEqual(result['status'],'probed-readonly');self.assertEqual(result['source_index_decode_calls'],1)
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_persisted_hit_preserves_every_timestamp_without_any_source_probe(self):
        source,_,_=self.source();first=self.acquire(source,persist=True)
        directory=Path(first[-1]['path']);before={p.name:p.read_bytes() for p in directory.iterdir()}
        with patch.object(clock,'probe_frames',side_effect=AssertionError('source probe must not run')):
            second=self.acquire(source,persist=True)
        self.assertEqual(first[:4],second[:4]);self.assertEqual(second[-1]['source_index_decode_calls'],0)
        self.assertEqual(second[-1]['status'],'cache-hit')
        self.assertEqual(before,{p.name:p.read_bytes() for p in directory.iterdir()})

    def test_actual_VFR_index_keeps_native_interval_boundaries(self):
        points=[0,33,101,188,195,441,499,800,1002,1221,1600,1800]
        source,_,_=self.source(count=len(points),vfr=points)
        first=self.acquire(source,persist=True);second=self.acquire(source)
        tb=Fraction(second[2]['time_base'])
        self.assertEqual([p*tb for p in second[0]],[Fraction(p,1000) for p in points])
        self.assertEqual(first[:4],second[:4]);self.assertEqual(second[-1]['source_index_decode_calls'],0)

    def test_nonzero_origin_and_original_duration_array_survive_persistence(self):
        source,_,_=self.source();path=self.work/'offset.nut'
        self.run_native([ffmpeg_path(),'-v','error','-i',source,'-output_ts_offset','5.117123',
            '-fps_mode','passthrough','-enc_time_base','filter','-c:v','ffv1','-pix_fmt','bgra',path])
        native=clock.probe_frames(path);self.acquire(path,persist=True)
        loaded=self.acquire(path);self.assertEqual(loaded[:4],native)
        self.assertNotEqual(native[0][0],0);self.assertTrue(Fraction(native[3]['start_time'])>5)

    def test_explicit_native_decoder_has_separate_pinned_index(self):
        source,_,_=self.source();default=self.acquire(source,persist=True)
        explicit=self.acquire(source,persist=True,decoder='ffv1')
        self.assertNotEqual(default[-1]['key'],explicit[-1]['key']);self.assertEqual(default[:4],explicit[:4])

    def test_changed_registered_source_rejects_before_source_probe(self):
        source,_,_=self.source();old='sha256:'+sha256_file(source);source.write_bytes(source.read_bytes()+b'changed')
        with self.assertRaises(AppError) as caught:
            index.acquire(self.root,source,old,lambda *a,**k:self.fail('must not probe'))
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_INPUT_CHANGED')
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_source_mutation_during_probe_cannot_publish_index(self):
        source,_,_=self.source();expected='sha256:'+sha256_file(source)
        def mutate(*args,**kwargs):
            value=clock.probe_frames(*args,**kwargs);source.write_bytes(source.read_bytes()+b'mutated');return value
        with self.assertRaises(AppError) as caught:index.acquire(self.root,source,expected,mutate,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_INPUT_CHANGED')
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_cancel_before_lookup_never_starts_probe(self):
        marker=self.work/'cancel';marker.write_bytes(b'cancel')
        with self.assertRaises(AppError) as caught:
            index.acquire(self.root,Path('unused'),'',lambda *a,**k:self.fail('must not probe'),cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')

    def test_cancel_after_native_probe_leaves_no_ready_or_staging_files(self):
        source,_,_=self.source();marker=self.work/'cancel'
        def cancelled(*args,**kwargs):
            value=clock.probe_frames(*args,**kwargs);marker.write_bytes(b'cancel');return value
        with self.assertRaises(AppError) as caught:
            index.acquire(self.root,source,'sha256:'+sha256_file(source),cancelled,persist=True,cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_tampered_binary_is_rejected_and_preserved_without_reprobe(self):
        source,_,_=self.source();result=self.acquire(source,persist=True)
        path=Path(result[-1]['path'])/'pts.i64le';path.write_bytes(path.read_bytes()+b'changed');before=path.read_bytes()
        with patch.object(clock,'probe_frames',side_effect=AssertionError('must not hide corruption')):
            with self.assertRaises(AppError) as caught:self.acquire(source)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_CORRUPT');self.assertEqual(path.read_bytes(),before)

    def test_invalid_json_or_count_is_rejected_before_array_allocation(self):
        source,_,_=self.source();result=self.acquire(source,persist=True);path=Path(result[-1]['path'])/'index.json'
        original=json.loads(path.read_bytes())
        for data in (b'{bad',b'[]',json.dumps({**original,'frames':1_000_001}).encode(),json.dumps({**original,'frames':True}).encode()):
            with self.subTest(data=data[:30]):
                path.write_bytes(data)
                with self.assertRaises(AppError) as caught:self.acquire(source)
                self.assertEqual(caught.exception.code,'NATIVE_INDEX_CORRUPT');self.assertEqual(path.read_bytes(),data)

    def test_inconsistent_native_arrays_cannot_be_persisted(self):
        source,_,_=self.source();bad=(array('q',[0,0]),array('q',[1,1]),{'time_base':'1/25','width':'32','height':'18','pix_fmt':'bgra'},{'start_time':'0'})
        with self.assertRaises(AppError) as caught:
            index.acquire(self.root,source,'sha256:'+sha256_file(source),lambda *a,**k:bad,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_INVALID');self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_insufficient_disk_rejects_before_publishing(self):
        source,_,_=self.source();usage=index.shutil.disk_usage(self.root)
        with patch.object(index.shutil,'disk_usage',return_value=usage._replace(free=0)):
            with self.assertRaises(AppError) as caught:self.acquire(source,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_DISK_SPACE');self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_source_index_directory_junction_cannot_redirect_write(self):
        import _winapi
        source,_,_=self.source();result=self.acquire(source)
        path=Path(result[-1]['path']);path.parent.mkdir(parents=True)
        outside=self.work/'outside';outside.mkdir();_winapi.CreateJunction(str(outside),str(path))
        self.addCleanup(lambda:path.rmdir() if path.exists() else None)
        with self.assertRaises(AppError) as caught:self.acquire(source,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_PATH_INVALID');self.assertEqual(list(outside.iterdir()),[])


if __name__=='__main__':unittest.main()
