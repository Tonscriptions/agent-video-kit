"""Native Windows process-tree lifetime for the optional HTML renderer.

No shell, service, VM or browser download is involved. Children are attached
before receiving work; KILL_ON_JOB_CLOSE covers Chromium descendants as well
as a blocked Node/FFmpeg pipe. This is lifetime containment, not a JS sandbox.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import threading
import time

from .errors import AppError


class BrowserProcessJob:
    def __init__(self, timeout: float, cancel_file: Path | None = None):
        if os.name != 'nt':
            raise AppError('HTML_NATIVE_WINDOWS_REQUIRED', 'HTML worker 当前要求原生 Windows Job Object', exit_code=10)
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]

        class BASIC(ctypes.Structure):
            _fields_ = [('ProcessTime', ctypes.c_int64), ('JobTime', ctypes.c_int64),
                        ('Flags', wintypes.DWORD), ('MinWorking', ctypes.c_size_t),
                        ('MaxWorking', ctypes.c_size_t), ('ActiveLimit', wintypes.DWORD),
                        ('Affinity', ctypes.c_size_t), ('Priority', wintypes.DWORD),
                        ('Scheduling', wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('ReadOps', 'WriteOps', 'OtherOps', 'ReadBytes', 'WriteBytes', 'OtherBytes')]

        class EXTENDED(ctypes.Structure):
            _fields_ = [('Basic', BASIC), ('IO', IO), ('ProcessMemory', ctypes.c_size_t),
                        ('JobMemory', ctypes.c_size_t), ('PeakProcessMemory', ctypes.c_size_t),
                        ('PeakJobMemory', ctypes.c_size_t)]

        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            self._error('CreateJobObjectW')
        limits = EXTENDED()
        limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.api.CloseHandle(self.handle)
            self.handle = None
            self._error('SetInformationJobObject')
        self.seen_pids: set[int] = set()
        self.processes: list[subprocess.Popen] = []
        self.cancel_file = cancel_file
        self.deadline = time.monotonic() + timeout
        self.reason: str | None = None
        self.done = threading.Event()
        self.mutex = threading.RLock()
        self.monitor = threading.Thread(target=self._watch, name='html-native-job-watchdog', daemon=True)
        self.monitor.start()
        self.closed = False

    @staticmethod
    def _error(cause: str):
        raise AppError('HTML_JOB_UNAVAILABLE', '无法约束浏览器子进程；拒绝无回收保障的执行', exit_code=10,
                       cause=f'{cause}: {ctypes.get_last_error()}')

    def pids(self) -> list[int]:
        # 1024 native descendants is far beyond the admitted one-page worker.
        class IDS(ctypes.Structure):
            _fields_ = [('assigned', wintypes.DWORD), ('count', wintypes.DWORD), ('ids', ctypes.c_size_t * 1024)]
        with self.mutex:
            if not self.handle:
                return []
            info = IDS()
            if not self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(info), ctypes.sizeof(info), None):
                self._error('QueryInformationJobObject')
            ids = [int(info.ids[i]) for i in range(info.count)]
            self.seen_pids.update(ids)
            return ids

    def start(self, argv: list[str], *, cwd: Path, env: dict[str, str], **pipes) -> subprocess.Popen:
        self.check()
        process = subprocess.Popen(argv, cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW, **pipes)
        with self.mutex:
            if not self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
                process.kill()
                process.wait(timeout=5)
                self._error('AssignProcessToJobObject')
            self.processes.append(process)
            self.seen_pids.add(process.pid)
            # A watchdog may have fired between Popen and assignment.
            if self.reason:
                self.api.TerminateJobObject(self.handle, 1)
        self.check()
        return process

    def _watch(self):
        while not self.done.wait(0.1):
            try:
                with self.mutex:
                    self.pids()
                    if self.cancel_file is not None and self.cancel_file.exists():
                        self.reason = 'CANCELLED'
                    elif time.monotonic() >= self.deadline:
                        self.reason = 'HTML_TIMEOUT'
                    if self.reason:
                        self.api.TerminateJobObject(self.handle, 1)
                        return
            except Exception:
                with self.mutex:
                    self.reason = 'HTML_JOB_MONITOR_FAILED'
                    self.api.TerminateJobObject(self.handle, 1)
                return

    def check(self):
        if self.cancel_file is not None and self.cancel_file.exists():
            self.reason = 'CANCELLED'
        if self.reason:
            raise AppError(self.reason, 'HTML 动效已取消或超过本地运行期限', exit_code=8 if self.reason == 'CANCELLED' else 6)

    def close(self) -> dict:
        if self.closed:
            return self.receipt
        self.done.set()
        self.monitor.join(timeout=2)
        with self.mutex:
            before = self.pids()
            self.api.TerminateJobObject(self.handle, 1)
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except OSError:
                        pass  # a killed child may have closed its pipe first
        end = time.monotonic() + 5
        active = self.pids()
        while active and time.monotonic() < end:
            time.sleep(0.05)
            active = self.pids()
        self.receipt = {'native_job': True, 'seen_pids': sorted(self.seen_pids),
                        'active_before_final_cleanup': before, 'active_after_cleanup': active,
                        'all_children_reaped': not active, 'termination_reason': self.reason}
        self.api.CloseHandle(self.handle)
        self.handle = None
        self.closed = True
        if active:
            raise AppError('HTML_CLEANUP_FAILED', '浏览器 Job 清理后仍有子进程', exit_code=6)
        return self.receipt
