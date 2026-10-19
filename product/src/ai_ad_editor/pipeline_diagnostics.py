"""Bounded, local failure evidence for native video pipelines.

Problem summaries, redaction and limited history are informed by OpenFilm
problems.mjs at f6a65ae54fa1c10ec482eeb84dc9ffa6ef33c4d8 (MIT).
Copyright (c) 2026 OpenFilm contributors. See OPENFILM_LICENSE.txt.
The byte readers, process observations, storage and integration are local work.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid
import zipfile

from .errors import AppError
from .policy import REMOTE_MARKERS

PROTOCOL = 'agent-native-pipeline-diagnostic-v1'
ROLES = ('decoder', 'worker', 'encoder')
LOG_LIMIT = 64 * 1024
RESPONSE_LIMIT = 128 * 1024
SUMMARY_LIMIT = 32 * 1024
MANIFEST_LIMIT = 64 * 1024
RECORD_LIMIT = 512 * 1024
ZIP_LIMIT = 768 * 1024
HISTORY_COUNT = 32
HISTORY_BYTES = 64 * 1024 * 1024
HISTORY_DAYS = 14
SCAN_LIMIT = 512
STORE_PARTS = ('renders', 'diagnostics', 'pipelines')
ID_RE = re.compile(r'diag_[0-9a-f]{32}\Z')
HASH_RE = re.compile(r'sha256:[0-9a-f]{64}\Z')
FILES = frozenset(('decoder.stderr.log', 'worker.stderr.log', 'encoder.stderr.log', 'request.json', 'response.json'))
STAGES = frozenset(('loading-local-text-encoder', 'loading-local-video-transformer-and-vae',
                    'joint-video-denoising', 'verifying-local-artifacts'))


def digest(value: bytes) -> str:
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf8')


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fault(code: str) -> AppError:
    return AppError(code, '本地管道诊断不可用或未通过边界核验', exit_code=10)


def _identity(info):
    return info.st_dev, info.st_ino


def _ordinary(info, *, directory=False):
    return (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def _final_windows_path(fd):
    import ctypes
    import msvcrt
    from ctypes import wintypes
    function = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
    function.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    function.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = function(wintypes.HANDLE(msvcrt.get_osfhandle(fd)), buffer, len(buffer), 0)
    if not 0 < length < len(buffer):
        raise fault('DIAGNOSTIC_HANDLE_PATH_INVALID')
    value = buffer.value
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return os.path.normcase(os.path.abspath(value))


class Directory:
    """A plain directory chain; reads validate the opened file before consuming it."""
    def __init__(self, path: Path):
        if '..' in Path(path).parts:
            raise fault('DIAGNOSTIC_PATH_INVALID')
        self.path = Path(os.path.abspath(path))
        if str(self.path).startswith('\\\\'):
            raise fault('DIAGNOSTIC_PATH_INVALID')
        self.chain = []
        for parent in reversed((self.path, *self.path.parents)):
            info = parent.lstat()
            if not _ordinary(info, directory=True):
                raise fault('DIAGNOSTIC_PATH_INVALID')
            self.chain.append((parent, _identity(info)))

    def check(self):
        for path, identity in self.chain:
            info = path.lstat()
            if not _ordinary(info, directory=True) or _identity(info) != identity:
                raise fault('DIAGNOSTIC_PATH_CHANGED')

    def child(self, name, *, create=False):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', name) or name in ('.', '..'):
            raise fault('DIAGNOSTIC_PATH_INVALID')
        self.check()
        path = self.path / name
        if create:
            try:
                path.mkdir()
            except FileExistsError:
                pass
        result = Directory(path)
        self.check()
        return result

    @contextlib.contextmanager
    def open(self, name, *, create=False):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', name) or name in ('.', '..'):
            raise fault('DIAGNOSTIC_PATH_INVALID')
        self.check()
        path = self.path / name
        before = None if create else path.lstat()
        if before is not None and (not _ordinary(before) or before.st_nlink != 1):
            raise fault('DIAGNOSTIC_FILE_INVALID')
        flags = (os.O_RDWR | os.O_CREAT | os.O_EXCL) if create else os.O_RDONLY
        flags |= getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
        # POSIX opens descend from an already checked directory handle.
        parent_fd = None
        if os.name != 'nt':
            parent_fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            if _identity(os.fstat(parent_fd)) != self.chain[-1][1]:
                os.close(parent_fd)
                raise fault('DIAGNOSTIC_PATH_CHANGED')
        fd = None
        try:
            fd = os.open(path if parent_fd is None else name, flags, 0o600, **({'dir_fd': parent_fd} if parent_fd is not None else {}))
            actual = os.fstat(fd)
            if not _ordinary(actual) or actual.st_nlink != 1 or before is not None and _identity(actual) != _identity(before):
                raise fault('DIAGNOSTIC_FILE_CHANGED')
            if os.name == 'nt' and _final_windows_path(fd) != os.path.normcase(str(path)):
                raise fault('DIAGNOSTIC_HANDLE_PATH_INVALID')
            self.check()
            with os.fdopen(fd, 'r+b' if create else 'rb') as stream:
                fd = None
                yield stream, actual
                after = os.fstat(stream.fileno())
                self.check()
                if _identity(after) != _identity(actual) or not create and (after.st_size, after.st_mtime_ns) != (actual.st_size, actual.st_mtime_ns):
                    raise fault('DIAGNOSTIC_FILE_CHANGED')
        finally:
            if fd is not None:
                os.close(fd)
            if parent_fd is not None:
                os.close(parent_fd)

    def read(self, name, limit, *, tail=False):
        with self.open(name) as (stream, info):
            if not tail and info.st_size > limit:
                return None, {'state': 'oversized', 'input_bytes': info.st_size, 'bytes_read': 0}
            offset = max(0, info.st_size - limit) if tail else 0
            stream.seek(offset)
            raw = stream.read(min(limit, info.st_size))
            if len(raw) != info.st_size - offset:
                raise fault('DIAGNOSTIC_FILE_CHANGED')
        return raw, {'state': 'read', 'input_bytes': info.st_size, 'offset': offset, 'bytes_read': len(raw),
                     'input_truncated': bool(offset), 'input_segment_sha256': digest(raw)}

    def write(self, name, raw):
        if not isinstance(name, str) or not 1 <= len(name) <= 100 or name in ('.', '..') or any(c in name for c in '/\\:'):
            raise fault('DIAGNOSTIC_PATH_INVALID')
        temporary = '.tmp_' + uuid.uuid4().hex
        try:
            with self.open(temporary, create=True) as (stream, _):
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self.check()
            target = self.path / name
            if target.exists() or target.is_symlink():
                raise fault('DIAGNOSTIC_OUTPUT_EXISTS')
            if os.name == 'nt':
                (self.path / temporary).rename(target)
            else:
                os.link(self.path / temporary, target, follow_symlinks=False)
                (self.path / temporary).unlink()
            self.check()
        finally:
            # Delete only our fixed temporary filename after rechecking its parent.
            self.check()
            (self.path / temporary).unlink(missing_ok=True)


def redact(text, *, literals=()):
    # Work on bounded input, including before expensive regular expressions.
    text = text[:RESPONSE_LIMIT]
    for literal in sorted({str(v) for v in literals if v}, key=len, reverse=True):
        text = text.replace(literal, '<redacted-local-input>')
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = re.sub(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9_+/.=:-]+', '<redacted-authorization>', text)
    text = re.sub(r'(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization|secret|token)\s*[=:]\s*["\']?[^\s,"\'<>]+', '<redacted-secret>', text)
    text = re.sub(r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|hf_[A-Za-z0-9_]{8,})\b', '<redacted-secret>', text)
    text = re.sub(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', '<redacted-email>', text, flags=re.I)
    text = re.sub(r'\b[A-Za-z][A-Za-z0-9+.-]*://[^\s<>"\']+', lambda m: '<reference-' + hashlib.sha256(m[0].encode('utf8')).hexdigest() + '>', text)
    for marker in REMOTE_MARKERS:
        text = re.sub(re.escape(marker) + r'[^\s<>"\']*', lambda m: '<reference-' + hashlib.sha256(m[0].encode('utf8')).hexdigest() + '>', text, flags=re.I)
    text = re.sub(r'(?i)(?:[A-Z]:[\\/]|/Users/|/home/)[^\r\n"\'<>]*', '<redacted-local-path>', text)
    text = ''.join(c if c in '\n\r\t' or ord(c) >= 32 and ord(c) != 127 else '\ufffd' for c in text)
    return text


def text_tail(raw, metadata, *, literals=()):
    try:
        text = raw.decode('utf8')
        invalid = False
    except UnicodeDecodeError:
        text = raw.decode('utf8', errors='replace')
        invalid = True
    boundary_removed = False
    if metadata['offset'] and '\n' in text:
        text = text.split('\n', 1)[1]
        boundary_removed = True
    cleaned = redact(text, literals=literals).encode('utf8')
    output_truncated = len(cleaned) > LOG_LIMIT
    cleaned = cleaned[-LOG_LIMIT:].decode('utf8', errors='ignore').encode('utf8')
    return cleaned, {**metadata, 'invalid_utf8_replaced': invalid, 'partial_first_line_removed': boundary_removed,
                     'output_truncated': output_truncated, 'redacted': True}


def exit_value(value, *, platform=None):
    if value is None:
        return None
    result = {'raw': value}
    if (platform or sys.platform) == 'win32':
        unsigned = value & 0xffffffff
        result.update(unsigned=unsigned, hex=f'0x{unsigned:08x}')
    return result


class Processes:
    def __init__(self):
        self.rows = {role: {'role': role, 'state': 'not_started', 'pid': None, 'started_at_utc': None,
                            'observed_exit': None, 'final_exit': None, 'cleanup_requested': False} for role in ROLES}
        self.handles = {}
        self.first_failure_roles = []
        self.first_failure_at_utc = None

    def started(self, role, process):
        self.handles[role] = process
        self.rows[role].update(state='running', pid=process.pid, started_at_utc=utc())

    def start_failed(self, role):
        self.rows[role]['state'] = 'start_failed'

    def observe(self):
        failures = []
        for role, process in self.handles.items():
            code = process.poll()
            row = self.rows[role]
            if code is not None and row['observed_exit'] is None and not row['cleanup_requested']:
                row.update(state='exited', observed_exit=exit_value(code), observed_at_utc=utc())
            if code not in (None, 0) and not row['cleanup_requested']:
                failures.append(role)
        if failures and self.first_failure_at_utc is None:
            self.first_failure_roles = failures
            self.first_failure_at_utc = utc()
        return failures

    def before_cleanup(self):
        self.observe()
        for role, process in self.handles.items():
            if process.poll() is None:
                self.rows[role].update(cleanup_requested=True, cleanup_requested_at_utc=utc())

    def finished(self):
        for role, process in self.handles.items():
            self.rows[role]['final_exit'] = exit_value(process.poll())
            self.rows[role]['state'] = 'terminated_by_cleanup' if self.rows[role]['cleanup_requested'] else 'exited'


def _store(root, *, create=False):
    result = Directory(root)
    for part in STORE_PARTS:
        result = result.child(part, create=create)
    return result


@contextlib.contextmanager
def store_lock(store):
    path = store.path / '.store.lock'
    if not path.exists():
        try:
            with store.open('.store.lock', create=True) as (handle, _):
                handle.write(b'0'); handle.flush()
        except FileExistsError:
            pass
    # Only a fixed, plain, single-link lock file may be reopened for writing.
    with store.open('.store.lock') as (checked, _):
        checked_fd = checked.fileno()
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(checked_fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise fault('DIAGNOSTIC_STORE_LOCKED') from exc
            try:
                yield
            finally:
                checked.seek(0); msvcrt.locking(checked_fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(checked_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise fault('DIAGNOSTIC_STORE_LOCKED') from exc
            try:
                yield
            finally:
                fcntl.flock(checked_fd, fcntl.LOCK_UN)


def _record(store, diagnostic_id):
    if not ID_RE.fullmatch(diagnostic_id):
        raise fault('DIAGNOSTIC_ID_INVALID')
    directory = store.child(diagnostic_id)
    raw, _ = directory.read('manifest.json', MANIFEST_LIMIT)
    if raw is None:
        raise fault('DIAGNOSTIC_MANIFEST_INVALID')
    try:
        manifest = strict_json(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise fault('DIAGNOSTIC_MANIFEST_INVALID') from exc
    if not isinstance(manifest, dict) or manifest.get('protocol') != PROTOCOL or manifest.get('diagnostic_id') != diagnostic_id:
        raise fault('DIAGNOSTIC_MANIFEST_INVALID')
    keys = {'protocol', 'diagnostic_id', 'operation_id', 'created_at_utc', 'platform', 'root_cause', 'error',
            'trigger', 'processes', 'progress', 'binding', 'files', 'warnings', 'limits', 'network'}
    if set(manifest) != keys or manifest['root_cause'] != 'unknown' or manifest['network'] != 'disabled' or manifest['limits'] != limits():
        raise fault('DIAGNOSTIC_MANIFEST_INVALID')
    try:
        stamp = datetime.fromisoformat(manifest['created_at_utc'])
        if stamp.tzinfo is None:
            raise ValueError('timezone required')
    except (TypeError, ValueError) as exc:
        raise fault('DIAGNOSTIC_MANIFEST_INVALID') from exc
    if not isinstance(manifest['processes'], list) or len(manifest['processes']) != 3 or [r.get('role') for r in manifest['processes'] if isinstance(r, dict)] != list(ROLES):
        raise fault('DIAGNOSTIC_MANIFEST_INVALID')
    files = manifest.get('files')
    if not isinstance(files, dict) or set(files) - FILES or len(files) > 5:
        raise fault('DIAGNOSTIC_MANIFEST_INVALID')
    payloads = {'manifest.json': raw}
    for name, entry in files.items():
        budget = LOG_LIMIT if name.endswith('.log') else SUMMARY_LIMIT
        if not isinstance(entry, dict) or set(entry) != {'bytes', 'sha256', 'input'} or type(entry.get('bytes')) is not int or not 0 <= entry['bytes'] <= budget or not HASH_RE.fullmatch(str(entry.get('sha256', ''))):
            raise fault('DIAGNOSTIC_MANIFEST_INVALID')
        payload, _ = directory.read(name, entry['bytes'])
        if payload is None or len(payload) != entry['bytes'] or digest(payload) != entry['sha256']:
            raise fault('DIAGNOSTIC_INTEGRITY_FAILED')
        payloads[name] = payload
    if sum(len(payloads.get(name, b'')) for name in ('request.json', 'response.json')) > SUMMARY_LIMIT:
        raise fault('DIAGNOSTIC_BUDGET_EXCEEDED')
    if sum(map(len, payloads.values())) > RECORD_LIMIT:
        raise fault('DIAGNOSTIC_BUDGET_EXCEEDED')
    with os.scandir(directory.path) as scan:
        names = [entry.name for _, entry in zip(range(9), scan)]
    if set(names) != set(payloads) or len(names) > 8:
        raise fault('DIAGNOSTIC_MANIFEST_INVALID')
    directory.check()
    return directory, manifest, payloads


def _entries(store):
    result = []; staging_bytes = 0
    with os.scandir(store.path) as scan:
        for index, entry in enumerate(scan):
            if index >= SCAN_LIMIT:
                raise fault('DIAGNOSTIC_STORE_SCAN_LIMIT')
            if entry.name == '.store.lock':
                continue
            if ID_RE.fullmatch(entry.name):
                directory, manifest, payloads = _record(store, entry.name)
                stamp = datetime.fromisoformat(manifest['created_at_utc'])
                if stamp.tzinfo is None:
                    raise fault('DIAGNOSTIC_MANIFEST_INVALID')
                result.append((stamp.timestamp(), directory, sum(map(len, payloads.values())), manifest))
            elif re.fullmatch(r'\.writing_[0-9a-f]{32}', entry.name):
                directory = store.child(entry.name)
                with os.scandir(directory.path) as children:
                    for child_index, child in enumerate(children):
                        if child_index >= 8:
                            raise fault('DIAGNOSTIC_STORE_FULL')
                        # Windows DirEntry.stat may omit link count (0); lstat
                        # supplies the actual file identity/link information.
                        info = (directory.path / child.name).lstat()
                        if not _ordinary(info) or info.st_nlink != 1:
                            raise fault('DIAGNOSTIC_FILE_INVALID')
                        staging_bytes += info.st_size
            else:
                raise fault('DIAGNOSTIC_STORE_ENTRY_INVALID')
    return sorted(result, key=lambda row: row[0]), staging_bytes


def _remove_record(store, directory):
    # Fixed, validated record files only; never recurse into an untrusted tree.
    _, _, payloads = _record(store, directory.path.name)
    for name in payloads:
        directory.check(); (directory.path / name).unlink()
    directory.check(); directory.path.rmdir(); store.check()


def retain(store, *, now=None, reserve=0):
    now = time.time() if now is None else now
    rows, active_bytes = _entries(store)
    total = sum(row[2] for row in rows) + active_bytes
    removed = []
    for index, (stamp, directory, size, _) in enumerate(rows):
        if now - stamp <= HISTORY_DAYS * 86400 and len(rows) - len(removed) <= HISTORY_COUNT and total + reserve <= HISTORY_BYTES:
            break
        _remove_record(store, directory); total -= size; removed.append(directory.path.name)
    if total + reserve > HISTORY_BYTES:
        raise fault('DIAGNOSTIC_STORE_FULL')
    return {'removed': removed, 'bytes': total, 'active_staging_bytes': active_bytes}


def strict_json(raw):
    def reject_constant(value):
        raise ValueError('nonfinite JSON constant')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError('nonfinite JSON number')
        return parsed
    result = json.loads(raw, parse_constant=reject_constant, parse_float=finite_float, object_pairs_hook=pairs)
    pending = [(result, 0)]; nodes = 0
    while pending:
        value, depth = pending.pop(); nodes += 1
        if depth > 32 or nodes > 4096:
            raise ValueError('JSON structural budget')
        if isinstance(value, dict): pending.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list): pending.extend((v, depth + 1) for v in value)
    return result


def _limited_json(directory, name, limit):
    try:
        raw, metadata = directory.read(name, limit)
        if raw is None:
            return None, metadata
        try:
            return strict_json(raw), metadata
        except (ValueError, UnicodeError, RecursionError):
            return None, {**metadata, 'state': 'invalid_json'}
    except FileNotFoundError:
        return None, {'state': 'missing', 'bytes_read': 0}


def progress_snapshot(directory, frames):
    value, metadata = _limited_json(directory, 'progress.json', SUMMARY_LIMIT)
    if not isinstance(value, dict) or type(value.get('frames')) is not int or not 0 <= value['frames'] <= frames:
        return {**metadata, 'state': metadata['state'] if value is None else 'invalid_frames'}
    result = {**metadata, 'frames': value['frames']}
    stage = value.get('stage')
    if stage is None:
        result['stage_state'] = 'not_reported'
    elif isinstance(stage, str) and (stage in STAGES or re.fullmatch(r'joint-video-denoising-step-(?:[1-9]|[1-9][0-9]|100)', stage)):
        result.update(stage_state='reported', stage=stage)
    else:
        result.update(stage_state='unknown', stage_sha256=digest(encoded(stage)))
    return result


def binding(request):
    adapter = request.get('adapter', {})
    generation = request.get('generation', {})
    values = {key: generation[key] for key in ('seed', 'inference_steps', 'window_frames', 'window_overlap', 'guidance_scale',
        'conditioning_scale', 'max_sequence_length', 'flow_shift', 'model_input_scale') if type(generation.get(key)) in (int, float) and math.isfinite(generation[key])}
    for key in ('prompt', 'negative_prompt'):
        if isinstance(generation.get(key), str):
            values[key + '_sha256'] = digest(generation[key].encode('utf8'))
    artifacts = [{key: item.get(key) for key in ('role', 'sha256', 'bytes')} for item in adapter.get('artifacts', [])]
    return {'request_sha256': request.get('request_sha256'), 'source_sha256': request.get('source', {}).get('sha256'),
        'adapter_sha256': adapter.get('sha256'), 'model_sha256': adapter.get('model_sha256'),
        'python_executable_sha256': adapter.get('executable_sha256'), 'artifacts_sha256': digest(encoded(artifacts)),
        'parameters_sha256': digest(encoded({key: request.get(key) for key in ('video', 'range', 'inpainting', 'outpainting', 'generation', 'mask')})),
        'generation': values, 'engine': request.get('engine'), 'runtime_versions': 'not_probed_by_diagnostics'}


class Session:
    def __init__(self, root, plan, adapter, operation_id=None):
        self.root = Path(root)
        self.request = {**plan, 'adapter': adapter}
        self.operation_id = operation_id
        self.processes = Processes()
        self.prepared_directory = None
        self.progress = {'state': 'not_observed'}
        self.stage = 'preparing'
        self.start_failure_role = None
        self.last_reported_frame = None
        self.cleanup_warnings = []
        self.literals = tuple(str(v) for v in (self.root, plan.get('source', {}).get('path'),
            adapter.get('model_path'), adapter.get('executable'), plan.get('generation', {}).get('prompt'),
            plan.get('generation', {}).get('negative_prompt')) if v)

    def prepare(self, work, request):
        self.prepared_directory = Directory(work)
        self.request = request
        self.stage = 'starting'

    def observe(self):
        self.processes.observe()

    def cause(self, value):
        return redact(value, literals=self.literals)

    def failure_text(self):
        result = []
        for name, limit in [('response.json', 2500), *((role + '.log', 1500) for role in ROLES)]:
            try:
                raw, _ = self.prepared_directory.read(name, limit, tail=True)
                result.append(raw.decode('utf8', errors='replace'))
            except Exception:
                result.append('<unavailable-failure-text>')
        return self.cause('\n'.join(result))

    def read_progress(self):
        try:
            return progress_snapshot(self.prepared_directory, int(self.request.get('video', {}).get('frames', 0)))
        except Exception as exc:
            return {'state': 'unavailable', 'code': getattr(exc, 'code', 'DIAGNOSTIC_PROGRESS_UNAVAILABLE')}

    def capture(self, work, error):
        """Best-effort evidence must never replace the original business failure."""
        try:
            reference = self._capture(work, error)
        except Exception as secondary:
            reference = {'protocol': PROTOCOL, 'status': 'unavailable', 'warnings': [
                {'code': getattr(secondary, 'code', 'DIAGNOSTIC_CAPTURE_FAILED'), 'python_type': type(secondary).__name__}]}
        try:
            error.diagnostics = reference
            if isinstance(error, AppError) and self.operation_id:
                error.operation_id = self.operation_id
        except (AttributeError, TypeError):
            pass

    def _capture(self, work, error):
        directory = self.prepared_directory
        if directory is None or Path(work) != directory.path:
            raise fault('DIAGNOSTIC_NOT_PREPARED')
        directory.check()
        if any(handle.poll() is None for handle in self.processes.handles.values()):
            raise fault('DIAGNOSTIC_CHILD_STILL_RUNNING')
        self.processes.finished()
        files = {}; warnings = list(self.cleanup_warnings)
        for role in ROLES:
            try:
                raw, metadata = directory.read(role + '.log', LOG_LIMIT, tail=True)
                payload, metadata = text_tail(raw, metadata, literals=self.literals)
                files[role + '.stderr.log'] = (payload, metadata)
            except Exception as exc:
                warnings.append({'code': getattr(exc, 'code', 'DIAGNOSTIC_LOG_UNAVAILABLE'), 'role': role})
        self.progress = self.read_progress()
        self.progress['last_reported_frame'] = self.last_reported_frame
        self.progress['older_than_reported'] = self.last_reported_frame is not None and type(self.progress.get('frames')) is int and self.progress['frames'] < self.last_reported_frame
        response, response_read = _limited_json(directory, 'response.json', RESPONSE_LIMIT)
        response_summary = {'read': response_read, 'fields': {}}
        if isinstance(response, dict):
            if isinstance(response.get('error'), str):
                # Workers commonly report exceptions in JSON with empty stderr.
                # Keep a bounded, redacted reason without copying the response.
                cleaned = ('worker error - ' + self.cause(response['error'][:2000])).encode('utf8')[:2000]
                response_summary['worker_error'] = cleaned.decode('utf8', errors='ignore')
            for key in ('status', 'engine', 'protocol', 'network'):
                value = response.get(key)
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', value):
                    response_summary['fields'][key] = value
            versions = response.get('versions', {})
            if isinstance(versions, dict):
                response_summary['actual_worker_versions'] = {key: value for key, value in versions.items()
                    if key in ('python', 'numpy', 'torch', 'transformers', 'diffusers', 'safetensors', 'onnxruntime')
                    and isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.+-]{1,80}', value)}
        bound = binding(self.request)
        files['request.json'] = (encoded(bound), {'redacted_summary': True})
        files['response.json'] = (encoded(response_summary), {'redacted_summary': True})
        if len(files['request.json'][0]) + len(files['response.json'][0]) + len(encoded(self.progress)) > SUMMARY_LIMIT:
            raise fault('DIAGNOSTIC_SUMMARY_TOO_LARGE')
        diagnostic_id = 'diag_' + uuid.uuid4().hex
        manifest = {'protocol': PROTOCOL, 'diagnostic_id': diagnostic_id, 'operation_id': self.operation_id,
            'created_at_utc': utc(), 'platform': sys.platform, 'root_cause': 'unknown',
            'error': {'code': getattr(error, 'code', 'OS_ERROR' if isinstance(error, OSError) else 'PYTHON_ERROR'),
                'exit_code': getattr(error, 'exit_code', None), 'python_type': type(error).__name__},
            'trigger': {'stage': self.stage, 'start_failure_role': self.start_failure_role,
                'first_failure_roles': self.processes.first_failure_roles, 'first_failure_at_utc': self.processes.first_failure_at_utc},
            'processes': list(self.processes.rows.values()), 'progress': self.progress, 'binding': bound,
            'files': {name: {'bytes': len(raw), 'sha256': digest(raw), 'input': metadata} for name, (raw, metadata) in files.items()},
            'warnings': warnings, 'limits': limits(), 'network': 'disabled'}
        payload = encoded(manifest)
        if len(payload) > MANIFEST_LIMIT or len(payload) + sum(len(row[0]) for row in files.values()) > RECORD_LIMIT:
            raise fault('DIAGNOSTIC_BUDGET_EXCEEDED')
        store = _store(self.root, create=True)
        with store_lock(store):
            retain(store, reserve=RECORD_LIMIT)
            stage_name = '.writing_' + uuid.uuid4().hex
            stage = store.child(stage_name, create=True)
            for name, (raw, _) in files.items():
                stage.write(name, raw)
            stage.write('manifest.json', payload)
            stage.check(); store.check()
            stage.path.rename(store.path / diagnostic_id)
            store.check()
            try:
                retain(store)
            except Exception as exc:
                warnings = [*warnings, {'code': getattr(exc, 'code', 'DIAGNOSTIC_RETENTION_FAILED')}]
        return {'protocol': PROTOCOL, 'status': 'stored', 'diagnostic_id': diagnostic_id,
            'manifest': '/'.join((*STORE_PARTS, diagnostic_id, 'manifest.json')), 'manifest_sha256': digest(payload),
            'warnings': warnings}


def limits():
    return {'stderr_bytes_each': LOG_LIMIT, 'response_read_bytes': RESPONSE_LIMIT, 'summary_bytes': SUMMARY_LIMIT,
        'manifest_bytes': MANIFEST_LIMIT, 'record_bytes': RECORD_LIMIT, 'archive_bytes': ZIP_LIMIT,
        'files': 8, 'history_records': HISTORY_COUNT, 'history_bytes': HISTORY_BYTES, 'history_days': HISTORY_DAYS}


def list_records(root):
    try:
        store = _store(root)
    except FileNotFoundError:
        return {'protocol': PROTOCOL, 'records': [], 'limits': limits()}
    rows, active_bytes = _entries(store)
    return {'protocol': PROTOCOL, 'records': [{'diagnostic_id': directory.path.name, 'created_at_utc': value['created_at_utc'],
        'operation_id': value['operation_id'], 'error': value['error'], 'bytes': size} for _, directory, size, value in reversed(rows[-HISTORY_COUNT:])],
        'active_staging_bytes': active_bytes, 'limits': limits()}


def inspect_record(root, diagnostic_id, *, expected_sha256=None):
    try:
        _, manifest, payloads = _record(_store(root), diagnostic_id)
    except FileNotFoundError as exc:
        raise AppError('DIAGNOSTIC_NOT_FOUND', '诊断不存在或已按保留策略清理', exit_code=3) from exc
    if expected_sha256 is not None and (not HASH_RE.fullmatch(expected_sha256) or digest(payloads['manifest.json']) != expected_sha256):
        raise fault('DIAGNOSTIC_INTEGRITY_FAILED')
    return manifest, payloads


def export_record(root, diagnostic_id, output, *, expected_sha256=None, dry_run=False):
    manifest, payloads = inspect_record(root, diagnostic_id, expected_sha256=expected_sha256)
    output = Path(os.path.abspath(output))
    if output.suffix.lower() != '.zip' or output.exists() or output.is_symlink():
        raise AppError('DIAGNOSTIC_OUTPUT_INVALID', '诊断导出要求尚不存在的本地 .zip 文件', exit_code=2)
    parent = Directory(output.parent)
    result = {'diagnostic_id': diagnostic_id, 'output': str(output), 'files': len(payloads),
              'source_bytes': sum(map(len, payloads.values())), 'manifest_sha256': digest(payloads['manifest.json'])}
    if dry_run:
        return result
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payloads.items()):
            archive.writestr(name, raw)
    raw = memory.getvalue()
    if len(raw) > ZIP_LIMIT:
        raise fault('DIAGNOSTIC_ARCHIVE_TOO_LARGE')
    parent.write(output.name, raw)
    return {**result, 'archive_bytes': len(raw), 'sha256': digest(raw)}
