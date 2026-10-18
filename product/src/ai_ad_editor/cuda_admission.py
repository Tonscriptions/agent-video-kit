"""Read-only, UUID-bound physical and Torch CUDA free-memory admission.

Checks are deliberately not reservations. Other applications may allocate after
a snapshot, and the fixed headroom does not estimate arbitrary activations.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import re
import shutil
import subprocess
import time

POLICY = 'cuda-uuid-physical-and-torch-free-v1'
HEADROOM_BYTES = 768 * 1024**2
UUID_PATTERN = re.compile(r'(?:GPU-)?([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})', re.IGNORECASE)


class CudaAdmissionError(ValueError):
    def __init__(self, code, report):
        self.report = {**report, 'status': 'rejected', 'error_code': code}
        super().__init__(code)


def _uuid(value):
    match = UUID_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError('complete physical GPU UUID required; MIG is unsupported')
    return 'GPU-'+match[1].lower()


def _integer(value, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError('CUDA byte counts must be integers')
    return value


def _validate_idle_cache(value):
    if (not isinstance(value, dict) or value.get('scope') != 'current-worker'
            or value.get('synchronized') is not True or value.get('empty_cache_called') is not True
            or value.get('completed') is not True or value.get('active_allocation_preserved') is not True):
        raise ValueError('CUDA idle-cache release evidence missing')
    counts = {name: _integer(value.get(name)) for name in (
        'allocated_before_bytes', 'reserved_before_bytes', 'allocated_after_bytes',
        'reserved_after_bytes', 'released_reserved_bytes')}
    if (counts['allocated_before_bytes'] != counts['allocated_after_bytes']
            or counts['allocated_before_bytes'] > counts['reserved_before_bytes']
            or counts['allocated_after_bytes'] > counts['reserved_after_bytes']
            or counts['reserved_after_bytes'] > counts['reserved_before_bytes']
            or counts['released_reserved_bytes'] != counts['reserved_before_bytes']-counts['reserved_after_bytes']):
        raise ValueError('CUDA idle-cache accounting changed active allocations or is inconsistent')


def _release_idle_cache(torch, report):
    value = {'scope': 'current-worker', 'synchronized': False, 'empty_cache_called': False,
             'completed': False, 'active_allocation_preserved': False}
    report['idle_cache_release'] = value
    torch.cuda.synchronize(0)
    value['synchronized'] = True
    allocated = _integer(torch.cuda.memory_allocated(0))
    reserved = _integer(torch.cuda.memory_reserved(0))
    value.update(allocated_before_bytes=allocated, reserved_before_bytes=reserved)
    if allocated > reserved:
        raise ValueError('CUDA allocated bytes exceed reserved bytes')
    value['empty_cache_called'] = True
    torch.cuda.empty_cache()
    value.update(allocated_after_bytes=_integer(torch.cuda.memory_allocated(0)),
                 reserved_after_bytes=_integer(torch.cuda.memory_reserved(0)))
    value.update(released_reserved_bytes=reserved-value['reserved_after_bytes'],
                 active_allocation_preserved=allocated == value['allocated_after_bytes'], completed=True)
    _validate_idle_cache(value)


def admit_cuda(torch, required_bytes, stage, *, expected_uuid=None):
    """Sample the actual logical CUDA 0 UUID; fail closed on missing evidence."""
    _integer(required_bytes, positive=True)
    if not isinstance(stage, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', stage):
        raise ValueError('CUDA admission stage is invalid')
    report = {'policy': POLICY, 'stage': stage, 'required_free_bytes': required_bytes,
              'reservation': False, 'oom_guarantee': False,
              'query_started_at_utc': datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    try:
        if torch.cuda.current_device() != 0:
            raise CudaAdmissionError('CUDA_ADMISSION_LOGICAL_DEVICE_MUST_BE_ZERO', report)
        device_uuid = _uuid(str(getattr(torch.cuda.get_device_properties(0), 'uuid', None)))
        report.update(device_uuid=device_uuid, logical_device_index=0)
        if expected_uuid is not None and device_uuid != _uuid(expected_uuid):
            raise CudaAdmissionError('CUDA_ADMISSION_DEVICE_IDENTITY_CHANGED', report)
        executable = shutil.which('nvidia-smi')
        if not executable:
            raise CudaAdmissionError('CUDA_ADMISSION_PHYSICAL_QUERY_UNAVAILABLE', report)
        # This frees this process's unused allocator blocks; live tensors stay resident.
        _release_idle_cache(torch, report)
        command = [executable, '--id='+device_uuid, '--query-gpu=uuid,memory.total,memory.free',
                   '--format=csv,noheader,nounits']
        report['query_command'] = command
        result = subprocess.run(command, capture_output=True, timeout=5, check=False)
        if result.returncode:
            raise CudaAdmissionError('CUDA_ADMISSION_PHYSICAL_QUERY_FAILED', report)
        if len(result.stdout) > 4096:
            raise ValueError('physical CUDA query response exceeds budget')
        rows = list(csv.reader(result.stdout.decode('ascii').strip().splitlines()))
        if len(rows) != 1 or len(rows[0]) != 3:
            raise ValueError('physical CUDA query must return one UUID-bound row')
        identity, total, free = (x.strip() for x in rows[0])
        if _uuid(identity) != device_uuid:
            raise ValueError('physical CUDA query returned a different UUID')
        if not total.isascii() or not free.isascii() or not total.isdecimal() or not free.isdecimal():
            raise ValueError('physical CUDA query returned noninteger MiB')
        physical_total, physical_free = int(total)*1024**2, int(free)*1024**2
        torch_free, torch_total = torch.cuda.mem_get_info(0)
        for value in (torch_total, physical_total):
            _integer(value, positive=True)
        for value in (torch_free, physical_free):
            _integer(value)
        if torch_free > torch_total or physical_free > physical_total:
            raise ValueError('CUDA free bytes exceed total bytes')
        report.update(torch_free_bytes=torch_free, torch_total_bytes=torch_total,
                      physical_free_bytes=physical_free, physical_total_bytes=physical_total,
                      effective_free_bytes=min(torch_free, physical_free),
                      query_finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      sample_seconds=time.monotonic()-started)
        if physical_free < required_bytes:
            raise CudaAdmissionError('CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE', report)
        if torch_free < required_bytes:
            raise CudaAdmissionError('CUDA_ADMISSION_INSUFFICIENT_TORCH_FREE', report)
        report['status'] = 'admitted'
        return report
    except CudaAdmissionError:
        raise
    except subprocess.TimeoutExpired as exc:
        raise CudaAdmissionError('CUDA_ADMISSION_PHYSICAL_QUERY_TIMEOUT', report) from exc
    except (ValueError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        report['cause'] = str(exc)[:512]
        raise CudaAdmissionError('CUDA_ADMISSION_DEVICE_EVIDENCE_INVALID', report) from exc


def window_summary():
    return {'count': 0, 'minimum_torch_free_bytes': None,
            'minimum_physical_free_bytes': None, 'first': None, 'last': None}


def record_window(summary, check):
    """Retain a bounded summary, rather than an unbounded response per frame."""
    number = summary['count'] + 1
    validate_check(check, stage='video-window-'+str(number), required=HEADROOM_BYTES,
                   device_uuid=summary['first']['device_uuid'] if summary['first'] else None)
    summary['count'] = number
    if number == 1:
        summary['first'] = check
    summary['last'] = check
    for field in ('torch', 'physical'):
        key = 'minimum_'+field+'_free_bytes'
        value = check[field+'_free_bytes']
        summary[key] = value if summary[key] is None else min(summary[key], value)


def validate_check(check, *, stage, required, device_uuid=None):
    if (not isinstance(check, dict) or check.get('policy') != POLICY or check.get('stage') != stage
            or check.get('status') != 'admitted' or check.get('reservation') is not False
            or check.get('oom_guarantee') is not False or check.get('logical_device_index') != 0
            or type(check.get('logical_device_index')) is not int):
        raise ValueError('CUDA admission check contract mismatch')
    identity = _uuid(check.get('device_uuid'))
    if identity != check['device_uuid'] or device_uuid is not None and identity != device_uuid:
        raise ValueError('CUDA admission identity changed')
    if _integer(check.get('required_free_bytes'), positive=True) != required:
        raise ValueError('CUDA admission budget mismatch')
    for field in ('torch', 'physical'):
        free = _integer(check.get(field+'_free_bytes'))
        total = _integer(check.get(field+'_total_bytes'), positive=True)
        if not required <= free <= total:
            raise ValueError('CUDA admission free bytes are below budget')
    if _integer(check.get('effective_free_bytes')) != min(check['torch_free_bytes'], check['physical_free_bytes']):
        raise ValueError('CUDA effective free bytes mismatch')
    _validate_idle_cache(check.get('idle_cache_release'))


def validate_execution(execution, *, text_gpu_budget_mib, model_calls):
    value = execution.get('gpu_admission')
    if (not isinstance(value, dict) or value.get('policy') != POLICY or value.get('reservation') is not False
            or value.get('oom_guarantee') is not False or value.get('headroom_bytes') != HEADROOM_BYTES):
        raise ValueError('CUDA admission execution metadata missing')
    text = value.get('text')
    validate_check(text, stage='text-weights', required=text_gpu_budget_mib*1024**2+HEADROOM_BYTES)
    weights = _integer(value.get('video_weight_bytes'), positive=True)
    embeds = _integer(value.get('prompt_embedding_bytes'), positive=True)
    validate_check(value.get('video'), stage='video-weights', required=weights+embeds+HEADROOM_BYTES,
                   device_uuid=text['device_uuid'])
    summary = value.get('windows')
    if not isinstance(summary, dict) or type(summary.get('count')) is not int or summary['count'] != model_calls or model_calls < 1:
        raise ValueError('CUDA window admission count mismatch')
    for key, stage in [('first', 'video-window-1'), ('last', 'video-window-'+str(model_calls))]:
        validate_check(summary.get(key), stage=stage, required=HEADROOM_BYTES, device_uuid=text['device_uuid'])
    for field in ('torch', 'physical'):
        minimum = _integer(summary.get('minimum_'+field+'_free_bytes'))
        if not HEADROOM_BYTES <= minimum <= min(summary[key][field+'_free_bytes'] for key in ('first', 'last')):
            raise ValueError('CUDA window admission minimum mismatch')
