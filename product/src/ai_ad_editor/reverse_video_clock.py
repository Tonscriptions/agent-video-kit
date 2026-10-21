"""Experimental source-interval clock for native video reverse, without VFR resampling."""
from array import array
from bisect import bisect_left, bisect_right
from fractions import Fraction
import hashlib
from pathlib import Path
import subprocess
import threading
import time

from .errors import AppError
from .media import ffprobe_path

PROTOCOL = 'reverse-native-video-intervals-v1'
MAX_FRAMES = 1_000_000
MAX_EXPRESSION_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 4096
MAX_SELECTED_BUFFER_BYTES = 256 * 1024 * 1024
DECODED_BYTES_PER_PIXEL_BOUND = 16


def reserve_buffer(compiler, metadata, clip_id):
    """Charge every selected reverse buffer in this graph, including children.

    Sixteen bytes/pixel bounds supported four-channel float decoded rasters.
    This excludes decoder/encoder queues, alignment, expressions and process RSS.
    Time-disjoint clips are charged together because filter scheduling may buffer
    them together. Large clips require a future chunked/cache implementation.
    """
    estimated = metadata['estimated_decoded_frame_buffer_bytes']
    before = getattr(compiler, '_reverse_video_buffer_bytes', 0)
    total = before + estimated
    if total > MAX_SELECTED_BUFFER_BYTES:
        raise AppError('REVERSE_VIDEO_BUFFER_BUDGET_EXCEEDED',
            '原生倒放帧缓冲超过共享配额；请缩短选区', exit_code=2,
            path=f'clips[{clip_id}].reverse', diagnostics={
                'estimated_selected_decoded_bytes': estimated,
                'estimated_shared_decoded_bytes': total,
                'budget_bytes': MAX_SELECTED_BUFFER_BYTES,
                'scope': 'selected-native-reverse-frame-rasters-not-process-rss',
                'time_disjoint_instances_charged': True})
    compiler._reverse_video_buffer_bytes = total
    metadata.update(shared_buffer_bytes_after=total,
        shared_buffer_budget_bytes=MAX_SELECTED_BUFFER_BYTES,
        buffer_budget_scope='selected-native-reverse-frame-rasters-not-process-rss',
        time_disjoint_instances_charged=True)


