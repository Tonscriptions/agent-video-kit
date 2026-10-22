"""Actual native children: bounded reads, failure, cancellation and ownership."""
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_native_pipe import NativePipe

NATIVE_RECEIPTS = []


class NativePipeTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.runtime/temp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='native-window-pipe-', dir=base)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def pipe(self, code, **kwargs):
        return NativePipe([sys.executable, '-I', '-S', '-B', '-c', code], cwd=self.root, **kwargs)

    def record(self, pipe, **extra):
        self.assertIsNotNone(pipe.process.poll())
        self.assertTrue(all(not t.is_alive() for t in pipe.threads))
        NATIVE_RECEIPTS.append({'test': self.id(), 'pid': pipe.process.pid,
            'exit_code': pipe.process.poll(), 'stdout_bytes': pipe.bytes_read,
            'maximum_queued_chunks': pipe.maximum_queued_chunks,
            'all_owned_threads_exited': True, **extra})

    def test_exact_frame_reads_cross_many_bounded_chunks_without_pixel_aliases(self):
        expected = bytes(range(256)) * 5000
        with self.pipe('import sys;sys.stdout.buffer.write(bytes(range(256))*5000)') as pipe:
            first = pipe.read(70001)
            second = pipe.read(len(expected) - len(first))
            self.assertEqual(first + second, expected)
            first[0] = 33
            self.assertEqual(second[0], expected[70001])
            self.assertEqual(pipe.read(1), b'')
            pipe.finish()
            self.assertLessEqual(pipe.maximum_queued_chunks, 4)
        self.record(pipe, expected_sha256='sha256:' + hashlib.sha256(expected).hexdigest())

    def test_streamed_probe_chunks_and_bounded_stderr_preserve_error_tail(self):
        with self.pipe('import sys;sys.stderr.buffer.write(b"x"*300000+b"TAIL");sys.stdout.buffer.write(b"probe"*30000)') as pipe:
            value = b''.join(pipe.chunks())
            pipe.finish()
            self.assertEqual(value, b'probe' * 30000)
            self.assertTrue(pipe.stderr().endswith('TAIL'))
            self.assertLessEqual(sum(map(len, pipe.tail)), 131072)
        self.record(pipe)

    def test_real_nonzero_child_is_reported_after_stdout_EOF_and_closed(self):
        with self.assertRaises(AppError) as caught:
            with self.pipe('import sys;sys.stdout.buffer.write(b"partial");sys.stderr.write("actual-error");sys.exit(7)') as pipe:
                self.assertEqual(pipe.read(100), b'partial')
                pipe.finish()
        self.assertEqual(caught.exception.code, 'FLOAT_NATIVE_PIPE_PROCESS')
        self.assertIn('actual-error', str(caught.exception.diagnostics))
        self.record(pipe)

    def test_cancellation_after_actual_first_byte_reaps_only_owned_child(self):
        marker = self.root / 'cancel'
        with self.assertRaises(AppError) as caught:
            with self.pipe('import sys,time;sys.stdout.buffer.write(b"x");sys.stdout.buffer.flush();time.sleep(30)', cancel_file=marker) as pipe:
                self.assertEqual(pipe.read(1), b'x')
                marker.write_text('cancel', encoding='utf8')
                pipe.read(1)
        self.assertEqual(caught.exception.code, 'CANCELLED')
        self.record(pipe)

    def test_native_stdout_stall_times_out_without_leaking_reader_threads(self):
        started = time.monotonic()
        with self.assertRaises(AppError) as caught:
            with self.pipe('import time;time.sleep(30)', timeout=.4) as pipe:
                pipe.read(1)
        self.assertEqual(caught.exception.code, 'FLOAT_NATIVE_PIPE_TIMEOUT')
        self.assertLess(time.monotonic() - started, 12)
        self.record(pipe)

    def test_abandon_full_stdout_queue_closes_owned_child_and_releases_chunks(self):
        with self.pipe('import sys;sys.stdout.buffer.write(b"x"*16000000)') as pipe:
            self.assertEqual(pipe.read(1), b'x')
            end = time.monotonic() + 3
            while pipe.queue.qsize() < 4 and time.monotonic() < end:
                time.sleep(.01)
            self.assertEqual(pipe.queue.qsize(), 4)
        self.assertTrue(pipe.queue.empty())
        self.assertEqual(pipe.pending, b'')
        self.record(pipe)

    def test_invalid_budgets_reject_before_spawning_and_closed_state_is_explicit(self):
        for timeout in (0, -1, True, float('nan'), 3601):
            with self.subTest(timeout=timeout), self.assertRaises(AppError):
                self.pipe('raise SystemExit(99)', timeout=timeout)
        with self.pipe('pass') as pipe:
            for count in (-1, True, 512 * 1024**2 + 1):
                with self.assertRaises(AppError):
                    pipe.read(count)
            with self.assertRaises(AppError):
                pipe.finish()
            self.assertEqual(pipe.read(1), b'')
            pipe.finish()
        with self.assertRaises(AppError):
            pipe.read(1)
        pipe.close()
        self.record(pipe)
