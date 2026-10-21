"""Typed RGB curve coordinates compiled into bounded, whole-channel commands.

Native `all` commands erase explicit RGB curves. Only red/green/blue commands
are emitted here, each containing an entire validated point string. Author
recipes stay editable; command files are disposable content-addressed cache.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
import re

from . import effect_automation as ea
from .errors import AppError
from .media import ffmpeg_path
from .text_highlight import file_fingerprint, _quoted
from .utils import atomic_write_text, sha256_file

ENGINE = 'native-curve-points-cfr-v1'
ALIASES = {'curves', 'curve', 'rgb_curves', 'rgb_curve', 'channel_curves'}
MAX_POINTS = 256
CHANNELS = ('red', 'green', 'blue')
_POINT = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')


def matches(name):
    return str(name).strip().lower().replace('-', '_') in ALIASES


def channels(name):
    return ('all',) if str(name).lower().replace('-', '_') in {'curves', 'curve'} else ('all', *CHANNELS)


def parameter_names(name):
    names = {f'{c}.{i}.{axis}' for c in channels(name) for i in range(MAX_POINTS) for axis in ('x', 'y')}
    if channels(name) == ('all',):
        names.update(f'master.{i}.{axis}' for i in range(MAX_POINTS) for axis in ('x', 'y'))
    return names


def tracks(effect):
    result = ea.normalized_tracks(effect)
    if channels(effect.get('type')) == ('all',):
        result = [{**t, 'property': 'all.'+t['property'][7:] if t['property'].startswith('master.') else t['property']} for t in result]
    return result


def _fail(message, *, code='CURVE_AUTOMATION_POINTS_INVALID'):
    raise AppError(code, message, exit_code=2)


def _geometry(points):
    # Match native parse_points_str: compare truncated 8-bit x coordinates.
    bins = [int(float(f'{p[0]:.6f}')*255) for p in points]
    if any(left >= right for left, right in zip(bins, bins[1:])):
        _fail('曲线 x 必须严格递增，且六位小数后的坐标不能落在同一 8-bit 采样格')


def parse_points(value):
    if not isinstance(value, str):
        _fail('动态曲线静态点必须是 x/y 字符串')
    tokens = value.split()
    if not 1 <= len(tokens) <= MAX_POINTS:
        _fail('每条动态曲线需要 1..256 个固定控制点')
    result = []
    for token in tokens:
        parts = token.split('/')
        if len(parts) != 2 or any(_POINT.fullmatch(part) is None for part in parts):
            _fail('曲线只接受有限数字 x/y，不接受命令、路径或表达式')
        pair = [float(part) for part in parts]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in pair):
            _fail('曲线坐标必须位于 0..1')
        result.append(pair)
    _geometry(result)
    return result


def definition(effect):
    parameters = effect.get('parameters') if isinstance(effect.get('parameters'), dict) else effect
    raw_all = parameters.get('all', parameters.get('master', '0/0 1/1') if channels(effect.get('type')) == ('all',) else '0/0 1/1')
    base = {'all': parse_points(raw_all)}
    own = {t['property'].split('.')[0] for t in tracks(effect)}
    for channel in channels(effect.get('type'))[1:]:
        raw = parameters.get(channel)
        if raw is not None and raw != '':
            base[channel] = parse_points(raw)
        elif channel in own:
            base[channel] = [p[:] for p in base['all']]
    return base


def validate(effect, *, duration_tick=None):
    if not matches(effect.get('type')) or not tracks(effect) or effect.get('enabled', True) is False:
        return []
    try:
        base = definition(effect)
    except AppError as error:
        return [{'code': error.code, 'message': str(error), 'suffix': '.parameters'}]
    specs = {f'{channel}.{i}.{axis}': ((f'{channel}.{i}.{axis}',), point[a], 0., 1., ())
             for channel, points in base.items() for i, point in enumerate(points) for a, axis in enumerate(('x', 'y'))}
    return ea.validate_tracks(tracks(effect), specs, duration_tick=duration_tick)


def bind(compiler, effect, clip, start, end):
    findings = validate(effect)
    if findings:
        raise AppError(findings[0]['code'], findings[0]['message'], exit_code=2, cause=json.dumps(findings))
    base = definition(effect)
    authored_tracks = tracks(effect)
    first = max(0, math.ceil(start*float(compiler.rate)-1e-9))
    stop = max(first, math.ceil(end*float(compiler.rate)-1e-9))
    count = max(1, stop-first)
    cost = len(authored_tracks)+sum(2*len(p) for p in base.values())
    samples = count*cost
    if compiler.samples+samples > ea.MAX_SAMPLES or compiler.targets+compiler.hsl_instances >= ea.MAX_TARGETS:
        _fail('动态曲线超过共享根图状态采样或实例配额', code='EFFECT_AUTOMATION_BUDGET')
    executable = ffmpeg_path()
    from pathlib import Path
    executable = Path(executable).resolve()
    fingerprint = file_fingerprint(executable)
    if not set(CHANNELS) <= ea.runtime_options(str(executable), fingerprint, 'curves'):
        raise AppError('EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE', '本机 FFmpeg 缺少 RGB 整曲线运行时命令', exit_code=6)
    identity = {'protocol': ENGINE, 'effect': effect, 'clock': clip.get('_nested_keyframe_clock'),
                'start': start, 'end': end, 'fps': str(compiler.rate), 'serial': compiler.targets}
    token = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode('utf8')).hexdigest()[:16]
    target = f'avk_cp_{compiler.targets}_{token}'
    curves = {t['property']: ea.Curve(t, clip, start, compiler.tps) for t in authored_tracks}
    lines, previous, initial = [], {}, None
    command_count = size = clamps = 0
    for offset, frame in enumerate(range(first, max(first+1, stop))):
        display = float(Fraction(frame, 1)/compiler.rate)
        state = {c: [p[:] for p in points] for c, points in base.items()}
        for prop, curve in curves.items():
            value = curve.value(display)
            if not math.isfinite(value):
                _fail('曲线控制点求值产生非有限数字', code='EFFECT_AUTOMATION_VALUE_INVALID')
            bounded = max(0., min(1., value)); clamps += bounded != value
            channel, index, axis = prop.split('.')
            state[channel][int(index)][axis == 'y'] = bounded
        for channel, points in state.items():
            try:
                _geometry(points)
            except AppError as error:
                _fail(f'{channel} 在显示帧 {frame} 的控制点无效: {error}')
        values = {channel: ' '.join(f'{x:.6f}/{y:.6f}' for x, y in state.get(channel, state['all'])) for channel in CHANNELS}
        if initial is None:
            initial = values
        changed = {c: v for c, v in values.items() if previous.get(c) != v}
        if changed:
            at = 0. if offset == 0 else float((Fraction(frame, 1)-Fraction(1, 2))/compiler.rate)
            line = f'{at:.12f} '+', '.join(f"curves@{target} {c} '{v}'" for c, v in changed.items())+';\n'
            command_count += len(changed); size += len(line.encode('utf8'))
            if compiler.commands+command_count > ea.MAX_COMMANDS or compiler.bytes+size > ea.MAX_BYTES:
                _fail('动态曲线超过共享根图命令或文本配额', code='EFFECT_AUTOMATION_BUDGET')
            lines.append(line)
        previous = values
    text = ''.join(lines)
    digest = hashlib.sha256(text.encode('utf8')).hexdigest()
    relative = f'cache/effect-automation/{digest}.ffcmd'
    path = compiler.root/relative
    if path.exists():
        if sha256_file(path) != digest:
            raise AppError('EFFECT_AUTOMATION_CACHE_HASH_MISMATCH', '动态曲线缓存摘要不匹配', exit_code=6, path=relative)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text)
    compiler.targets += 1; compiler.samples += samples; compiler.commands += command_count; compiler.bytes += size
    metadata = {'kind': 'curve-point-automation', 'protocol': ENGINE, 'backend': 'curves', 'target': target,
                'clip_id': clip.get('id'), 'effect': effect.get('type'), 'parameters': sorted(curves),
                'ffmpeg_sha256': 'sha256:'+fingerprint, 'fps': str(compiler.rate), 'ticks_per_second': compiler.tps,
                'sampled_frames': stop-first, 'state_samples': samples, 'frame_start': first, 'frame_stop_exclusive': stop,
                'point_counts': {c: len(p) for c, p in base.items()}, 'independent_channels': sorted(set(base)-{'all'}),
                'commands_between_samples': True, 'initial_state_explicit': True,
                'command_count': command_count, 'command_file': relative, 'command_file_sha256': 'sha256:'+digest,
                'command_bytes': size, 'clamped_parameter_samples': clamps,
                'author_clock': clip.get('_nested_keyframe_clock'), 'effect_start_seconds': start, 'effect_end_seconds': end,
                'native_value_serialization': 'six-decimals-8bit-x-bins', 'spatial_interpolation': 'natural-cubic',
                'native_commands': list(CHANNELS), 'all_semantics': 'fallback-not-post-master'}
    static_filter = f'curves@{target}='+':'.join(f'{c}={_quoted(v)}' for c, v in initial.items())
    return ['sendcmd=filename='+_quoted(relative), static_filter], metadata