def probe_frames(path: Path, *, timeout=300, cancel_file=None, decoder=None):
    """Read bounded compact records into int64 arrays, rather than a JSON frame tree."""
    if cancel_file is not None and cancel_file.exists():
        raise AppError('CANCELLED', '原生帧时钟探测已取消', exit_code=8)
    fields = ('frame=best_effort_timestamp,duration,width,height,pix_fmt:frame_side_data=:'
              'stream=time_base,width,height,pix_fmt,sample_aspect_ratio,color_range,color_space,color_transfer,color_primaries,chroma_location:stream_disposition=:stream_tags=rotate:stream_side_data=rotation,displaymatrix:'
              'format=start_time:format_tags=')
    command = [ffprobe_path(), '-v', 'error', '-protocol_whitelist', 'file,pipe',
               '-select_streams', 'v:0', '-show_frames', '-show_streams', '-show_format',
               '-show_entries', fields, '-of', 'compact=p=1:nk=0',
               *(['-c:v', decoder] if decoder else []), str(path)]
    pts, durations = array('q'), array('q')
    result = {'stream': None, 'format': None, 'error': None, 'decoded_format': None,'orientation':{}}
    stderr = bytearray()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def consume():
        try:
            while True:
                raw = process.stdout.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    break
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError('native frame record exceeds bounded line size')
                parts = raw.decode('utf8', 'strict').strip().split('|')
                row = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
                # FFmpeg 8 compact output prefixes these inline stream fields
                # with side_datum/display_matrix:. Older builds omit it.
                row.update({key.rsplit(':',1)[-1]:value for key,value in list(row.items())
                    if key.rsplit(':',1)[-1] in {'rotation','displaymatrix'}})
                if parts[0] == 'frame':
                    signature = (int(row['width']), int(row['height']), row['pix_fmt'])
                    if result['decoded_format'] is None:
                        result['decoded_format'] = signature
                    elif signature != result['decoded_format']:
                        raise ValueError('variable decoded raster or pixel format is not accepted')
                    point = int(row['best_effort_timestamp'])
                    raw_duration = row.get('duration', '0')
                    duration = 0 if raw_duration == 'N/A' else int(raw_duration)
                    if pts and point <= pts[-1]:
                        raise ValueError('native video PTS must be strictly increasing')
                    if duration < 0 or len(pts) >= MAX_FRAMES:
                        raise ValueError('native video duration or frame-count limit exceeded')
                    pts.append(point); durations.append(duration)
                elif parts[0] == 'stream':
                    if result['stream'] is not None:
                        raise ValueError('expected only the selected native video stream')
                    result['stream'] = row
                elif parts[0] == 'format':
                    result['format'] = row
                elif parts[0] == 'side_data':
                    result['orientation'].update(row)
        except BaseException as error:
            result['error'] = error

    def consume_stderr():
        while True:
            chunk = process.stderr.read(4096)
            if not chunk:
                return
            stderr.extend(chunk)
            if len(stderr) > 65536:
                del stderr[:-65536]

    reader = threading.Thread(target=consume, daemon=True, name='reverse-native-frame-index')
    err_reader = threading.Thread(target=consume_stderr, daemon=True, name='reverse-native-probe-stderr')
    reader.start(); err_reader.start(); started = time.monotonic()
    try:
        while reader.is_alive():
            if cancel_file is not None and cancel_file.exists():
                raise AppError('CANCELLED', '原生帧时钟探测已取消', exit_code=8)
            if time.monotonic()-started > timeout:
                raise AppError('PROCESS_TIMEOUT', '原生帧时钟探测超时', exit_code=6, retryable=True)
            reader.join(timeout=.1)
        if result['error'] is not None:
            raise result['error']
        code = process.wait(timeout=5)
        err_reader.join(timeout=5)
        if code:
            raise ValueError('ffprobe failed: ' + stderr.decode('utf8', 'replace')[-2000:])
        if not pts or result['stream'] is None or result['format'] is None:
            raise ValueError('native frame index, stream or format is missing')
        result['stream'].update(result['orientation'])
        if result['decoded_format']:
            result['stream']['pix_fmt']=result['decoded_format'][2]
        return pts, durations, result['stream'], result['format']
    except AppError:
        raise
    except (ValueError, KeyError, OverflowError, subprocess.TimeoutExpired) as error:
        raise AppError('REVERSE_VIDEO_CLOCK_INVALID', '无法建立原生倒放帧区间时钟', exit_code=3,
                       path=str(path), cause=str(error)) from error
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
        reader.join(timeout=5); err_reader.join(timeout=5)
        process.stdout.close(); process.stderr.close()


