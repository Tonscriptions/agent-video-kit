"""Paint glyph coverage and authored colors as separate straight-alpha layers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any

from .errors import AppError
from .media import ffmpeg_path
from .text_highlight import file_fingerprint
from .utils import atomic_write_json, run_process

COLOR_KEYS = ('boxcolor', 'shadowcolor', 'bordercolor', 'fontcolor')


def resolve_color(root: Path, value: Any) -> tuple[tuple[int, int, int, int], dict[str, Any]]:
    """Use the actual local FFmpeg color parser, never a remote color service."""
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9#@._+\-]{1,96}', value):
        raise AppError('SUBTITLE_COLOR_INVALID', '文字颜色必须是本地 FFmpeg 支持的名称或十六进制及可选 @alpha', exit_code=2)
    if value.lower().split('@', 1)[0] in {'random', 'bikeshed'}:
        raise AppError('SUBTITLE_COLOR_NONDETERMINISTIC', '文字颜色不能使用随机颜色；请显式指定颜色', exit_code=2)
    executable = Path(ffmpeg_path()).resolve()
    identity = {'protocol': 'ffmpeg-rgba-color-v1', 'ffmpeg_sha256': file_fingerprint(executable), 'value': value}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode('utf-8')).hexdigest()
    directory = root / 'cache' / 'text-colors' / digest
    directory.mkdir(parents=True, exist_ok=True)
    cached = directory / 'color.json'
    rgba = None
    if cached.is_file():
        try:
            record = json.loads(cached.read_text(encoding='utf-8-sig'))
            if record['identity'] == identity and isinstance(record['rgba'], list) and len(record['rgba']) == 4 and all(type(v) is int and 0 <= v <= 255 for v in record['rgba']):
                rgba = tuple(record['rgba'])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if rgba is None:
        with tempfile.NamedTemporaryFile(dir=directory, suffix='.rgba', delete=False) as handle:
            output = Path(handle.name)
        try:
            result = run_process([str(executable), '-v', 'error', '-y', '-f', 'lavfi',
                '-i', f'color=c={value}:s=2x2:r=1:d=1,format=rgba',
                '-frames:v', '1', '-pix_fmt', 'rgba', '-f', 'rawvideo', str(output)], cwd=root, timeout=30)
            if result.returncode:
                raise AppError('SUBTITLE_COLOR_INVALID', '本地 FFmpeg 拒绝了文字颜色', exit_code=2,
                               cause=result.stderr[-1500:])
            raw = output.read_bytes()
            if len(raw) != 16 or any(raw[index:index+4] != raw[:4] for index in (4, 8, 12)):
                raise AppError('SUBTITLE_COLOR_PROBE_FAILED', '本地颜色探针没有返回一致的 2×2 RGBA 像素', exit_code=6)
            rgba = tuple(raw[:4])
            atomic_write_json(cached, {'identity': identity, 'rgba': list(rgba)})
        finally:
            output.unlink(missing_ok=True)
    return rgba, {**identity, 'cache_key': digest, 'rgba': list(rgba)}


def paint_drawtext(root: Path, parts: list[str], scope: str) -> tuple[str, dict[str, Any]]:
    """Retain native layout; source-over box, shadow, border, fill coverage."""
    options = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
    enabled = {
        'boxcolor': options.get('box', '0') in {'1', 'true'},
        'shadowcolor': bool(int(options.get('shadowx', '0')) or int(options.get('shadowy', '0'))),
        'bordercolor': int(options.get('borderw', '0')) > 0,
        'fontcolor': True,
    }
    default = {'fontcolor': 'white', 'boxcolor': 'white', 'shadowcolor': 'black', 'bordercolor': 'black'}
    colors, components = [], []
    for key in COLOR_KEYS:
        if not enabled[key]:
            continue
        color = options.get(key, default[key]).strip("'")
        rgba, record = resolve_color(root, color)
        colors.append({'component': key, **record})
        if rgba[3]:
            components.append((key, rgba))
    evidence = {'engine': 'straight-component-source-over', 'coverage': 'opaque-white-drawtext-on-opaque-black',
                'component_order': [key for key, _ in components], 'colors': colors,
                'alpha_application': 'coverage-times-color-alpha-once', 'working_color': 'encoded-rgb-8bit'}
    typing = re.match(r'drawtext@(avk_typing_[A-Za-z0-9_]+)=', parts[0])
    command_targets: list[str] = []
    if typing:
        evidence['command_targets'] = {typing[1]: command_targets}
    if not components:
        return 'null', evidence
    token = hashlib.sha256((scope + json.dumps(parts)).encode('utf-8')).hexdigest()[:16]
    base = f'paint_{token}_base'
    masks = [f'paint_{token}_mask{i}' for i in range(len(components))]
    filters = [f'split={len(components)+1}[{base}]' + ''.join(f'[{label}]' for label in masks)]
    previous = base
    for index, ((component, rgba), mask) in enumerate(zip(components, masks)):
        # Keep geometry options even for invisible components: they affect
        # fix_bounds, clipping, alignment and the shadow's outlined bitmap.
        mask_parts = [parts[0], *(part for part in parts[1:] if part.split('=', 1)[0] not in COLOR_KEYS)]
        if typing:
            target_name = f'{typing[1]}_{token}_{index}'
            mask_parts[0] = mask_parts[0].replace('drawtext@'+typing[1]+'=', 'drawtext@'+target_name+'=', 1)
            command_targets.append(target_name)
        mask_parts.extend(f'{key}={"white" if key == component else "black@0"}' for key in COLOR_KEYS)
        colored = f'paint_{token}_color{index}'
        r, g, b, a = rgba
        filters.append(f'[{mask}]format=rgba,lutrgb=r=0:g=0:b=0:a=255,' + ':'.join(mask_parts)
            + f",format=gbrap,geq=r={r}:g={g}:b={b}:a='r(X,Y)*{a}/255',format=rgba[{colored}]")
        target = f'paint_{token}_over{index}'
        filters.append(f'[{previous}][{colored}]overlay=x=0:y=0:format=rgb:alpha=straight:shortest=1[{target}]')
        previous = target
    # A trailing unlabelled filter lets the caller concatenate another line,
    # select active text colors, transform a title, or composite inline text.
    filters.append(f'[{previous}]format=rgba')
    return ';'.join(filters), evidence
