"""Verified bundled native HSL backend; never builds or downloads at runtime."""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import platform
import re
from .errors import AppError
from .hsl_program import compile_program
from .media import ffmpeg_path
from .text_highlight import file_fingerprint
from .utils import run_process, sha256_file


@lru_cache(maxsize=8)
def _runtime_supported(executable,fingerprint):
    result=run_process([executable,'-hide_banner','-h','filter=frei0r'],timeout=30)
    return result.returncode==0 and 'frei0r AVOptions:' in result.stdout+result.stderr


def compile_native(effect,expression,reference_kernel,metadata):
    from .selective_hsl import SPECS,MAX_KERNEL_BYTES
    selection=os.environ.get('AI_AD_EDITOR_HSL_BACKEND','auto')
    if selection not in ('auto','native','expression'):
        raise AppError('SELECTIVE_HSL_BACKEND_INVALID','HSL 后端只允许 auto/native/expression',exit_code=2)
    metadata={**metadata,'backend':'ffmpeg:geq','backend_selection':selection}
    if metadata['bypass'] or selection=='expression':return reference_kernel,metadata
    resource=Path(__file__).with_name('native_hsl_manifest.json')
    if not resource.exists() or platform.system()!='Windows' or platform.machine().lower() not in ('amd64','x86_64'):
        if selection=='native':raise AppError('SELECTIVE_HSL_NATIVE_UNAVAILABLE','缺少适用的本地原生 HSL 模块',exit_code=6)
        return reference_kernel,{**metadata,'fallback_reason':'native-module-not-installed-for-platform'}
    try:
        def require(value):
            if not value:raise ValueError('native module manifest integrity')
        manifest=json.loads(resource.read_bytes());name=manifest['binary_filename']
        require(manifest['format']=='avk-selective-hsl-native-v1' and manifest['platform']=='win32-amd64')
        require(manifest['program_format']=='AVKHSL01' and re.fullmatch(r'avk_hsl_[0-9a-f]{16}\.dll',name))
        binary=resource.with_name(name)
        require('sha256:'+sha256_file(binary)==manifest['binary_sha256'])
        require(name=='avk_hsl_'+manifest['binary_sha256'][7:23]+'.dll')
        require('sha256:'+sha256_file(resource.with_name('native_hsl.c'))==manifest['source_sha256'])
        require(manifest['license']=='NATIVE_HSL_LICENSE.txt' and resource.with_name(manifest['license']).is_file())
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise AppError('SELECTIVE_HSL_NATIVE_INTEGRITY','本地原生 HSL 模块或来源摘要不匹配',exit_code=6) from exc
    executable=Path(ffmpeg_path()).resolve();fingerprint=file_fingerprint(executable)
    if not _runtime_supported(str(executable),fingerprint):
        if selection=='native':raise AppError('SELECTIVE_HSL_NATIVE_UNAVAILABLE','本地 FFmpeg 未启用 frei0r',exit_code=6)
        return reference_kernel,{**metadata,'fallback_reason':'local-ffmpeg-without-frei0r'}
    expressions=[]
    tracks=set(metadata['animated_parameters'])
    for name,spec in SPECS.items():
        value=metadata['parameters'][name]
        raw=expression((name,),value) if name in tracks else f'{value:.8f}'
        expressions.append(f'clip({raw},{spec[2]:g},{spec[3]:g})')
    program,details=compile_program(expressions)
    kernel="format=rgba,frei0r=filter_name="+binary.stem+":filter_params='"+program.hex()+"'"
    if len(kernel.encode('utf8'))>MAX_KERNEL_BYTES:
        raise AppError('SELECTIVE_HSL_BUDGET','分色 HSL 原生内核超过 64 KiB',exit_code=2)
    # This affects only the current process and its children. The hash-named
    # filter is searched in exactly this verified package directory.
    os.environ['FREI0R_PATH']=str(resource.parent)
    metadata.update(backend='ffmpeg:frei0r',plugin_filename=binary.name,
        plugin_sha256=manifest['binary_sha256'],plugin_source_sha256=manifest['source_sha256'],
        program=details,program_sha256='sha256:'+hashlib.sha256(program).hexdigest(),
        ffmpeg_sha256='sha256:'+fingerprint,reference_kernel_sha256=metadata['kernel_sha256'],
        kernel_bytes=len(kernel.encode('utf8')),kernel_sha256='sha256:'+hashlib.sha256(kernel.encode('utf8')).hexdigest())
    return kernel,metadata
