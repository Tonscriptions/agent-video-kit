"""Actual Windows file sharing, lifetime and digest reuse invariants."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ai_ad_editor.artifact_locks import artifact_entry, verification_scope
from ai_ad_editor.errors import AppError
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json


@unittest.skipUnless(sys.platform == 'win32', 'Native Windows file sharing')
class ArtifactLocksTests(unittest.TestCase):
    def setUp(self):
        configure_local_runtime()
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime/temp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root/'model.bin'
        self.path.write_bytes(b'local weights'*4096)

    def test_digest_reused_while_writes_and_replacement_are_denied(self):
        expected = 'sha256:'+hashlib.sha256(self.path.read_bytes()).hexdigest()
        replacement = self.root/'replacement.bin';replacement.write_bytes(b'other weights')
        with verification_scope() as scope:
            first = artifact_entry(self.path, 'model')
            for _ in range(10):self.assertEqual(artifact_entry(self.path, 'model'), first)
            self.assertEqual(first['sha256'], expected)
            self.assertEqual(scope.summary()['files_hashed'], 1)
            self.assertEqual(scope.summary()['bytes_hashed'], self.path.stat().st_size)
            self.assertEqual(scope.summary()['digest_reuses_while_locked'], 10)
            with self.assertRaises(PermissionError):self.path.write_bytes(b'forbidden')
            with self.assertRaises(PermissionError):os.replace(replacement, self.path)
            with self.assertRaises(PermissionError):atomic_write_json(self.path, {'forbidden': 'replacement'})
            self.assertEqual(list(self.root.glob('.model.bin.*.tmp')), [])
            self.assertEqual(self.path.read_bytes(), b'local weights'*4096)
        self.path.write_bytes(b'allowed after release')

    def test_same_size_and_restored_mtime_are_rehashed_next_command(self):
        before = self.path.stat()
        with verification_scope():first = artifact_entry(self.path, 'model')
        self.path.write_bytes(b'X'*before.st_size)
        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with verification_scope() as scope:second = artifact_entry(self.path, 'model')
        self.assertNotEqual(first['sha256'], second['sha256'])
        self.assertEqual(scope.bytes_hashed, before.st_size)

    def test_existing_writer_prevents_lock_and_has_no_cached_digest(self):
        with self.path.open('r+b'):
            with verification_scope() as scope:
                with self.assertRaises(AppError) as failure:artifact_entry(self.path, 'model')
                self.assertEqual(failure.exception.code, 'LOCAL_ARTIFACT_LOCK_FAILED')
                self.assertEqual(scope.bytes_hashed, 0)
        with verification_scope():self.assertTrue(artifact_entry(self.path, 'model')['sha256'])

    def test_other_process_can_read_but_cannot_write_while_locked(self):
        child = "from pathlib import Path;import sys;p=Path(sys.argv[1]);assert p.read_bytes();\ntry:p.write_bytes(b'changed')\nexcept PermissionError:print('readable-write-blocked')\nelse:raise SystemExit(9)"
        with verification_scope():
            artifact_entry(self.path, 'model')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', child, str(self.path)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'readable-write-blocked')

    def test_exception_releases_all_handles(self):
        with self.assertRaisesRegex(RuntimeError, 'controlled failure'):
            with verification_scope():
                artifact_entry(self.path, 'model')
                raise RuntimeError('controlled failure')
        self.path.write_bytes(b'updated after failure')
        with verification_scope():self.assertEqual(artifact_entry(self.path, 'model')['bytes'], 21)

    def test_nested_scope_retains_outer_lock(self):
        with verification_scope() as outer:
            artifact_entry(self.path, 'model')
            with verification_scope() as inner:
                self.assertIs(inner, outer);artifact_entry(self.path, 'evidence')
            with self.assertRaises(PermissionError):self.path.unlink()
        self.path.unlink();self.assertFalse(self.path.exists())

    def test_nonlocal_empty_and_directory_inputs_are_rejected(self):
        empty = self.root/'empty';empty.touch()
        with verification_scope():
            for path in (Path(r'\\127.0.0.1\never-touch\model'), empty, self.root):
                with self.subTest(path=path), self.assertRaises(AppError):artifact_entry(path, 'model')


if __name__ == '__main__':unittest.main()
