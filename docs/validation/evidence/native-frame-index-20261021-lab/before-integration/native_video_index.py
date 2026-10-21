"""Immutable source/runtime-pinned native frame indexes; no frame pixel cache."""
from __future__ import annotations
from array import array
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from .artifact_locks import artifact_entry,verification_scope
from .errors import AppError
from .media import ffprobe_path
from .policy import resolve_local_path
from .utils import sha256_file

PROTOCOL='native-video-frame-index-v1'
MAX_FRAMES=1_000_000
MAX_METADATA_BYTES=128*1024
DISK_HEADROOM=64*1024**2

def error(code,message,**details):return AppError(code,message,exit_code=6,diagnostics=details or None)

def cancel(marker):
    if marker is not None and marker.exists():raise AppError('CANCELLED','原生视频帧索引已取消',exit_code=8,path=str(marker))

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def owned(root,path):
    root=root.resolve();path=Path(os.path.abspath(path))
    if not path.is_relative_to(root):raise error('NATIVE_INDEX_PATH_INVALID','帧索引缓存必须位于当前工程内')
    current=root
    for part in path.relative_to(root).parts:
        current/=part
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():
            raise error('NATIVE_INDEX_PATH_INVALID','帧索引缓存不能包含符号链接或目录联接',path=str(current))
    return path

def verify(recipe,marker):
    with verification_scope():
        for expected in recipe['artifacts'].values():
            cancel(marker)
            if artifact_entry(Path(expected['path']),'native-index-boundary')['sha256']!=expected['sha256']:
                raise error('NATIVE_INDEX_INPUT_CHANGED','帧索引源或原生程序在边界之间变化',path=expected['path'])

def validate(pts,durations,stream,format_info):
    if (sys.byteorder!='little' or not isinstance(pts,array) or not isinstance(durations,array) or
        pts.typecode!='q' or durations.typecode!='q' or pts.itemsize!=8 or durations.itemsize!=8 or
        not 0<len(pts)<=MAX_FRAMES or len(pts)!=len(durations)):
        raise error('NATIVE_INDEX_INVALID','帧索引必须是有界小端 int64 时间戳与时长数组')
    if any(right<=left for left,right in zip(pts,pts[1:])) or any(value<0 for value in durations):
        raise error('NATIVE_INDEX_INVALID','帧索引时间戳必须严格递增，时长必须非负')
    try:
        if Fraction(stream['time_base'])<=0 or min(int(stream['width']),int(stream['height']))<1 or not stream['pix_fmt']:
            raise ValueError('invalid native stream format')
        origin=format_info.get('start_time','0')
        Fraction('0' if origin in (None,'','N/A') else origin)
        canonical({'stream':stream,'format':format_info})
    except (KeyError,ValueError,TypeError) as caught:
        raise AppError('NATIVE_INDEX_INVALID','帧索引原生流元数据无效',exit_code=6,cause=str(caught)) from caught

