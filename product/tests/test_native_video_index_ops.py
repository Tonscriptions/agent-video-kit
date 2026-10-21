"""Owned three-file index cleanup through the public CLI and junction guards."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_ad_editor import native_video_index as cache
from ai_ad_editor import reverse_video_clock as clock
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import load_project,save_project
from ai_ad_editor.utils import sha256_file
import test_cfr_boundaries as helpers
from test_magnetic_reorder import invoke


class NativeVideoIndexOpsTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp
    source=helpers.CFRBoundaryTests.source
    run_native=helpers.CFRBoundaryTests.run_native

    def entry(self,key='a',size=8,mtime=100):
        directory=self.root/'cache/native-video-index'/(key*64);directory.mkdir(parents=True)
        (directory/'pts.i64le').write_bytes(b'x'*size)
        (directory/'durations.i64le').write_bytes(b'y'*size)
        (directory/'index.json').write_bytes(b'{}')
        os.utime(directory,ns=(mtime,mtime));return directory

    def test_public_empty_list_is_readonly(self):
        code,value=invoke('cache','list','--kind','native-video-index','--project',self.root)
        self.assertEqual(code,0,value);self.assertEqual(value['data']['entries'],[])
        self.assertEqual(value['data']['kind'],'native-video-index')
        self.assertFalse((self.root/'cache/native-video-index').exists())

    def test_inventory_counts_three_files_without_integrity_claim(self):
        self.entry();listing=cache.cache_list(self.root)
        self.assertEqual(listing['bytes'],18)
        self.assertTrue(listing['entries'][0]['complete_file_set'])
        self.assertFalse(listing['entries'][0]['byte_integrity_checked'])

    def test_public_dry_prune_preserves_exact_bytes(self):
        directory=self.entry();before={p.name:p.read_bytes() for p in directory.iterdir()}
        code,value=invoke('cache','prune','--project',self.root,'--kind','native-video-index','--key','a'*64,'--dry-run')
        self.assertEqual(code,0,value);self.assertEqual(value['status'],'planned')
        self.assertEqual(value['data']['removed'],['a'*64])
        self.assertEqual(before,{p.name:p.read_bytes() for p in directory.iterdir()})

    def test_public_selected_prune_preserves_other_kind_and_entry(self):
        first=self.entry('a');second=self.entry('b');reverse=self.root/'cache/reverse-video'/('c'*64)
        reverse.mkdir(parents=True);(reverse/'frames.nut').write_bytes(b'preserve')
        code,value=invoke('cache','prune','--project',self.root,'--kind','native-video-index','--key','a'*64)
        self.assertEqual(code,0,value);self.assertFalse(first.exists());self.assertTrue(second.exists())
        self.assertEqual((reverse/'frames.nut').read_bytes(),b'preserve')
        code,value=invoke('cache','list','--project',self.root)
        self.assertEqual(code,0,value);self.assertEqual(len(value['data']['entries']),1)
        self.assertEqual(value['data']['kind'],'reverse-video')

    def test_malformed_metadata_remains_explicitly_removable(self):
        directory=self.entry();(directory/'index.json').write_bytes(b'{broken')
        self.assertEqual(cache.cache_prune(self.root,key='a'*64)['removed'],['a'*64])
        self.assertFalse(directory.exists())

    def test_unknown_authored_file_blocks_pruning(self):
        directory=self.entry();sentinel=directory/'authored.txt';sentinel.write_text('keep',encoding='utf8')
        with self.assertRaises(AppError) as caught:cache.cache_prune(self.root)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_LAYOUT_INVALID')
        self.assertEqual(sentinel.read_text(encoding='utf8'),'keep')
        self.assertTrue((directory/'pts.i64le').exists())

    def test_entry_junction_rejected_without_touching_external_files(self):
        import _winapi
        outside=self.work/'outside';outside.mkdir();sentinel=outside/'sentinel';sentinel.write_bytes(b'keep')
        base=self.root/'cache/native-video-index';base.mkdir(parents=True);link=base/('a'*64)
        _winapi.CreateJunction(str(outside),str(link));self.addCleanup(lambda:link.rmdir() if link.exists() else None)
        with self.assertRaises(AppError) as caught:cache.cache_prune(self.root)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_PATH_INVALID')
        self.assertEqual(sentinel.read_bytes(),b'keep')

    def test_parent_junction_rejected_before_inventory(self):
        import _winapi
        outside=self.work/'outside';outside.mkdir();base=self.root/'cache'
        if base.exists():base.rmdir()
        _winapi.CreateJunction(str(outside),str(base));self.addCleanup(lambda:base.rmdir() if base.exists() else None)
        with self.assertRaises(AppError) as caught:cache.cache_list(self.root)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_PATH_INVALID')
        self.assertEqual(list(outside.iterdir()),[])

    def test_current_project_references_protect_absolute_and_relative_paths(self):
        protected=self.entry('a');other=self.entry('b');project=load_project(self.root)[1]
        project['assets']=[{'id':'derived-author-source','kind':'image','uri':str(protected/'pts.i64le')}]
        save_project(self.root,project);result=cache.cache_prune(self.root)
        self.assertEqual(result['protected_reference_keys'],['a'*64])
        self.assertTrue(protected.exists());self.assertFalse(other.exists())
        project['assets'][0]['uri']=(protected/'index.json').relative_to(self.root).as_posix()
        save_project(self.root,project);self.assertEqual(cache.cache_prune(self.root)['removed'],[])

    def test_keep_budget_preserves_newer_entry(self):
        old=self.entry('a',8,100);new=self.entry('b',16,200)
        result=cache.cache_prune(self.root,keep_bytes=34)
        self.assertEqual(result['remaining_bytes'],34)
        self.assertFalse(old.exists());self.assertTrue(new.exists())

    def test_full_entry_budget_rejects_new_build_before_native_probe(self):
        source,_,_=self.source();self.entry('a')
        with patch.object(cache,'MAX_CACHE_ENTRIES',1),patch.object(clock,'probe_frames',side_effect=AssertionError('admission before probe')):
            with self.assertRaises(AppError) as caught:
                cache.acquire(self.root,source,'sha256:'+sha256_file(source),clock.probe_frames,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_INDEX_ENTRY_BUDGET')
        self.assertEqual(len(list((self.root/'cache/native-video-index').iterdir())),1)

    def test_invalid_key_and_budget_are_structured_errors(self):
        for kwargs in ({'keep_bytes':-1},{'key':'../outside'},{'key':'a'*64,'keep_bytes':1}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(AppError) as caught:cache.cache_prune(self.root,**kwargs)
                self.assertEqual(caught.exception.code,'NATIVE_INDEX_ARGUMENT_INVALID')

    def test_empty_broken_entry_is_explicitly_removable(self):
        directory=self.root/'cache/native-video-index'/('a'*64);directory.mkdir(parents=True)
        self.assertEqual(cache.cache_prune(self.root,key='a'*64)['removed'],['a'*64])
        self.assertFalse(directory.exists())


if __name__=='__main__':unittest.main()
