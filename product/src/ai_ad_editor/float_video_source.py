"""Bounded native RGB video frames with their original verified frame clock.

Uses the existing content-bound native index and the native pixel decoder.
No fps filter, implicit RGB/alpha conversion, autorotation, remote input or
colour transfer is requested. YUV needs the explicit colour-managed adapter.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import queue
import subprocess
import threading
import time
import numpy as np
from .artifact_locks import artifact_entry,verification_scope
from .errors import AppError
from .float_pixels import decode_frame,frame_bytes,layout
from .media import ffmpeg_path,ffprobe_path
from .native_video_index import IndexContext
from .reverse_video_clock import probe_frames
from .utils import sha256_file

PROTOCOL='native-RGB-float32-frame-source-v1'
TIMEOUT_SECONDS=3600

def error(suffix,message,**details):
    return AppError('FLOAT_VIDEO_'+suffix,message,exit_code=6,diagnostics=details or None)

def cancelled(marker):
    if marker is not None and marker.exists():raise AppError('CANCELLED','高精度视频读取已取消',exit_code=8,path=str(marker))

def digest(path):return 'sha256:'+sha256_file(Path(path))

class _RawPipe:
    """Same bounded-queue lifecycle as the existing native audio reader."""
    def __init__(self,command,marker):
        cancelled(marker);self.marker=marker;self.deadline=time.monotonic()+TIMEOUT_SECONDS
        self.queue=queue.Queue(maxsize=4);self.stop=threading.Event();self.buffer=bytearray();self.eof=False
        self.tail=deque(maxlen=2)
        self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def output():
            try:
                while not self.stop.is_set():
                    block=self.process.stdout.read(65536)
                    while not self.stop.is_set():
                        try:self.queue.put(block,timeout=.2);break
                        except queue.Full:pass
                    if not block:break
            except BaseException as exc:
                while not self.stop.is_set():
                    try:self.queue.put(exc,timeout=.2);break
                    except queue.Full:pass
        def stderr():
            while block:=self.process.stderr.read(65536):self.tail.append(block)
        self.threads=[threading.Thread(target=output,daemon=True),threading.Thread(target=stderr,daemon=True)]
        for thread in self.threads:thread.start()

    def read(self,count):
        while len(self.buffer)<count and not self.eof:
            cancelled(self.marker)
            if time.monotonic()>self.deadline:raise error('TIMEOUT','高精度原生视频读取超时')
            try:block=self.queue.get(timeout=.2)
            except queue.Empty:continue
            if isinstance(block,BaseException):raise error('PIPE','原生视频管道读取失败',cause=repr(block))
            if block:self.buffer.extend(block)
            else:self.eof=True
        result=bytes(self.buffer[:count]);del self.buffer[:count];return result

    def finish(self):
        code=self.process.wait(timeout=10);self.threads[1].join(timeout=5)
        if code:raise error('DECODE','原生视频解码失败',exit_code=code,stderr=b''.join(self.tail).decode('utf8','replace')[-6000:])

    def close(self):
        self.stop.set()
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
        for thread in self.threads:thread.join(timeout=5)
        for stream in (self.process.stdout,self.process.stderr):
            if stream is not None:stream.close()

@dataclass(frozen=True)
class NativeFloatFrame:
    index:int
    pts:int
    duration:int
    time_base:Fraction
    rgba:np.ndarray

class NativeRGBSource:
    """Context-managed prefix decoder; native index owns original source coverage."""
    def __init__(self,root,source,source_sha256,*,alpha_association='straight',stop_frame=None,
                 cancel_file=None,index_context=None,persist_index=False):
        self.root=Path(root).resolve();self.source=Path(source).resolve(strict=True)
        if not self.source.is_file():raise error('INPUT','原生视频源须是本地文件')
        self.source_sha256=source_sha256;self.alpha_association=alpha_association;self.stop_frame=stop_frame
        self.marker=Path(cancel_file) if cancel_file is not None else None
        self.context=index_context if index_context is not None else IndexContext(self.root,persist=persist_index,cancel_file=self.marker)
        self.pipe=None;self.position=0;self.complete=False;self.closed=False
        self.metadata={'protocol':PROTOCOL,'source':str(self.source),'source_sha256':source_sha256,
            'native_frame_clock':True,'network':False,'autorotation':False,'CFR_normalization':False,
            'colour_transform':'none;native-RGB/gray-values-only','editor_integrated':False,'HDR_accepted':False}

    def _additional_artifacts(self):
        return []

    def _prepare_pixels(self,pixel_format):
        info=layout(pixel_format)
        self.bytes_per_frame=frame_bytes(pixel_format,self.width,self.height)
        return {'source_has_alpha':info.has_alpha}

    def _decode_pixels(self,raw):
        return decode_frame(raw,self.pixel_format,self.width,self.height,
            alpha_association=self.alpha_association,cancel=lambda:cancelled(self.marker))

    def __enter__(self):
        if self.closed or self.pipe is not None:raise error('STATE','高精度源不能重复打开')
        cancelled(self.marker)
        if digest(self.source)!=self.source_sha256:raise error('INPUT_CHANGED','源视频与登记SHA不相同')
        with verification_scope():
            artifacts={name:artifact_entry(Path(path).resolve(),'float-video-source') for name,path in
                [('source',self.source),('ffmpeg',ffmpeg_path()),('ffprobe',ffprobe_path()),
                 ('implementation',__file__),('pixels_implementation',Path(__file__).with_name('float_pixels.py')),
                 *self._additional_artifacts()]}
        if artifacts['source']['sha256']!=self.source_sha256:raise error('INPUT_CHANGED','索引前源视频发生改变')
        self.artifacts=artifacts
        self.pts,self.durations,self.stream,self.format_info,index=self.context.acquire(
            self.source,self.source_sha256,probe_frames)
        pixel_format=self.stream['pix_fmt']
        self.width,self.height=int(self.stream['width']),int(self.stream['height'])
        pixel_metadata=self._prepare_pixels(pixel_format)
        self.time_base=Fraction(self.stream['time_base']);self.pixel_format=pixel_format
        count=len(self.pts)
        if self.stop_frame is not None:
            if isinstance(self.stop_frame,bool) or not isinstance(self.stop_frame,int) or not 1<=self.stop_frame<=count:
                raise error('RANGE','原生解码末帧须在已核验帧索引内')
            count=self.stop_frame
        if self.alpha_association not in ('straight','premultiplied'):raise error('ALPHA','源透明度表示必须明确')
        self.count=count
        command=[ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe',
            '-noautorotate','-i',str(self.source),'-map','0:v:0','-an','-sn','-dn','-frames:v',str(count),
            '-fps_mode','passthrough','-pix_fmt',pixel_format,'-f','rawvideo','pipe:1']
        self.metadata.update(native_index=index,native_stream=self.stream,format_info=self.format_info,
            source_frame_count=len(self.pts),requested_prefix_frame_count=count,
            native_time_base=str(self.time_base),alpha_association=self.alpha_association,
            **pixel_metadata,frame_bytes=self.bytes_per_frame,
            command=command,artifacts=artifacts,bounded_stdout_chunks=4,chunk_bytes=65536,bounded_stderr_chunks=2)
        self.pipe=_RawPipe(command,self.marker);return self

    def verify(self):
        cancelled(self.marker)
        for name,row in self.artifacts.items():
            if digest(row['path'])!=row['sha256']:raise error('INPUT_CHANGED','源、工具或实现字节改变',artifact=name)

    def read(self):
        if self.pipe is None or self.closed:raise error('STATE','须在打开的上下文中读取原生表面')
        if self.complete:return None
        cancelled(self.marker)
        raw=self.pipe.read(self.bytes_per_frame)
        if len(raw)!=self.bytes_per_frame:raise error('TRUNCATED','原生解码字节未覆盖已核验帧',frame=self.position,
            expected_bytes=self.bytes_per_frame,actual_bytes=len(raw))
        value,metadata=self._decode_pixels(raw)
        index=self.position;frame=NativeFloatFrame(index,int(self.pts[index]),int(self.durations[index]),self.time_base,value)
        self.position+=1;self.metadata['decoded_frames']=self.position;self.metadata['pixel_boundary']=metadata
        if self.position==self.count:
            if self.pipe.read(1):raise error('FRAME_COUNT','原生解码返回多余帧字节')
            self.pipe.finish();self.verify();self.complete=True
            self.metadata.update(requested_prefix_complete=True,all_source_frames_decoded=self.count==len(self.pts))
        return frame

    def __iter__(self):
        while (frame:=self.read()) is not None:yield frame

    def close(self):
        if self.pipe is not None:self.pipe.close()
        self.closed=True;self.metadata.update(closed=True,requested_prefix_complete=self.complete)

    def __exit__(self,kind,value,traceback):
        try:
            if kind is None:self.verify()
        finally:self.close()