def acquire(root,source,source_sha256,probe,*,decoder=None,persist=False,cancel_file=None):
    """Read an existing index or probe; persist misses only for actual execution.

    The caller holds the project write lock when persist is true. The probe
    callable returns (int64 PTS, int64 durations, stream dict, format dict).
    """
    cancel(cancel_file);root=root.resolve();source=resolve_local_path(root,str(source),field='native-index.source')
    with verification_scope():
        artifacts={name:artifact_entry(path,'native-index-'+name) for name,path in (
            ('source',source),('ffprobe',Path(ffprobe_path()).resolve()),
            ('implementation',Path(__file__)),('probe_implementation',Path(__file__).with_name('reverse_video_clock.py')))}
    if artifacts['source']['sha256']!=source_sha256:
        raise error('NATIVE_INDEX_INPUT_CHANGED','源字节与登记摘要不符')
    recipe={'protocol':PROTOCOL,'artifacts':artifacts,'decoder':decoder,'byte_order':'little','item_type':'signed-int64'}
    key=hashlib.sha256(canonical(recipe)).hexdigest();directory=owned(root,root/'cache/native-video-index'/key)
    metadata=owned(root,directory/'index.json');files={name:owned(root,directory/(name+'.i64le')) for name in ('pts','durations')}
    if directory.exists():
        if (not metadata.is_file() or metadata.stat().st_size>MAX_METADATA_BYTES or
            {p.name for p in islice(directory.iterdir(),4)}!={'index.json','pts.i64le','durations.i64le'}):
            raise error('NATIVE_INDEX_CORRUPT','帧索引清单、文件布局缺失或超限')
        try:
            previous=json.loads(metadata.read_bytes());count=previous['frames']
            if (type(count) is not int or not 0<count<=MAX_FRAMES or previous['recipe']!=recipe):
                raise ValueError('index recipe/count mismatch')
            values={}
            for name,path in files.items():
                cancel(cancel_file)
                if path.stat().st_size!=count*8 or 'sha256:'+sha256_file(path)!=previous['files'][name]['sha256']:
                    raise ValueError('index size or byte hash mismatch')
                with path.open('rb') as stream:
                    values[name]=array('q');values[name].fromfile(stream,count)
            pts,durations=values['pts'],values['durations'];stream=previous['stream'];format_info=previous['format']
            validate(pts,durations,stream,format_info)
        except AppError as caught:
            if caught.code!='NATIVE_INDEX_INVALID':raise
            raise AppError('NATIVE_INDEX_CORRUPT','帧索引缓存未通过时间戳或元数据约束',exit_code=6,path=str(directory),cause=str(caught)) from caught
        except (ValueError,KeyError,TypeError,OSError,EOFError,MemoryError) as caught:
            raise AppError('NATIVE_INDEX_CORRUPT','原生帧索引缓存无效，保留原文件',exit_code=6,path=str(directory),cause=str(caught)) from caught
        verify(recipe,cancel_file)
        return pts,durations,stream,format_info,{'protocol':PROTOCOL,'key':key,'status':'cache-hit',
            'source_index_decode_calls':0,'path':str(directory),'frames':count,'byte_validation':True}
    pts,durations,stream,format_info=probe(source,cancel_file=cancel_file,decoder=decoder)
    validate(pts,durations,stream,format_info);verify(recipe,cancel_file)
    descriptor={'protocol':PROTOCOL,'key':key,'status':'probed-readonly','source_index_decode_calls':1,
        'path':str(directory),'frames':len(pts),'byte_validation':False}
    if not persist:return pts,durations,stream,format_info,descriptor
    record={'recipe':recipe,'frames':len(pts),'stream':stream,'format':format_info,'files':{},
        'completed_at_utc':datetime.now(timezone.utc).isoformat()}
    for name,value in (('pts',pts),('durations',durations)):
        record['files'][name]={'bytes':len(value)*8,'sha256':'sha256:'+hashlib.sha256(memoryview(value)).hexdigest()}
    payload=canonical(record)+b'\n'
    if len(payload)>MAX_METADATA_BYTES:raise error('NATIVE_INDEX_METADATA_BUDGET','帧索引元数据超过字节配额')
    if shutil.disk_usage(root).free<len(pts)*16+MAX_METADATA_BYTES+DISK_HEADROOM:
        raise error('NATIVE_INDEX_DISK_SPACE','帧索引缓存磁盘余量不足')
    scratch=owned(root,root/'renders/.tmp');scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-index-',dir=scratch) as temporary:
        staged=Path(temporary)/'ready';staged.mkdir()
        for name,value in (('pts',pts),('durations',durations)):
            cancel(cancel_file)
            with (staged/(name+'.i64le')).open('xb') as output:
                output.write(memoryview(value));output.flush();os.fsync(output.fileno())
        with (staged/'index.json').open('xb') as output:output.write(payload);output.flush();os.fsync(output.fileno())
        verify(recipe,cancel_file);cancel(cancel_file)
        owned(root,directory);directory.parent.mkdir(parents=True,exist_ok=True)
        if directory.exists():raise error('NATIVE_INDEX_CONFLICT','另一个任务已发布同一索引，保留原目录')
        os.replace(staged,directory)
    descriptor.update(status='built',byte_validation=True)
    return pts,durations,stream,format_info,descriptor
