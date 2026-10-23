from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from ai_ad_editor import pipeline_diagnostics as d
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_matting import _pipeline_workspace
from ai_ad_editor.runtime import configure_local_runtime
import test_local_matting as matting_tests
invoke = matting_tests.invoke


class DiagnosticStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pipeline-diagnostics-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.directory = d.Directory(self.work)

    def session(self):
        request = {'video': {'frames': 8}, 'source': {'path': str(self.root / 'private.mov'), 'sha256': 'sha256:' + '1' * 64},
            'adapter': {'sha256': 'sha256:' + '2' * 64}, 'generation': {'prompt': 'PRIVATE scene description', 'seed': 42}}
        session = d.Session(self.root, request, request['adapter'], 'op_controlled')
        session.prepare(self.work, request)
        return session

    def capture(self, session=None):
        for role in d.ROLES:
            (self.work / (role + '.log')).write_bytes(b'controlled stderr\n')
        session = session or self.session()
        error = AppError('CONTROLLED_FAILURE', 'fixture', exit_code=6)
        session.capture(self.work, error)
        self.assertEqual(error.diagnostics['status'], 'stored', error.diagnostics)
        return error, d.inspect_record(self.root, error.diagnostics['diagnostic_id'])

    def rewrite_manifest(self, reference, function):
        path = self.root.joinpath(*d.STORE_PARTS, reference['diagnostic_id'], 'manifest.json')
        value = json.loads(path.read_bytes()); function(value); path.write_bytes(d.encoded(value))

    def test_plain_error_serialization_has_no_diagnostic_field(self):
        value = AppError('ORIGINAL', 'text', exit_code=6).as_dict()
        self.assertNotIn('diagnostics', value)
        self.assertEqual(value['code'], 'ORIGINAL')

    def test_capture_preserves_error_and_hash_binds_only_fixed_files(self):
        error, (manifest, files) = self.capture()
        self.assertEqual((error.code, error.exit_code, error.operation_id), ('CONTROLLED_FAILURE', 6, 'op_controlled'))
        self.assertEqual(set(files), set(d.FILES) | {'manifest.json'})
        self.assertEqual(d.digest(files['manifest.json']), error.diagnostics['manifest_sha256'])
        self.assertEqual(manifest['root_cause'], 'unknown')
        for name, entry in manifest['files'].items():
            self.assertEqual((len(files[name]), d.digest(files[name])), (entry['bytes'], entry['sha256']))

    def test_prompt_paths_environment_and_binary_are_not_copied(self):
        session = self.session()
        for role in d.ROLES:
            (self.work / (role + '.log')).write_text('PRIVATE scene description\nE:\\private\\secret.mov\ntoken=privatekey123\nBearer TOPSECRET\nuser@example.test\nhttps://provider.test/key\n', encoding='utf8')
        (self.work / 'stdout.rgba').write_bytes(bytes(range(256)) * 1024)
        (self.work / 'request.json').write_text('secret environment and prompts', encoding='utf8')
        error = AppError('CONTROLLED_FAILURE', 'fixture', exit_code=6); session.capture(self.work, error)
        _, files = d.inspect_record(self.root, error.diagnostics['diagnostic_id'])
        all_bytes = b''.join(files.values())
        for secret in (b'PRIVATE scene description', b'privatekey123', b'TOPSECRET', b'user@example', b'https://provider', b'secret environment'):
            self.assertNotIn(secret, all_bytes)
        self.assertNotIn('stdout.rgba', files)
        request = json.loads(files['request.json'])
        self.assertEqual(request['generation']['prompt_sha256'], d.digest(b'PRIVATE scene description'))

    def test_capture_secondary_write_failure_preserves_original(self):
        error = AppError('CANCELLED', 'cancelled', exit_code=8)
        with patch.object(d.Directory, 'write', side_effect=OSError('controlled write failure')):
            self.session().capture(self.work, error)
        self.assertEqual((error.code, error.exit_code), ('CANCELLED', 8))
        self.assertEqual(error.diagnostics['status'], 'unavailable')

    def test_structured_worker_error_is_bounded_redacted_and_retained(self):
        (self.work / 'response.json').write_bytes(d.encoded({'status': 'failed',
            'error': 'DecodeError: PRIVATE scene description token=secretValue https://private.test/model huggingface.co/private ' + '汉' * 3000,
            'environment': 'UNWANTED PRIVATE ENV'}))
        _, (_, files) = self.capture()
        summary = json.loads(files['response.json'])
        value = summary['worker_error']
        self.assertIn('DecodeError', value); self.assertLessEqual(len(value.encode('utf8')), 2000)
        for secret in ('PRIVATE scene description', 'secretValue', 'https://private.test', 'huggingface.co/private', 'UNWANTED PRIVATE ENV'):
            self.assertNotIn(secret.encode(), b''.join(files.values()))
        from ai_ad_editor.policy import reference_kind
        self.assertEqual(reference_kind(value), 'local')

    def test_running_child_is_never_reported_as_completed(self):
        process = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time;time.sleep(30)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            session = self.session(); session.processes.started('worker', process)
            error = AppError('TIMEOUT', 'fixture', exit_code=8); session.capture(self.work, error)
            self.assertEqual(error.diagnostics['warnings'][0]['code'], 'DIAGNOSTIC_CHILD_STILL_RUNNING')
        finally:
            process.kill(); process.wait(timeout=10)

    def test_windows_exit_bits_are_not_applied_to_posix_signals(self):
        self.assertEqual(d.exit_value(-1073741819, platform='win32'), {'raw': -1073741819, 'unsigned': 3221225477, 'hex': '0xc0000005'})
        self.assertEqual(d.exit_value(-9, platform='linux'), {'raw': -9})
        self.assertIsNone(d.exit_value(None))

    def test_simultaneous_native_exits_are_a_set_not_a_root_cause(self):
        processes = d.Processes(); children = []
        try:
            for role in d.ROLES:
                p = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'raise SystemExit(23)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                children.append(p); processes.started(role, p)
            for p in children: p.wait(timeout=10)
            processes.observe(); processes.before_cleanup(); processes.finished()
            self.assertEqual(set(processes.first_failure_roles), set(d.ROLES))
            self.assertTrue(all(row['observed_exit']['raw'] == 23 and not row['cleanup_requested'] for row in processes.rows.values()))
        finally:
            for p in children:
                if p.poll() is None: p.kill()
                p.wait(timeout=10)

    def test_progress_missing_invalid_and_out_of_range(self):
        self.assertEqual(d.progress_snapshot(self.directory, 8)['state'], 'missing')
        for raw in (b'not json', b'{"frames":NaN}', b'{"frames":1,"frames":2}', b'[' * 1500 + b']' * 1500):
            (self.work / 'progress.json').write_bytes(raw)
            self.assertEqual(d.progress_snapshot(self.directory, 8)['state'], 'invalid_json')
        for value in (True, -1, 9, '1'):
            (self.work / 'progress.json').write_bytes(d.encoded({'frames': value}))
            self.assertEqual(d.progress_snapshot(self.directory, 8)['state'], 'invalid_frames')

    def test_unknown_stage_is_hashed_and_known_stage_retained(self):
        for value in ('joint-video-denoising-step-2', ['untrusted', 'private text']):
            (self.work / 'progress.json').write_bytes(d.encoded({'frames': 3, 'stage': value}))
            result = d.progress_snapshot(self.directory, 8)
            self.assertEqual(result['frames'], 3)
            if isinstance(value, str): self.assertEqual(result['stage'], value)
            else:
                self.assertEqual(result['stage_state'], 'unknown'); self.assertNotIn('private', str(result))

    def test_stale_progress_retains_last_delivered_frame(self):
        (self.work / 'progress.json').write_bytes(d.encoded({'frames': 2}))
        session = self.session(); session.last_reported_frame = 5
        _, (manifest, _) = self.capture(session)
        self.assertTrue(manifest['progress']['older_than_reported'])

    def test_sparse_four_gib_log_actually_reads_only_64kib(self):
        path = self.work / 'worker.log'
        with path.open('wb') as stream:
            if os.name == 'nt':
                import ctypes, msvcrt
                from ctypes import wintypes
                fn = ctypes.WinDLL('kernel32', use_last_error=True).DeviceIoControl
                fn.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
                fn.restype = wintypes.BOOL
                count = wintypes.DWORD()
                self.assertTrue(fn(msvcrt.get_osfhandle(stream.fileno()), 0x900c4, None, 0, None, 0, ctypes.byref(count), None))
            stream.seek(4 * 1024**3); stream.write(b'\nLAST controlled log\n')
        reads = []; original = self.directory.open
        class Counted:
            def __init__(self, stream): self.stream = stream
            def __getattr__(self, name): return getattr(self.stream, name)
            def read(self, size=-1):
                reads.append(size); return self.stream.read(size)
        @contextlib.contextmanager
        def counted(*args, **kwargs):
            with original(*args, **kwargs) as (stream, info): yield Counted(stream), info
        with patch.object(self.directory, 'open', counted):
            raw, metadata = self.directory.read('worker.log', d.LOG_LIMIT, tail=True)
        self.assertEqual(reads, [d.LOG_LIMIT]); self.assertEqual(len(raw), d.LOG_LIMIT)
        self.assertGreater(metadata['input_bytes'], 4 * 1024**3)
        self.assertTrue(raw.endswith(b'LAST controlled log\n'))

    def test_oversized_response_does_not_read_payload(self):
        (self.work / 'response.json').write_bytes(b'x' * (d.RESPONSE_LIMIT + 1))
        value, metadata = d._limited_json(self.directory, 'response.json', d.RESPONSE_LIMIT)
        self.assertIsNone(value); self.assertEqual(metadata['bytes_read'], 0)
        self.assertEqual(metadata['state'], 'oversized')

    def test_unicode_invalid_utf8_empty_and_long_line_tails(self):
        for raw in (b'', b'\xff\xfe bad', ('汉' * 30000).encode(), b'x' * d.LOG_LIMIT):
            (self.work / 'worker.log').write_bytes(raw)
            value, meta = self.directory.read('worker.log', d.LOG_LIMIT, tail=True)
            cleaned, flags = d.text_tail(value, meta)
            cleaned.decode('utf8'); self.assertLessEqual(len(cleaned), d.LOG_LIMIT)
            self.assertEqual(flags['bytes_read'], min(len(raw), d.LOG_LIMIT))

    def test_hardlink_and_file_identity_replacement_fail_before_read(self):
        path = self.work / 'worker.log'; path.write_bytes(b'private')
        link = self.root / 'linked.log'; os.link(path, link)
        with self.assertRaises(AppError): self.directory.read('worker.log', 64)
        link.unlink()
        original_open = os.open
        def changed(file, flags, *args, **kwargs):
            if Path(file) == path:
                path.rename(path.with_suffix('.old')); path.write_bytes(b'replacement')
            return original_open(file, flags, *args, **kwargs)
        with patch.object(d.os, 'open', side_effect=changed), self.assertRaises(AppError):
            self.directory.read('worker.log', 64)

    def test_directory_junction_and_traversal_are_rejected(self):
        target = self.root / 'outside'; target.mkdir()
        junction = self.work / 'junction'
        if os.name == 'nt':
            completed = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(junction), str(target)], capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        else: junction.symlink_to(target, target_is_directory=True)
        try:
            with self.assertRaises(AppError): d.Directory(junction)
        finally: junction.rmdir() if os.name == 'nt' else junction.unlink()
        with self.assertRaises(AppError): self.directory.child('../outside')
        with self.assertRaises(AppError): d.Directory(self.work / '..' / 'outside')

    def test_changed_directory_is_rejected(self):
        self.work.rename(self.root / 'old'); self.work.mkdir()
        with self.assertRaises(AppError): self.directory.check()

    def test_history_count_and_age_retain_only_finished_records(self):
        for _ in range(34): self.capture()
        rows = d.list_records(self.root)['records']; self.assertEqual(len(rows), 32)
        first = rows[-1]['diagnostic_id']
        self.rewrite_manifest({'diagnostic_id': first}, lambda v: v.update(created_at_utc=(datetime.now(timezone.utc) - timedelta(days=15)).isoformat()))
        store = d._store(self.root)
        with d.store_lock(store): result = d.retain(store)
        self.assertIn(first, result['removed']); self.assertEqual(len(d.list_records(self.root)['records']), 31)

    def test_active_large_staging_is_protected_and_refuses_new_capture(self):
        store = d._store(self.root, create=True)
        stage = store.child('.writing_' + 'a' * 32, create=True)
        with (stage.path / 'worker.stderr.log').open('wb') as stream: stream.truncate(d.HISTORY_BYTES)
        error = AppError('ORIGINAL', 'fixture', exit_code=6); self.session().capture(self.work, error)
        self.assertEqual(error.diagnostics['status'], 'unavailable')
        self.assertEqual(error.diagnostics['warnings'][0]['code'], 'DIAGNOSTIC_STORE_FULL')
        self.assertTrue(stage.path.is_dir())

    def test_concurrent_store_writer_gets_secondary_lock_warning(self):
        store = d._store(self.root, create=True)
        with d.store_lock(store):
            error = AppError('ORIGINAL', 'fixture', exit_code=6); self.session().capture(self.work, error)
        self.assertEqual(error.diagnostics['status'], 'unavailable')
        self.assertEqual(error.diagnostics['warnings'][0]['code'], 'DIAGNOSTIC_STORE_LOCKED')

    def test_tampered_content_and_manifest_reference_are_rejected(self):
        error, (_, files) = self.capture(); ref = error.diagnostics
        with self.assertRaises(AppError): d.inspect_record(self.root, ref['diagnostic_id'], expected_sha256='sha256:' + '0' * 64)
        path = self.root.joinpath(*d.STORE_PARTS, ref['diagnostic_id'], 'worker.stderr.log')
        path.write_bytes(b'tampered')
        with self.assertRaises(AppError): d.inspect_record(self.root, ref['diagnostic_id'])

    def test_unknown_files_and_invalid_manifest_are_rejected(self):
        error, _ = self.capture(); ref = error.diagnostics
        path = self.root.joinpath(*d.STORE_PARTS, ref['diagnostic_id'])
        (path / 'extra.bin').write_bytes(b'unexpected')
        with self.assertRaises(AppError): d.inspect_record(self.root, ref['diagnostic_id'])
        (path / 'extra.bin').unlink()
        self.rewrite_manifest(ref, lambda v: v.update(extra_private_data='not whitelisted'))
        with self.assertRaises(AppError): d.inspect_record(self.root, ref['diagnostic_id'])

    def test_per_file_budget_is_checked_before_payload_read(self):
        error, _ = self.capture(); ref = error.diagnostics
        self.rewrite_manifest(ref, lambda v: v['files']['worker.stderr.log'].update(bytes=d.LOG_LIMIT + 1))
        with self.assertRaises(AppError) as raised: d.inspect_record(self.root, ref['diagnostic_id'])
        self.assertEqual(raised.exception.code, 'DIAGNOSTIC_MANIFEST_INVALID')

    def test_zip_export_is_opt_in_bounded_new_and_hash_matched(self):
        error, (_, files) = self.capture(); ref = error.diagnostics; output = self.root / '诊断.zip'
        d.export_record(self.root, ref['diagnostic_id'], output, dry_run=True)
        self.assertFalse(output.exists())
        result = d.export_record(self.root, ref['diagnostic_id'], output, expected_sha256=ref['manifest_sha256'])
        self.assertLessEqual(result['archive_bytes'], d.ZIP_LIMIT)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), set(files))
            for name, raw in files.items(): self.assertEqual(archive.read(name), raw)
        before = output.read_bytes()
        with self.assertRaises(AppError): d.export_record(self.root, ref['diagnostic_id'], output)
        self.assertEqual(output.read_bytes(), before)

    def test_manifest_missing_is_a_structured_not_found(self):
        with self.assertRaises(AppError) as raised: d.inspect_record(self.root, 'diag_' + '0' * 32)
        self.assertEqual((raised.exception.code, raised.exception.exit_code), ('DIAGNOSTIC_NOT_FOUND', 3))

    def test_workspace_capture_precedes_cleanup_and_callback_cannot_mask_primary(self):
        seen = []; cache = self.root / 'cache'; cache.mkdir()
        original = AppError('ORIGINAL', 'fixture', exit_code=6)
        def callback(work, exc):
            seen.append((work.is_dir(), exc)); raise OSError('controlled diagnostic failure')
        with self.assertRaises(AppError) as raised:
            with _pipeline_workspace(cache, callback): raise original
        self.assertIs(raised.exception, original); self.assertEqual(seen, [(True, original)])
        self.assertFalse(list(cache.iterdir()))

    def test_workspace_cleanup_failure_is_secondary(self):
        cache = self.root / 'cache'; cache.mkdir()
        original = AppError('ORIGINAL', 'fixture', exit_code=6)
        with patch('ai_ad_editor.local_matting.shutil.rmtree', side_effect=OSError('controlled cleanup failure')):
            with self.assertRaises(AppError) as raised:
                with _pipeline_workspace(cache): raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(original.diagnostics['warnings'][0]['code'], 'MATTING_CACHE_CLEANUP_FAILED')


class NativeDiagnosticIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case = matting_tests.NativeMattingTests('test_registration_dry_run_and_inspection_do_not_infer')
        self.case.setUpClass(); self.case.setUp(); self.addCleanup(self.case.doCleanups)
        self.case.register()

    def inspect_failure(self, code, result, expected):
        self.assertEqual(code, expected, result)
        error = result['errors'][0]; ref = error['diagnostics']
        self.assertEqual(ref['status'], 'stored', result)
        manifest, files = d.inspect_record(self.case.root, ref['diagnostic_id'], expected_sha256=ref['manifest_sha256'])
        self.assertEqual(error['operation_id'], manifest['operation_id'])
        self.case.assert_no_outputs()
        return manifest

    def test_each_native_role_failure_retains_natural_exit_and_cleans_others(self):
        original_popen = subprocess.Popen
        for role in d.ROLES:
            before = self.case.metadata(); children = []; index = [0]
            def controlled(command, **kwargs):
                if 'rawvideo' not in command and str(self.case.worker) not in command:
                    return original_popen(command, **kwargs)
                current = d.ROLES[index[0]]; index[0] += 1
                program = 'import sys;print("controlled role failure",file=sys.stderr);sys.exit(17)' if current == role else 'import time;time.sleep(30)'
                process = original_popen([sys.executable, '-I', '-B', '-c', program], **kwargs); children.append(process); return process
            with self.subTest(role=role), self.case.fake_command('fail'), patch('ai_ad_editor.local_matting.subprocess.Popen', side_effect=controlled):
                code, result = invoke(*self.case.options_for_matting())
            manifest = self.inspect_failure(code, result, 6)
            rows = {row['role']: row for row in manifest['processes']}
            self.assertEqual(rows[role]['observed_exit']['raw'], 17)
            self.assertFalse(rows[role]['cleanup_requested']); self.assertIn(role, manifest['trigger']['first_failure_roles'])
            self.assertTrue(all(p.poll() is not None for p in children)); self.assertEqual(self.case.metadata(), before)

    def test_worker_start_failure_retains_not_started_encoder(self):
        original_popen = subprocess.Popen; index = [0]; children = []
        def controlled(command, **kwargs):
            if 'rawvideo' not in command and str(self.case.worker) not in command:
                return original_popen(command, **kwargs)
            index[0] += 1
            if index[0] == 2: raise OSError('controlled startup failure')
            p = original_popen([sys.executable, '-I', '-B', '-c', 'import time;time.sleep(30)'], **kwargs); children.append(p); return p
        before = self.case.metadata()
        with self.case.fake_command('fail'), patch('ai_ad_editor.local_matting.subprocess.Popen', side_effect=controlled): code, result = invoke(*self.case.options_for_matting())
        manifest = self.inspect_failure(code, result, 6)
        rows = {row['role']: row for row in manifest['processes']}
        self.assertEqual(rows['worker']['state'], 'start_failed'); self.assertEqual(rows['encoder']['state'], 'not_started')
        self.assertTrue(all(p.poll() is not None for p in children)); self.assertEqual(before, self.case.metadata())

    def test_cancel_and_timeout_keep_trigger_and_original_metadata(self):
        for mode in ('cancel', 'wait'):
            cancel = self.case.base / ('cancel-' + mode); before = self.case.metadata()
            original_popen = subprocess.Popen
            def notify_worker_started(command, **kwargs):
                process = original_popen(command, **kwargs)
                # Cancellation must actually arrive before the deadline. Import
                # speed of the fake NumPy worker is not a cancellation clock.
                if mode == 'cancel' and str(self.case.worker) in list(map(str,command)):
                    cancel.write_text('cancel after worker start',encoding='utf8')
                return process
            with self.case.fake_command(mode, str(cancel)), patch('ai_ad_editor.local_matting.subprocess.Popen',side_effect=notify_worker_started):
                code, result = invoke(*self.case.options_for_matting(), '--cancel-file', str(cancel), '--timeout-seconds', '2')
            manifest = self.inspect_failure(code, result, 8)
            self.assertEqual(manifest['error']['code'], 'CANCELLED' if mode == 'cancel' else 'TIMEOUT')
            self.assertTrue(any(row['cleanup_requested'] for row in manifest['processes']))
            self.assertEqual(before, self.case.metadata())

    def test_bad_worker_report_survives_rollback_and_readonly_cli(self):
        before = self.case.metadata()
        with self.case.fake_command('bad_json'): code, result = invoke(*self.case.options_for_matting())
        manifest = self.inspect_failure(code, result, 6); ref = result['errors'][0]['diagnostics']
        code, listing = invoke('diagnostics', 'list', '--project', str(self.case.root), '--operation-id', result['errors'][0]['operation_id'])
        self.assertEqual(code, 0, listing); self.assertEqual(len(listing['data']['records']), 1)
        args = ('--project', str(self.case.root), '--diagnostic-id', ref['diagnostic_id'], '--expected-manifest-sha256', ref['manifest_sha256'])
        code, shown = invoke('diagnostics', 'show', *args)
        self.assertEqual(code, 0, shown); self.assertNotIn('logs', shown['data'])
        code, shown = invoke('diagnostics', 'show', *args, '--include-logs')
        self.assertEqual(code, 0, shown); self.assertEqual(len(shown['data']['logs']), 3)
        output = self.case.base / 'failure.zip'
        code, value = invoke('diagnostics', 'export', *args, '--output', str(output), '--dry-run')
        self.assertEqual(code, 0, value); self.assertFalse(output.exists())
        code, value = invoke('diagnostics', 'export', *args, '--output', str(output))
        self.assertEqual(code, 0, value); self.assertTrue(output.is_file()); self.assertEqual(self.case.metadata(), before)

    def test_success_has_no_failure_history(self):
        with self.case.fake_command(): code, result = invoke(*self.case.options_for_matting())
        self.assertEqual(code, 0, result); self.assertEqual(d.list_records(self.case.root)['records'], [])

    def test_cli_export_rejects_junction_without_resolving_it_away(self):
        with self.case.fake_command('fail'): code, result = invoke(*self.case.options_for_matting())
        self.inspect_failure(code, result, 6); ref = result['errors'][0]['diagnostics']
        outside = self.case.base / 'outside'; outside.mkdir(); link = self.case.root / 'linked'
        if os.name == 'nt':
            p = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
        else: link.symlink_to(outside, target_is_directory=True)
        try:
            code, result = invoke('diagnostics', 'export', '--project', str(self.case.root), '--diagnostic-id', ref['diagnostic_id'], '--output', 'linked/failure.zip')
            self.assertEqual(code, 10, result); self.assertFalse((outside / 'failure.zip').exists())
        finally: link.rmdir() if os.name == 'nt' else link.unlink()

    def test_native_failure_with_diagnostic_write_error_keeps_business_failure(self):
        with self.case.fake_command('fail'), patch.object(d.Directory, 'write', side_effect=OSError('controlled no space')):
            code, result = invoke(*self.case.options_for_matting())
        self.assertEqual(code, 6, result); self.assertEqual(result['errors'][0]['code'], 'MATTING_PIPELINE_FAILED')
        self.assertEqual(result['errors'][0]['diagnostics']['status'], 'unavailable'); self.case.assert_no_outputs()


if __name__ == '__main__': unittest.main()
