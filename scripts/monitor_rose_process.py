"""Read Windows memory/I/O counters for one verified research process; never modify it."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import time


class Memory(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
        'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
        'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


class IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
        'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


def run(pid, executable, work):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO)]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    path = ctypes.create_unicode_buffer(32768)
    length = wintypes.DWORD(len(path))
    rows = []
    output = work/'windows-process-samples.jsonl'
    if output.exists():
        raise ValueError('fresh counter output required')
    (work/'executed-process-monitor.py').write_bytes(Path(__file__).read_bytes())
    try:
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(path.value).resolve() != executable.resolve():
            raise ValueError('research executable identity mismatch')
        while kernel.WaitForSingleObject(handle, 0) == 258:
            memory, io = Memory(), IO()
            memory.cb = ctypes.sizeof(memory)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), ctypes.sizeof(memory)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.GetProcessIoCounters(handle, ctypes.byref(io)):
                raise ctypes.WinError(ctypes.get_last_error())
            response_path = work/'worker-response.json'
            response = json.loads(response_path.read_bytes()) if response_path.is_file() else {}
            row = {'utc': datetime.now(timezone.utc).isoformat(), 'pid': pid,
                'working_set_bytes': memory.WorkingSetSize, 'os_peak_working_set_bytes': memory.PeakWorkingSetSize,
                'private_bytes': memory.PrivateUsage, 'os_peak_pagefile_bytes': memory.PeakPagefileUsage,
                'read_transfer_bytes': io.ReadTransferCount, 'write_transfer_bytes': io.WriteTransferCount,
                'phase': response.get('phases', [{}])[-1].get('phase'), 'model_calls': response.get('model_calls')}
            with output.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(row)+'\n')
            rows.append(row)
            print(json.dumps(row), flush=True)
            time.sleep(30)
    finally:
        kernel.CloseHandle(handle)
        (work/'windows-process-monitor.json').write_text(json.dumps({'status': 'monitor_ended', 'pid': pid,
            'read_only': True, 'samples': len(rows), 'sample_interval_seconds': 30,
            'last_observed_os_peak_working_set_bytes': max((r['os_peak_working_set_bytes'] for r in rows), default=0),
            'sampled_peak_private_bytes': max((r['private_bytes'] for r in rows), default=0),
            'sampling_may_miss_final_process_counters': True}, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    run(args.pid, args.executable, args.work.resolve())