def _nearest(value):
    """AV_ROUND_NEAR_INF: nearest, with ties away from zero."""
    sign = -1 if value < 0 else 1
    value = abs(value)
    return sign * ((2*value.numerator + value.denominator) // (2*value.denominator))


def _lookup(values, first=0, end=None):
    end = len(values) if end is None else end
    if end-first == 1:
        return str(values[first])
    middle = (first+end)//2
    return f'if(lt(N,{middle}),{_lookup(values,first,middle)},{_lookup(values,middle,end)})'


def reverse_intervals(path, source_in_tick, source_out_tick, tps, working_time_base,
                      *, expected_time_base, cancel_file=None, decoder=None,
                      index_context=None, source_sha256=None):
    index_metadata=None
    if index_context is None:
        pts, durations, stream, format_info = probe_frames(path, cancel_file=cancel_file, decoder=decoder)
    else:
        pts,durations,stream,format_info,index_metadata=index_context.acquire(
            path,source_sha256,probe_frames,decoder=decoder)
    try:
        native = Fraction(stream['time_base'])
        if native != Fraction(expected_time_base):
            raise ValueError('registered and native video time bases differ')
        origin_text = format_info.get('start_time', '0')
        if origin_text == 'N/A':
            origin_text = '0'
        # Native ffmpeg input timestamps subtract the demux origin rescaled to
        # the selected stream's integer time base; do not reset at video PTS[0].
        origin = _nearest(Fraction(origin_text)/native)
        first_time = Fraction(source_in_tick, tps)
        final_time = Fraction(source_out_tick, tps)
        if first_time < 0 or final_time <= first_time:
            raise ValueError('invalid requested source interval')
        first = max(0, bisect_right(pts, first_time/native+origin)-1)
        end = bisect_left(pts, final_time/native+origin)
        if end <= first:
            raise ValueError('requested source window contains no displayed frame')
        width, height = int(stream['width']), int(stream['height'])
        if min(width, height) < 1:
            raise ValueError('invalid native decoded raster dimensions')
        grid = Fraction(working_time_base)
        values = []
        for index in range(end-1, first-1, -1):
            if index+1 < len(pts):
                frame_end = (pts[index+1]-origin)*native
            else:
                if durations[index] <= 0:
                    raise ValueError('final decoded frame has no known native duration')
                frame_end = (pts[index]+durations[index]-origin)*native
            frame_start = (pts[index]-origin)*native
            if min(frame_end, final_time) <= max(frame_start, first_time):
                raise ValueError('native source frame has no positive requested interval')
            value = (final_time-min(frame_end, final_time))/grid
            if value.denominator != 1:
                raise ValueError('reverse interval is not representable on working clock')
            values.append(int(value))
        eof = (final_time-max(first_time, (pts[first]-origin)*native))/grid
        if eof.denominator != 1 or eof <= values[-1]:
            raise ValueError('reverse EOF does not follow the final displayed frame')
        expression = f'if(gte(N,{len(values)}),{int(eof)},{_lookup(values)})'
        if len(expression.encode('ascii')) > MAX_EXPRESSION_BYTES:
            raise ValueError('reverse frame expression exceeds bounded size')
        index_digest = hashlib.sha256()
        index_digest.update(memoryview(pts)); index_digest.update(memoryview(durations))
        index_hash = index_digest.hexdigest()
        chunk_frames = MAX_SELECTED_BUFFER_BYTES // (width*height*DECODED_BYTES_PER_PIXEL_BOUND)
        chunks = []
        if chunk_frames:
            right = end
            while right > first:
                left = max(first, right-chunk_frames)
                last_pts = pts[right] if right < len(pts) else pts[-1]+durations[-1]
                relative = (pts[left]-origin)*native
                # Seek to a timestamp below the selected frame and trim by
                # absolute native PTS with copyts; retain keyframe preroll.
                microseconds = max(0, relative.numerator*1_000_000//relative.denominator-1)
                chunks.append({'source_start_frame':left,'source_end_frame_exclusive':right,
                    'native_start_pts':pts[left],'native_end_pts':last_pts,
                    'seek_seconds':f'{microseconds//1_000_000}.{microseconds%1_000_000:06}',
                    'frames':right-left})
                if len(chunks) > 65536:
                    raise ValueError('reverse chunk count exceeds 65536')
                right = left
        metadata = {'protocol': PROTOCOL, 'source_frame_start': first, 'source_frame_end_exclusive': end,
            'native_frame_count': len(pts), 'selected_frame_count': len(values),
            'native_time_base': str(native), 'demux_format_start_time': origin_text,
            'demux_origin_native_pts': origin, 'working_time_base': str(grid),
            'source_in_tick': source_in_tick, 'source_out_tick': source_out_tick,
            'first_reverse_clock_tick': values[0], 'reverse_eof_clock_tick': int(eof),
            'frame_index_sha256': 'sha256:'+index_hash,
            'expression_sha256': 'sha256:'+hashlib.sha256(expression.encode('ascii')).hexdigest(),
            'expression_bytes': len(expression), 'lookup_depth_bound': len(values).bit_length()+1,
            'input_VFR_normalized': False, 'frame_limit': MAX_FRAMES,
            'frame_buffer_strategy': 'native-FFmpeg-entire-selected-clip',
            'estimated_rgba8_selected_frame_bytes': (end-first)*width*height*4,
            'estimated_decoded_frame_buffer_bytes': (end-first)*width*height*DECODED_BYTES_PER_PIXEL_BOUND,
            'decoded_bytes_per_pixel_bound': DECODED_BYTES_PER_PIXEL_BOUND,
            'native_video_format':{k:stream[k] for k in ('width','height','pix_fmt','sample_aspect_ratio',
                'color_range','color_space','color_transfer','color_primaries','chroma_location',
                'rotation','displaymatrix','tag:rotate') if k in stream},
            'source_decoder':decoder,
            'reverse_chunk_ranges':chunks,
            'long_clip_memory_and_latency_accepted': False}
        if index_metadata is not None:metadata['native_frame_index']=index_metadata
        return first, end, expression, metadata
    except (ValueError, KeyError, ZeroDivisionError, OverflowError) as error:
        raise AppError('REVERSE_VIDEO_CLOCK_INVALID', '无法建立原生倒放帧区间时钟', exit_code=3,
                       path=str(path), cause=str(error)) from error
