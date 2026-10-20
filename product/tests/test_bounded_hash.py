"""Correct complete digests under a bounded local read-allocation budget."""
from __future__ import annotations

import builtins
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from ai_ad_editor.errors import AppError
from ai_ad_editor.utils import sha256_file


class LimitedReadStream(io.BytesIO):
    def __init__(self, data, *, fail_after=None):
        super().__init__(data)
        self.fail_after = fail_after
        self.read_calls = 0
        self.max_buffer = 0

    def read(self, *args):
        raise MemoryError('Simulated allocation pressure in bytes-returning read')

    def readinto(self, target):
        if self.fail_after is not None and self.read_calls >= self.fail_after:
            raise OSError('Simulated local I/O failure')
        self.read_calls += 1
        self.max_buffer = max(self.max_buffer, len(target))
        # A real reader may return fewer bytes than requested before EOF.
        return super().readinto(memoryview(target)[:1 + self.read_calls % 997])


class LocalStreamPath:
    def __init__(self, stream):
        self.stream = stream
        self.opened = False

    def open(self, *args, **kwargs):
        self.opened = True
        return self.stream

    def __str__(self):
        return 'local-allocation-test.bin'


class BoundedFileHashTests(unittest.TestCase):
    def test_real_empty_and_multibuffer_files_match_independent_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.bin'
            for data in (b'', b'x', bytes(range(256)) * 13001):
                path.write_bytes(data)
                for size in (1, 7919, 1024 * 1024):
                    with self.subTest(bytes=len(data), requested=size):
                        self.assertEqual(sha256_file(path, size), hashlib.sha256(data).hexdigest())

    def test_memory_limited_reader_and_short_reads_keep_complete_digest(self):
        data = bytes(range(256)) * 707
        stream = LimitedReadStream(data)
        self.assertEqual(sha256_file(LocalStreamPath(stream), 10 * 1024**3), hashlib.sha256(data).hexdigest())
        self.assertLessEqual(stream.max_buffer, 65536)
        self.assertTrue(stream.closed)

    def test_buffer_reservation_can_degrade_without_advancing_or_skipping_source(self):
        data = b'independent local source bytes\x00\xff' * 3001
        stream = LimitedReadStream(data)
        path = LocalStreamPath(stream)

        def reserve(size):
            if size > 8192:
                self.assertFalse(path.opened)
                raise MemoryError('Reservation budget is 8 KiB')
            return builtins.bytearray(size)

        with mock.patch('ai_ad_editor.utils.bytearray', side_effect=reserve, create=True):
            result = sha256_file(path)
        self.assertEqual(result, hashlib.sha256(data).hexdigest())
        self.assertLessEqual(stream.max_buffer, 8192)
        self.assertTrue(stream.closed)

    def test_io_failure_never_returns_a_prefix_digest_and_closes_handle(self):
        stream = LimitedReadStream(b'original source' * 3001, fail_after=2)
        with self.assertRaisesRegex(OSError, 'Simulated local I/O'):
            sha256_file(LocalStreamPath(stream))
        self.assertTrue(stream.closed)

    def test_no_buffer_fails_before_opening_source_with_structured_resource_error(self):
        path = LocalStreamPath(LimitedReadStream(b'original'))
        with mock.patch('ai_ad_editor.utils.bytearray', side_effect=MemoryError, create=True):
            with self.assertRaises(AppError) as caught:
                sha256_file(path)
        self.assertEqual(caught.exception.code, 'FILE_HASH_MEMORY_EXHAUSTED')
        self.assertFalse(path.opened)
        path.stream.close()


if __name__ == '__main__':
    unittest.main()
