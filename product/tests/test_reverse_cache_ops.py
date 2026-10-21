"""Public derived-cache inventory, explicit pruning and authored-input protection."""
import os
from pathlib import Path
import unittest
from ai_ad_editor import reverse_cache as cache
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import load_project,save_project
import test_cfr_boundaries as helpers
from test_magnetic_reorder import invoke


class ReverseCacheOpsTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp

    def entry(self,key='a',size=10,mtime=100):
        directory=self.root/'cache/reverse-video'/(key*64);directory.mkdir(parents=True)
        (directory/'frames.nut').write_bytes(b'x'*size)
        (directory/'receipt.json').write_bytes(b'{}')
        os.utime(directory,ns=(mtime,mtime));return directory

    def test_public_list_on_empty_project_creates_no_cache(self):
        code,value=invoke('cache','list','--project',self.root)
        self.assertEqual(code,0,value);self.assertEqual(value['data']['entries'],[])
        self.assertFalse((self.root/'cache/reverse-video').exists())

    def test_inventory_does_not_certify_media_integrity(self):
        self.entry();result=cache.cache_list(self.root)
        self.assertEqual(result['bytes'],12)
        self.assertTrue(result['entries'][0]['complete_file_set'])
        self.assertFalse(result['entries'][0]['media_integrity_checked'])

    def test_public_dry_run_preserves_exact_owned_files(self):
        path=self.entry();before={p.name:p.read_bytes() for p in path.iterdir()}
        code,value=invoke('cache','prune','--project',self.root,'--dry-run')
        self.assertEqual(code,0,value);self.assertEqual(value['status'],'planned')
        self.assertEqual(value['data']['removed'],['a'*64])
        self.assertEqual(before,{p.name:p.read_bytes() for p in path.iterdir()})

    def test_lru_keep_budget_preserves_newer_entry(self):
        old=self.entry('a',10,100);new=self.entry('b',20,200)
        result=cache.cache_prune(self.root,keep_bytes=22)
        self.assertEqual(result['remaining_bytes'],22);self.assertFalse(old.exists());self.assertTrue(new.exists())

    def test_selected_key_leaves_other_cache_bytes_untouched(self):
        first=self.entry('a');second=self.entry('b');before=(second/'frames.nut').read_bytes()
        code,value=invoke('cache','prune','--project',self.root,'--key','a'*64)
        self.assertEqual(code,0,value);self.assertEqual(value['data']['removed'],['a'*64])
        self.assertFalse(first.exists());self.assertEqual((second/'frames.nut').read_bytes(),before)

    def test_empty_damaged_entry_can_be_removed_explicitly(self):
        directory=self.root/'cache/reverse-video'/('a'*64);directory.mkdir(parents=True)
        result=cache.cache_prune(self.root,key='a'*64)
        self.assertEqual(result['removed'],['a'*64]);self.assertFalse(directory.exists())

    def test_missing_selected_key_does_not_delete_other_entries(self):
        path=self.entry();result=cache.cache_prune(self.root,key='b'*64)
        self.assertEqual(result['removed'],[]);self.assertTrue(path.exists())

    def test_current_authored_asset_protects_absolute_and_relative_cache_paths(self):
        protected=self.entry('a');unreferenced=self.entry('b')
        project=load_project(self.root)[1]
        project['assets']=[{'id':'linked','kind':'video','uri':str(protected/'frames.nut')}]
        save_project(self.root,project)
        result=cache.cache_prune(self.root)
        self.assertEqual(result['protected_reference_keys'],['a'*64]);self.assertTrue(protected.exists())
        self.assertFalse(unreferenced.exists())
        project['assets'][0]['uri']=(protected/'frames.nut').relative_to(self.root).as_posix()
        save_project(self.root,project);self.assertEqual(cache.cache_prune(self.root)['removed'],[])

    def test_unknown_user_file_blocks_pruning_without_deletion(self):
        directory=self.entry();(directory/'keep-me.txt').write_text('authored',encoding='utf8')
        with self.assertRaises(AppError) as caught:cache.cache_prune(self.root)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_LAYOUT_INVALID')
        self.assertEqual((directory/'keep-me.txt').read_text(encoding='utf8'),'authored')
        self.assertTrue((directory/'frames.nut').exists())

    def test_malformed_receipt_remains_explicitly_removable(self):
        directory=self.entry();(directory/'receipt.json').write_bytes(b'{broken json')
        self.assertEqual(len(cache.cache_list(self.root)['entries']),1)
        self.assertEqual(cache.cache_prune(self.root,key='a'*64)['removed'],['a'*64])

    def test_directory_junction_cannot_redirect_inventory_or_prune(self):
        import _winapi
        outside=self.work/'outside';outside.mkdir();sentinel=outside/'sentinel';sentinel.write_bytes(b'keep')
        base=self.root/'cache/reverse-video';base.mkdir(parents=True);link=base/('a'*64)
        _winapi.CreateJunction(str(outside),str(link));self.addCleanup(lambda:link.rmdir() if link.exists() else None)
        with self.assertRaises(AppError) as caught:cache.cache_prune(self.root)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_PATH_INVALID');self.assertEqual(sentinel.read_bytes(),b'keep')

    def test_cache_parent_junction_is_rejected_before_inventory(self):
        import _winapi
        outside=self.work/'outside';outside.mkdir();base=self.root/'cache'
        # create_project already owns an empty cache directory.
        if base.exists():base.rmdir()
        _winapi.CreateJunction(str(outside),str(base));self.addCleanup(lambda:base.rmdir() if base.exists() else None)
        with self.assertRaises(AppError) as caught:cache.cache_list(self.root)
        self.assertEqual(caught.exception.code,'REVERSE_CACHE_PATH_INVALID');self.assertEqual(list(outside.iterdir()),[])

    def test_invalid_key_and_budget_are_structured_errors(self):
        for kwargs in ({'keep_bytes':-1},{'key':'../outside'},{'key':'a'*64,'keep_bytes':1}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(AppError) as caught:cache.cache_prune(self.root,**kwargs)
                self.assertEqual(caught.exception.code,'REVERSE_CACHE_ARGUMENT_INVALID')


if __name__=='__main__':unittest.main()
