"""Native, bounded multi-frame inspection with actual presentation anchors.

The alpha-aware decoder and resize-before-sheet organization follow OpenFilm
71922644da5d6b67db2cc796d4e057f98999944f, src/look.mjs:lookMedia (MIT;
see OPENFILM_LICENSE.txt). Composition, anchors and publication are local
Python/FFmpeg implementations. No browser, media download or model is used.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction
from typing import Any

from .artifact_locks import artifact_entry, verification_scope
from .browser_process import BrowserProcessJob
from .errors import AppError
from .media import MAX_INPUT_BYTES, ffmpeg_path, ffprobe_path
from .policy import require_local_reference
from .utils import atomic_write_json, run_process, sha256_file

ENGINE = 'agent-native-contact-sheet-v1'
MAX_FRAMES = 32
MAX_CANVAS_PIXELS = 16_000_000
MAX_CANVAS_SIDE = 8192
LABEL_HEIGHT = 42
VIEWS = ('checker', 'light', 'dark', 'alpha')
FORMATS = {'mov,mp4,m4a,3gp,3g2,mj2', 'matroska,webm', 'nut', 'avi', 'mpegts',
           'mpeg', 'mxf', 'flv', 'ogg', 'png_pipe', 'jpeg_pipe', 'webp_pipe',
           'bmp_pipe', 'tiff_pipe', 'gif', 'apng'}


def fail(code, message, *, exit_code=2, **details):
    return AppError(code, message, exit_code=exit_code, **details)


def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise fail('CONTACT_ARGUMENT_INVALID', label + ' 必须是有限数值', path=label)
    return float(value)


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise fail('CONTACT_ARGUMENT_INVALID', f'{label} 必须为 {low}..{high} 整数', path=label)
    return value


def plan_contact_sheet(source: Path, *, times=None, count=8, start=0.0, end=None,
                       width=320, height=180, columns=2, views=None, cancel_file=None):
    require_local_reference(str(source), field='input')
    source = source.expanduser().resolve()
    if not source.is_file() or not 0 < source.stat().st_size <= MAX_INPUT_BYTES:
        raise fail('CONTACT_SOURCE_INVALID', '需要有界的本地媒体文件', path=str(source), exit_code=3)
    count = _integer(count, 1, MAX_FRAMES, 'count')
    width = _integer(width, 32, 640, 'width'); height = _integer(height, 32, 640, 'height')
    columns = _integer(columns, 1, 8, 'columns')
    views = list(VIEWS if views is None else views)
    if not views or len(set(views)) != len(views) or any(v not in VIEWS for v in views):
        raise fail('CONTACT_ARGUMENT_INVALID', 'views 必须为互不重复的 checker/light/dark/alpha')
    start = number(start, 'start'); end = None if end is None else number(end, 'end')
    if start < 0 or end is not None and end <= start:
        raise fail('CONTACT_ARGUMENT_INVALID', '需要 0 <= start < end')
    before = sha256_file(source)
    command = [ffprobe_path(), '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-select_streams', 'v:0', '-show_entries',
        'format=duration,format_name,start_time:stream=index,codec_name,codec_type,width,height,pix_fmt,time_base,start_time,duration,avg_frame_rate,r_frame_rate,sample_aspect_ratio,color_transfer,color_primaries,color_space:stream_tags=alpha_mode:stream_side_data=rotation',
        '-of', 'json', str(source)]
    probe = run_process(command, timeout=60, cancel_file=cancel_file)
    if probe.returncode or len(probe.stdout.encode('utf8')) > 1024 * 1024:
        raise fail('CONTACT_PROBE_FAILED', '无法读取本地单文件视频信息', exit_code=6, cause=probe.stderr[-2000:])
    try:
        raw = json.loads(probe.stdout)
        stream = raw.get('streams', [])[0]
    except (ValueError, IndexError, TypeError) as exc:
        raise fail('CONTACT_VIDEO_MISSING', '输入必须包含可解码视频或图片', exit_code=4) from exc
    if raw.get('format', {}).get('format_name') not in FORMATS:
        raise fail('CONTACT_CONTAINER_UNSUPPORTED', '联系表仅接受明确的单文件容器', exit_code=4)
    if max(int(stream.get('width', 0)), int(stream.get('height', 0))) > 8192:
        raise fail('CONTACT_DIMENSION_LIMIT', '源尺寸超过 8192 像素', exit_code=4)
    origin = float(stream.get('start_time') or raw.get('format', {}).get('start_time') or 0)
    container_start = float(raw.get('format', {}).get('start_time') or 0)
    duration = float(stream.get('duration') or raw.get('format', {}).get('duration') or 0)
    duration_basis = 'stream.duration' if stream.get('duration') else 'format.duration'
    if not stream.get('duration') and raw['format']['format_name'] == 'matroska,webm':
        duration = max(0, duration - origin)
        duration_basis = 'matroska_segment_end_minus_video_start'
    if not math.isfinite(duration) or duration < 0 or duration > 7200 or not math.isfinite(origin):
        raise fail('CONTACT_DURATION_LIMIT', '源时长必须为 0..7200 秒', exit_code=4)
    if times is not None:
        if start != 0 or end is not None:
            raise fail('CONTACT_ARGUMENT_INVALID', '显式锚点不能和 start/end 同时指定')
        times = [number(t, 'at_seconds') for t in times]
        if not 1 <= len(times) <= MAX_FRAMES:
            raise fail('CONTACT_ARGUMENT_INVALID', '显式锚点数量为 1..32')
    elif duration:
        stop = duration if end is None else end
        if stop > duration or start >= stop:
            raise fail('CONTACT_ARGUMENT_INVALID', '采样范围超出视频时长')
        times = [start + (stop - start) * i / count for i in range(count)]
    elif start == 0 and end is None and raw['format']['format_name'].endswith('_pipe'):
        times = [0.0]
    else:
        raise fail('CONTACT_DURATION_UNKNOWN', '未知时长需要显式 at_seconds 锚点', exit_code=4)
    if any(t < 0 or duration and t >= duration for t in times):
        raise fail('CONTACT_ARGUMENT_INVALID', '锚点必须在视频呈现范围 [0, duration) 内')
    columns = min(columns, len(times))
    sheet_width = width * len(views) * columns
    sheet_height = (height + LABEL_HEIGHT) * math.ceil(len(times) / columns)
    if max(sheet_width, sheet_height) > MAX_CANVAS_SIDE or sheet_width * sheet_height > MAX_CANVAS_PIXELS:
        raise fail('CONTACT_CANVAS_LIMIT', '联系表超过 8192 边长或 1600 万像素上限', exit_code=4)
    tags = {str(k).lower(): str(v) for k, v in stream.get('tags', {}).items()}
    decoder = {'vp8': 'libvpx', 'vp9': 'libvpx-vp9'}.get(stream.get('codec_name')) if tags.get('alpha_mode') == '1' else None
    rotated = any(float(v.get('rotation', 0)) % 360 for v in stream.get('side_data_list', []))
    resample = (stream.get('sample_aspect_ratio') not in (None, '0:1', '1:1') or rotated or
                int(stream.get('width', 0)) > width or int(stream.get('height', 0)) > height)
    tools = [{'path': str(Path(p).resolve()), 'sha256': 'sha256:' + sha256_file(Path(p))}
             for p in (ffmpeg_path(), ffprobe_path())]
    if before != sha256_file(source):
        raise fail('CONTACT_INPUT_CHANGED', '探测期间源字节发生变化', exit_code=10)
    return {'engine': ENGINE, 'source': {'path': str(source), 'sha256': 'sha256:' + before},
        'probe': raw, 'probe_command': command, 'probe_stdout_sha256': hashlib.sha256(probe.stdout.encode('utf8')).hexdigest(),
        'tools': tools, 'times': times, 'origin_seconds': origin, 'container_start_seconds': container_start,
        'duration_seconds': duration, 'duration_basis': duration_basis, 'decoder': decoder,
        'width': width, 'height': height, 'columns': columns, 'views': views, 'resample': bool(resample),
        'sheet_width': sheet_width, 'sheet_height': sheet_height,
        'selection': 'first_decodable_frame_at_or_after_requested_source_timestamp',
        'preview': '8bit_rgba_ffmpeg_resize_sar_and_auto_rotation; not a source precision or HDR quality measurement',
        'network': 'disabled', 'browser': False, 'model_forwards': 0}


def _background(size, view):
    from PIL import Image, ImageDraw
    background = Image.new('RGBA', size, (255, 255, 255, 255) if view == 'light' else (0, 0, 0, 255))
    if view == 'checker':
        draw = ImageDraw.Draw(background)
        for y in range(0, size[1], 12):
            for x in range(0, size[0], 12):
                gray = 192 if (x // 12 + y // 12) % 2 else 96
                draw.rectangle((x, y, min(x + 11, size[0]-1), min(y + 11, size[1]-1)), fill=(gray, gray, gray, 255))
    return background


def execute_contact_sheet(plan: dict[str, Any], output: Path, *, timeout=300, cancel_file=None):
    from PIL import Image, ImageDraw, ImageFont
    timeout = number(timeout, 'timeout')
    if not .1 <= timeout <= 3600:
        raise fail('CONTACT_ARGUMENT_INVALID', 'timeout 为 0.1..3600 秒')
    output = output.expanduser().resolve()
    if output.exists():
        raise fail('CONTACT_OUTPUT_EXISTS', '联系表输出目录必须为新路径', path=str(output))
    source = Path(plan['source']['path'])
    if source.is_relative_to(output):
        raise fail('CONTACT_OUTPUT_INVALID', '源媒体不能位于新输出目录中')
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='.' + output.name + '-', dir=output.parent))
    job = None; error = None; published = False
    report = {'engine': ENGINE, 'plan': plan, 'frames': [], 'commands': [],
              'continuous_playback_reviewed': False, 'audio_listening_reviewed': False,
              'quality_accepted': False, 'network': 'disabled'}

    def verify():
        for row in [plan['source'], *plan['tools']]:
            if artifact_entry(Path(row['path']), 'contact-sheet')['sha256'] != row['sha256']:
                raise fail('CONTACT_INPUT_CHANGED', '联系表来源或工具字节发生变化', exit_code=10, path=row['path'])

    try:
        with verification_scope():
            verify(); job = BrowserProcessJob(timeout, cancel_file)
            font = ImageFont.load_default(size=12)
            sheet = Image.new('RGB', (plan['sheet_width'], plan['sheet_height']), (24, 24, 24))
            for index, requested in enumerate(plan['times']):
                job.check()
                filename = f'frame-{index:03}.png'; frame_path = scratch / filename
                stderr = scratch / f'frame-{index:03}.stderr.log'
                target = plan['origin_seconds'] + requested
                vf = ('format=gbrapf32le,premultiply=inplace=1,' +
                      f"scale=w='min({plan['width']},iw)':h='min({plan['height']},ih)':" +
                      'force_original_aspect_ratio=decrease:reset_sar=1,unpremultiply=inplace=1,format=rgba,showinfo'
                      if plan['resample'] else 'format=rgba,showinfo')
                command = [plan['tools'][0]['path'], '-hide_banner', '-nostdin', '-loglevel', 'info', '-copyts',
                    '-ss', f'{target - plan["container_start_seconds"]:.9f}', '-protocol_whitelist', 'file,pipe',
                    *(['-c:v', plan['decoder']] if plan['decoder'] else []), '-i', str(source),
                    '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', vf, '-frames:v', '1',
                    '-fps_mode', 'passthrough', '-threads', '1', '-update', '1', '-y', str(frame_path)]
                with stderr.open('wb') as err:
                    process = job.start(command, cwd=scratch, env=dict(os.environ), stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=err)
                    process.wait(); job.check()
                if stderr.stat().st_size > 256 * 1024:
                    raise fail('CONTACT_LOG_LIMIT', '单帧日志超过 256 KiB', exit_code=6)
                log = stderr.read_text(encoding='utf8', errors='replace')
                if process.returncode or not frame_path.is_file() or not 0 < frame_path.stat().st_size <= 4 * plan['width'] * plan['height'] + 65536:
                    raise fail('CONTACT_FRAME_UNAVAILABLE', '无法在指定锚点提取有界帧', exit_code=6, cause=log[-3000:])
                match = re.search(r'\bn:\s*0\s+pts:\s*(-?\d+)\s+pts_time:\s*([-+\d.eE]+)', log)
                clock = re.search(r'config in time_base:\s*(\d+)/(\d+)', log)
                if not match or not clock or int(clock[2]) == 0:
                    raise fail('CONTACT_TIMESTAMP_MISSING', '解码帧缺少实际呈现时间戳', exit_code=6)
                pts = Fraction(int(match[1]) * int(clock[1]), int(clock[2]))
                pts_time = float(pts)
                if not math.isfinite(pts_time) or pts_time + .000002 < target:
                    raise fail('CONTACT_TIMESTAMP_INVALID', '解码帧早于显式时间锚点', exit_code=6)
                with Image.open(frame_path) as image:
                    frame = image.convert('RGBA')
                if frame.width > plan['width'] or frame.height > plan['height']:
                    raise fail('CONTACT_FRAME_LIMIT', '解码帧超过联系表单元格', exit_code=6)
                alpha = frame.getchannel('A')
                row = {'index': index, 'requested_seconds': requested, 'source_pts': int(match[1]),
                    'source_pts_time_text': match[2], 'relative_seconds': pts_time - plan['origin_seconds'],
                    'source_time_base': clock[1] + '/' + clock[2], 'source_pts_seconds_rational': str(pts),
                    'width': frame.width, 'height': frame.height, 'path': filename,
                    'png_sha256': 'sha256:' + sha256_file(frame_path),
                    'rgba_sha256': 'sha256:' + hashlib.sha256(frame.tobytes()).hexdigest(),
                    'alpha_extrema': list(alpha.getextrema()),
                    'alpha_sha256': 'sha256:' + hashlib.sha256(alpha.tobytes()).hexdigest(),
                    'log_sha256': 'sha256:' + sha256_file(stderr)}
                group_width = plan['width'] * len(plan['views'])
                x = (index % plan['columns']) * group_width
                y = (index // plan['columns']) * (plan['height'] + LABEL_HEIGHT)
                header = Image.new('RGB', (group_width, LABEL_HEIGHT), (24, 24, 24))
                header_draw = ImageDraw.Draw(header)
                header_draw.text((4, 2), f"#{index} request {requested:.6f}s | actual {row['relative_seconds']:.6f}s", font=font, fill='white')
                for n, view in enumerate(plan['views']):
                    header_draw.text((n * plan['width'] + 4, 22), view, font=font, fill=(192, 192, 192))
                sheet.paste(header, (x, y))
                panels = []
                for n, view in enumerate(plan['views']):
                    dx = x + n * plan['width']; dy = y + LABEL_HEIGHT
                    if view == 'alpha':
                        panel = Image.new('RGB', (plan['width'], plan['height']), 'black')
                        panel.paste(alpha.convert('RGB'), ((plan['width'] - frame.width)//2, (plan['height'] - frame.height)//2))
                    else:
                        background = _background((plan['width'], plan['height']), view)
                        layer = Image.new('RGBA', background.size)
                        layer.paste(frame, ((plan['width'] - frame.width)//2, (plan['height'] - frame.height)//2))
                        panel = Image.alpha_composite(background, layer).convert('RGB')
                    sheet.paste(panel, (dx, dy))
                    panels.append({'view': view, 'x': dx, 'y': dy, 'width': panel.width, 'height': panel.height,
                                   'rgb_sha256': 'sha256:' + hashlib.sha256(panel.tobytes()).hexdigest()})
                row['panels'] = panels
                report['frames'].append(row)
                report['commands'].append({'argv': command, 'exit_code': process.returncode, 'stderr': stderr.name})
                verify()
            job.check(); sheet.save(scratch / 'contact.png', format='PNG')
            verify(); job.check()
            report['contact'] = {'path': 'contact.png', 'width': sheet.width, 'height': sheet.height,
                                 'sha256': 'sha256:' + sha256_file(scratch / 'contact.png')}
            cleanup = job.close(); job = None
            if not cleanup['all_children_reaped']:
                raise fail('CONTACT_CLEANUP_FAILED', '联系表子进程未完全回收', exit_code=6)
            report['process_cleanup'] = cleanup
            atomic_write_json(scratch / 'manifest.json', report)
            if cancel_file is not None and cancel_file.exists():
                raise fail('CANCELLED', '联系表发布前已取消', exit_code=8)
            if output.exists():
                raise fail('CONTACT_OUTPUT_EXISTS', '联系表目标在执行中被创建')
            scratch.rename(output); published = True
            return report
    except AppError as exc:
        error = exc
        if exc.code.startswith('HTML_'):
            error = fail('CONTACT_TIMEOUT' if exc.code == 'HTML_TIMEOUT' else 'CONTACT_PROCESS_FAILED',
                         '联系表达到期限或原生进程约束失败', exit_code=6, cause=exc.code)
        raise error from exc
    except (OSError, ValueError) as exc:
        error = fail('CONTACT_WRITE_FAILED', '联系表文件写入或解码失败', exit_code=6, cause=str(exc))
        raise error from exc
    finally:
        try:
            if job is not None:
                cleanup = job.close()
                if error is not None:
                    error.diagnostics = {'engine': ENGINE, 'process_cleanup': cleanup}
        finally:
            if not published:
                shutil.rmtree(scratch)
