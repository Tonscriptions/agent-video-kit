"""Bounded native filter commands sampled on the complete author clock.

Only the numeric vocabulary below can become commands. Author projects keep
ordinary effect keyframes; command files are derived, content-addressed cache.
One compiler belongs to the entire recursive graph, including author windows.
"""
from __future__ import annotations

from bisect import bisect_right
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .animation import keyframe_value
from .errors import AppError
from .media import ffmpeg_path
from .text_highlight import file_fingerprint, _quoted
from .time_mapping import compose_time
from .utils import atomic_write_text, run_process, sha256_file


# canonical property: (accepted aliases, default, lower, upper, native options)
SPECS = {
    'blur': {
        # Set both axes explicitly: sigmaV=-1 is resolved when the native
        # filter initializes and must not leave a stale vertical radius.
        'radius': (('radius', 'sigma'), 4., 0., 128., ('sigma', 'sigmaV')),
    },
    'color_contrast': {
        **{channel: ((channel, option), 0., -1., 1., (option,))
           for channel, option in (('red', 'rc'), ('green', 'gm'), ('blue', 'by'))},
        **{channel: ((channel, option), 0., 0., 1., (option,))
           for channel, option in (('red_weight', 'rcw'), ('green_weight', 'gmw'),
                                   ('blue_weight', 'byw'), ('preserve_luma', 'pl'))},
    },
    'lens_correction': {
        'k1': (('k1',), 0., -1., 1., ('k1',)),
        'k2': (('k2',), 0., -1., 1., ('k2',)),
        'cx': (('cx',), .5, 0., 1., ('cx',)),
        'cy': (('cy',), .5, 0., 1., ('cy',)),
    },
    'chroma_key': {
        'similarity': (('similarity',), .1, .00001, 1., ('similarity',)),
        'blend': (('blend',), 0., 0., 1., ('blend',)),
    },
    'color_temperature': {
        'kelvin': (('kelvin',), 6500., 1000., 40000., ('rs', 'gs', 'bs')),
    },
    'color_balance': {
        channel: ((channel, option), 0., -1., 1., (option,))
        for channel, option in zip(('red', 'green', 'blue'), ('rs', 'gs', 'bs'))
    },
    'color_wheel': {
        f'{tone}_{channel}': ((f'{tone}_{channel}',), 0., -1., 1., (option,))
        for tone, suffix in (('shadows', 's'), ('midtones', 'm'), ('highlights', 'h'))
        for channel, prefix in (('red', 'r'), ('green', 'g'), ('blue', 'b'))
        for option in (prefix+suffix,)
    },
    'exposure': {
        'amount': (('amount', 'exposure'), 0., -3., 3., ('exposure',)),
        'black': (('black',), 0., -1., 1., ('black',)),
    },
    'color_levels': {
        'input_black': (('input_black', 'rimin'), 0., -1., 1., ('rimin', 'gimin', 'bimin')),
        'input_white': (('input_white', 'rimax'), 1., -1., 1., ('rimax', 'gimax', 'bimax')),
        'output_black': (('output_black', 'romin'), 0., 0., 1., ('romin', 'gomin', 'bomin')),
        'output_white': (('output_white', 'romax'), 1., 0., 1., ('romax', 'gomax', 'bomax')),
    },
    'lut3d': {
        'intensity': (('intensity',), 1., 0., 1., ('c0_opacity', 'c1_opacity', 'c2_opacity')),
    },
}
ALIASES = {
    alias: canonical for canonical, aliases in {
        'blur': ('blur', 'gaussian_blur', 'gblur'),
        'color_contrast': ('color_contrast', 'colorcontrast'),
        'lens_correction': ('lens_correction', 'lenscorrection'),
        'chroma_key': ('chroma_key', 'chromakey', 'green_screen'),
        'color_temperature': ('color_temperature', 'temperature', 'warmth'),
        'color_balance': ('color_balance', 'colorbalance'),
        'color_wheel': ('color_wheel', 'three_way_color', 'three_way_wheel'),
        'exposure': ('exposure',),
        'color_levels': ('color_levels', 'levels', 'colorlevels'),
        'lut3d': ('lut3d', 'lut', 'cube', 'look'),
    }.items() for alias in aliases
}
BACKENDS = {
    'blur': 'gblur', 'color_contrast': 'colorcontrast',
    'lens_correction': 'lenscorrection', 'chroma_key': 'colorkey',
    'color_temperature': 'colorbalance', 'color_balance': 'colorbalance',
    'color_wheel': 'colorbalance', 'exposure': 'exposure',
    'color_levels': 'colorlevels', 'lut3d': 'blend',
}
MAX_SAMPLES = 2_000_000
MAX_COMMANDS = 200_000
MAX_BYTES = 16*1024*1024
MAX_TARGETS = 1024


def canonical(name: str) -> str | None:
    return ALIASES.get(str(name).strip().lower().replace('-', '_'))


def parameter_names(name: str) -> set[str]:
    return {alias for spec in SPECS.get(canonical(name), {}).values() for alias in spec[0]}


def normalized_tracks(effect: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = effect.get('parameters') if isinstance(effect.get('parameters'), dict) else effect
    tracks = effect.get('keyframes')
    if not isinstance(tracks, list):
        tracks = parameters.get('keyframes') if isinstance(parameters.get('keyframes'), list) else []
    effect_type = str(effect.get('type', '')).lower().replace('-', '_')
    result = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        prop = str(track.get('property', '')).strip().lower().replace('-', '_')
        for prefix in ('effect.', 'parameters.', effect_type+'.'):
            if prop.startswith(prefix):
                prop = prop[len(prefix):]
                break
        result.append({**track, 'property': prop})
    return result


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate(effect: dict[str, Any], *, duration_tick: int | None = None) -> list[dict[str, str]]:
    """Strict checks for the executable numeric color/spatial/keying channels."""
    from .selective_hsl import matches as is_hsl, validate as validate_hsl
    if is_hsl(effect.get('type', '')):
        return validate_hsl(effect, duration_tick=duration_tick)
    name = canonical(effect.get('type', ''))
    tracks = normalized_tracks(effect)
    if name is None or not tracks or effect.get('enabled', True) is False:
        return []
    return validate_tracks(tracks, SPECS[name], duration_tick=duration_tick)


def validate_tracks(tracks, specs, *, duration_tick=None):
    """Shared strict numeric authoring contract for both local execution engines."""
    errors = []
    def fail(code, message, suffix):
        errors.append({'code': code, 'message': message, 'suffix': suffix})
    names = {alias: prop for prop, spec in specs.items() for alias in spec[0]}
    seen = set()
    for index, track in enumerate(tracks):
        suffix = f'.keyframes[{index}]'
        prop = names.get(track.get('property'))
        if prop is None:
            fail('EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED', '此效果的动态属性不在可执行数值通道内', suffix+'.property')
            continue
        if prop in seen:
            fail('EFFECT_AUTOMATION_DUPLICATE_PROPERTY', '同一数值通道不能重复声明或使用重复别名', suffix+'.property')
        seen.add(prop)
        points = track.get('keyframes')
        if not isinstance(points, list) or not points:
            fail('EFFECT_AUTOMATION_KEYFRAMES_INVALID', '动态通道需要非空关键帧数组', suffix)
            continue
        previous = -1
        lower, upper = specs[prop][2:4]
        for at_index, point in enumerate(points):
            location = suffix+f'.keyframes[{at_index}]'
            if not isinstance(point, dict):
                fail('EFFECT_AUTOMATION_KEYFRAMES_INVALID', '关键帧必须是对象', location)
                continue
            at = point.get('at_tick')
            if isinstance(at, bool) or not isinstance(at, int) or at < 0 or at <= previous or (duration_tick is not None and at > duration_tick):
                fail('EFFECT_AUTOMATION_TIME_INVALID', 'tick 必须为严格递增且位于完整作者区间内的非负整数', location+'.at_tick')
            if isinstance(at, int): previous = at
            value = point.get('value')
            if not _finite_number(value) or not lower <= value <= upper:
                fail('EFFECT_AUTOMATION_VALUE_INVALID', f'数值必须位于 {lower:g}..{upper:g}', location+'.value')
            interpolation = point.get('interpolation')
            if interpolation not in {'hold', 'linear', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'}:
                fail('EFFECT_AUTOMATION_INTERPOLATION_INVALID', '关键帧插值无效', location+'.interpolation')
            if interpolation == 'bezier':
                controls = point.get('control_points')
                if (not isinstance(controls, list) or len(controls) not in (2, 4) or
                    any(not _finite_number(v) for v in controls) or
                    (len(controls) == 4 and not (0 <= controls[0] <= 1 and 0 <= controls[2] <= 1))):
                    fail('EFFECT_AUTOMATION_BEZIER_INVALID', 'Bezier 需要合法的 2/4 个有限控制点', location+'.control_points')
    return errors


@lru_cache(maxsize=16)
def runtime_options(executable: str, fingerprint: str, backend: str) -> frozenset[str]:
    result = run_process([executable, '-hide_banner', '-h', 'filter='+backend], timeout=30)
    if result.returncode:
        return frozenset()
    return frozenset(re.findall(r'^\s+(\w+)\s+<[^>]+>\s+\S*T\S*\s', result.stdout+result.stderr, re.M))


class Curve:
    def __init__(self, track, clip, start, tps):
        self.clock = track.get('_nested_clock') or clip.get('_nested_keyframe_clock')
        self.points = self.clock.get('keyframes', track['keyframes']) if self.clock else track['keyframes']
        self.ticks = [p['at_tick'] for p in self.points]
        self.start, self.tps = start, tps
        self.origin = int(clip.get('timeline_start_tick', round(start*tps)))/tps

    def value(self, display):
        local = display-self.start
        if self.clock:
            local = compose_time(self.clock['maps'], local+self.origin, inverse=True)-self.clock['authored_start']
        tick = local*self.tps
        index = bisect_right(self.ticks, tick)-1
        if index < 0: return float(self.points[0]['value'])
        if index >= len(self.points)-1: return float(self.points[-1]['value'])
        track = {'property': 'v', 'keyframes': self.points[index:index+2]}
        return keyframe_value({'keyframes': [track]}, ('v',), 0., tick)


class EffectAutomation:
    def __init__(self, root: Path, fps: str, tps: int):
        self.root, self.rate, self.tps = root, Fraction(fps), tps
        self.targets = self.samples = self.commands = self.bytes = 0
        self.alpha_compositors = 0
        self.hsl_instances = self.hsl_expression_bytes = 0

    def reserve_hsl(self, metadata, clip, start, end):
        frames = max(0, math.ceil(end*float(self.rate)-1e-9)-max(0, math.ceil(start*float(self.rate)-1e-9)))
        if metadata['bypass']:
            metadata.update(instance=None, sampled_frames=frames, state_samples=0, fps=str(self.rate),
                            ticks_per_second=self.tps, clip_id=clip.get('id'),
                            author_clock=clip.get('_nested_keyframe_clock'),
                            effect_start_seconds=start, effect_end_seconds=end)
            return
        samples = max(1, frames)*max(1, len(metadata['animated_parameters']))
        size = metadata['kernel_bytes']
        if (self.targets+self.hsl_instances >= MAX_TARGETS or self.samples+samples > MAX_SAMPLES or
                self.hsl_expression_bytes+size > MAX_BYTES):
            raise AppError('SELECTIVE_HSL_BUDGET', '分色 HSL 超过共享实例、状态样本或表达式配额', exit_code=2)
        metadata.update(instance=self.hsl_instances, sampled_frames=frames, state_samples=samples,
                        fps=str(self.rate), ticks_per_second=self.tps, clip_id=clip.get('id'),
                        author_clock=clip.get('_nested_keyframe_clock'),
                        effect_start_seconds=start, effect_end_seconds=end)
        self.hsl_instances += 1
        self.samples += samples
        self.hsl_expression_bytes += size

    def reserve_key_alpha(self):
        """Allocate a deterministic root-wide static/dynamic coverage node."""
        if self.alpha_compositors >= MAX_TARGETS:
            raise AppError('EFFECT_AUTOMATION_BUDGET', '抠像覆盖合成超出根渲染图实例配额', exit_code=2)
        target = f'avk_key_alpha_{self.alpha_compositors}'
        self.alpha_compositors += 1
        return target

    def bind(self, effect, static_filter, clip, start, end, *, resource_context=None):
        name = canonical(effect['type'])
        findings = validate(effect)
        if findings:
            raise AppError(findings[0]['code'], findings[0]['message'], exit_code=2, cause=json.dumps(findings))
        specs = SPECS[name]
        names = {alias: prop for prop, spec in specs.items() for alias in spec[0]}
        tracks = {names[track['property']]: track for track in normalized_tracks(effect)}
        return self._bind(effect, name, BACKENDS[name], specs, tracks, static_filter,
                          clip, start, end, resource_context=resource_context)

    def bind_blend(self, animation, clip, start, end):
        from .blend_automation import OpacityCurve
        curve = OpacityCurve(animation, clip, start, self.tps, self.rate)
        tracks = {'opacity': {'property': 'opacity', 'keyframes': animation['keyframes']}}
        effect = {'type': 'layer-blend-opacity', 'animation': animation}
        generated, metadata = self._bind(effect, 'layer-blend-opacity', 'colorchannelmixer',
            {'opacity': (('opacity',), 1., 0., 1., ('aa',))}, tracks,
            'colorchannelmixer=aa=1', clip, start, end,
            curves={'opacity': curve}, state_cost=1+len(animation['clock_maps']),
            resource_context={'kind': 'external-layer-opacity-v1', 'animation': animation})
        metadata.update(kind='blend-opacity-automation',
                        clock_stages=len(animation['clock_maps']),
                        parameter_clock='continuous-author-parameters-at-display-CFR',
                        alpha_operation='multiply-original-coverage-once')
        return generated, metadata

    def _bind(self, effect, name, backend, specs, tracks, static_filter, clip, start, end,
              *, resource_context=None, curves=None, state_cost=1):
        first = max(0, math.ceil(start*float(self.rate)-1e-9))
        stop = max(first, math.ceil(end*float(self.rate)-1e-9))
        samples = max(1, stop-first)*len(tracks)*state_cost
        if self.samples+samples > MAX_SAMPLES or self.targets+self.hsl_instances >= MAX_TARGETS:
            raise AppError('EFFECT_AUTOMATION_BUDGET', '动态效果超出根渲染图状态采样或实例配额', exit_code=2)
        executable = Path(ffmpeg_path()).resolve()
        fingerprint = file_fingerprint(executable)
        if not static_filter.startswith(backend+'='):
            raise AppError('EFFECT_AUTOMATION_FILTER_INVALID', '动态滤镜必须来自对应的本地固定映射', exit_code=6)
        required = {option for prop in tracks for option in specs[prop][4]}
        if not required <= runtime_options(str(executable), fingerprint, backend):
            raise AppError('EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE', '本地 FFmpeg 缺少所需滤镜运行时数值命令', exit_code=6)
        identity = {'protocol': 'native-color-command-cfr-v1', 'effect': effect,
                    'static_filter': static_filter, 'clock': clip.get('_nested_keyframe_clock'),
                    'start': start, 'end': end, 'fps': str(self.rate), 'serial': self.targets}
        if resource_context is not None:
            identity['resource_context'] = resource_context
        token = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]
        target = f'avk_ea_{self.targets}_{token}'
        curves = curves if curves is not None else {prop: Curve(track, clip, start, self.tps) for prop, track in tracks.items()}
        lines, previous, clamps = [], {}, 0
        command_count = 0
        for offset, frame in enumerate(range(first, max(first+1, stop))):
            display = float(Fraction(frame, 1)/self.rate)
            values = {}
            for prop, curve in curves.items():
                value = curve.value(display)
                if not math.isfinite(value):
                    raise AppError('EFFECT_AUTOMATION_VALUE_INVALID', '动态效果求值产生非有限数字', exit_code=2)
                bounded = max(specs[prop][2], min(specs[prop][3], value))
                clamps += bounded != value
                if name == 'color_temperature':
                    delta = max(-1., min(1., (bounded-6500)/6500))
                    native_values = (-delta*.30, -delta*.05, delta*.30)
                else:
                    native_values = (bounded,)*len(specs[prop][4])
                values.update((option, f'{value:.6f}') for option, value in zip(specs[prop][4], native_values))
            changed = {option: value for option, value in values.items() if previous.get(option) != value}
            if changed:
                at = 0. if offset == 0 else float((Fraction(frame, 1)-Fraction(1, 2))/self.rate)
                commands = ', '.join(f'{backend}@{target} {option} {value}' for option, value in changed.items())
                lines.append(f'{at:.12f} {commands};')
                command_count += len(changed)
                if self.commands+command_count > MAX_COMMANDS:
                    raise AppError('EFFECT_AUTOMATION_BUDGET', '动态效果超出根渲染图命令配额', exit_code=2)
            previous = values
        text = '\n'.join(lines)+'\n'
        size = len(text.encode('utf-8'))
        if self.bytes+size > MAX_BYTES:
            raise AppError('EFFECT_AUTOMATION_BUDGET', '动态效果超出根渲染图命令文本配额', exit_code=2)
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        relative = f'cache/effect-automation/{digest}.ffcmd'
        path = self.root/relative
        if path.exists():
            if sha256_file(path) != digest:
                raise AppError('EFFECT_AUTOMATION_CACHE_HASH_MISMATCH', '动态效果命令缓存摘要不匹配', exit_code=6, path=relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, text)
        self.targets += 1; self.samples += samples; self.commands += command_count; self.bytes += size
        metadata = {'kind': 'effect-automation', 'protocol': 'native-color-command-cfr-v1',
                    'clip_id': clip.get('id'), 'effect': name, 'parameters': sorted(tracks),
                    'backend': backend, 'target': target, 'ffmpeg_sha256': 'sha256:'+fingerprint,
                    'fps': str(self.rate), 'ticks_per_second': self.tps,
                    'sampled_frames': stop-first, 'state_samples': samples,
                    'frame_start': first, 'frame_stop_exclusive': stop,
                    'commands_between_samples': True, 'initial_state_explicit': True,
                    'command_count': command_count, 'command_file': relative,
                    'command_file_sha256': 'sha256:'+digest, 'command_bytes': size,
                    'clamped_parameter_samples': clamps, 'author_clock': clip.get('_nested_keyframe_clock'),
                    'effect_start_seconds': start, 'effect_end_seconds': end,
                    'native_value_serialization': 'six-decimals-matches-static-filter-options'}
        named = static_filter.replace(backend+'=', backend+'@'+target+'=', 1)
        if resource_context is not None:
            metadata['resource_context'] = resource_context
        return ['sendcmd=filename='+_quoted(relative), named], metadata

    def bind_lut(self, effect, lut_filter, lut_path, clip, start, end):
        """Mix ungraded/graded RGB on the author clock, keeping alpha exact.

        A connected multi-chain fragment fits every existing effect-chain
        caller. All labels derive from the shared allocator's unique target;
        the source is split after conversion, so both blend inputs have the
        same format, frames and PTS, including transparent pixels.
        """
        path = Path(lut_path).resolve()
        resource = {'kind': 'lut-pixel-mix-v1',
                    'lut_sha256': 'sha256:'+sha256_file(path),
                    'lut_uri': path.relative_to(self.root.resolve()).as_posix(),
                    'format': 'gbrap', 'rgb_mix': 'w*graded+(1-w)*original',
                    'alpha': 'unchanged', 'interpolation': lut_filter.rsplit(':interp=', 1)[-1],
                    'precision': '8-bit-encoded-RGB'}
        generated, metadata = self.bind(effect,
            'blend=c0_opacity=1:c1_opacity=1:c2_opacity=1:c3_opacity=1:shortest=1',
            clip, start, end, resource_context=resource)
        target = metadata['target']
        dry, wet, graded = (target+'_'+suffix for suffix in ('dry', 'wet', 'graded'))
        fragment = (f'format=gbrap,{generated[0]},split=2[{dry}][{wet}];'
                    f'[{wet}]{lut_filter}[{graded}];[{graded}][{dry}]{generated[1]}')
        return [fragment], metadata

    def summary(self):
        return {'kind': 'effect-automation-budget', 'recursive_shared': True,
                'targets': self.targets, 'state_samples': self.samples, 'commands': self.commands,
                'command_bytes': self.bytes, 'key_alpha_compositors': self.alpha_compositors,
                'selective_hsl_instances': self.hsl_instances, 'selective_hsl_expression_bytes': self.hsl_expression_bytes,
                'effect_instances_total': self.targets+self.hsl_instances,
                'limits': {'targets': MAX_TARGETS, 'state_samples': MAX_SAMPLES,
                           'commands': MAX_COMMANDS, 'command_bytes': MAX_BYTES,
                           'key_alpha_compositors': MAX_TARGETS, 'selective_hsl_expression_bytes': MAX_BYTES}}
